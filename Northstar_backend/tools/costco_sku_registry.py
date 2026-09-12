#!/usr/bin/env python
"""
Costco SKU Registry - loads and indexes all Costco SKU data for instant lookup.
"""
import json
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from quantity_parser import ParsedQuantity, parse_costco_pack

@dataclass
class CostcoSKU:
    """Costco SKU details from any source."""
    item_id: str                    # Costco item number (e.g., "1493188")
    asin: str                       # Amazon ASIN
    requested_title: str = ""       # Title from Costco
    requested_brand: str = ""
    requested_pack: str = ""        # Pack description from Costco
    costco_cost_reference: float = 0.0
    resolution: str = ""            # "resolved", "unresolved_needs_lookup", etc.
    mapped_asins: List[str] = field(default_factory=list)  # For costco_detail items
    catalog_source_url: str = ""
    match_score: float = 0.0
    pool: str = ""
    
    # Parsed quantity
    quantity: Optional['ParsedQuantity'] = None
    
    def __post_init__(self):
        if self.quantity is None and (self.requested_pack or self.item_id):
            from quantity_parser import parse_costco_pack
            self.quantity = parse_costco_pack(self.requested_pack, self.item_id)
    
    @property
    def is_multipack(self) -> bool:
        return self.quantity.is_multipack if self.quantity else False
    
    @property
    def pack_count(self) -> int:
        return self.quantity.count if self.quantity else 1
    
    def to_dict(self) -> dict:
        return {
            'item_id': self.item_id,
            'asin': self.asin,
            'requested_title': self.requested_title,
            'requested_brand': self.requested_brand,
            'requested_pack': self.requested_pack,
            'costco_cost_reference': self.costco_cost_reference,
            'resolution': self.resolution,
            'mapped_asins': self.mapped_asins,
            'catalog_source_url': self.catalog_source_url,
            'match_score': self.match_score,
            'pool': self.pool,
            'quantity': {
                'count': self.quantity.count if self.quantity else 1,
                'unit': self.quantity.unit if self.quantity else 'each',
                'unit_type': self.quantity.unit_type if self.quantity else 'item',
                'is_multipack': self.is_multipack,
            } if self.quantity else None
        }


class CostcoSKURegistry:
    """
    Loads and indexes all Costco SKU data from multiple sources for instant lookup.
    """
    
    def __init__(self, data_root: str = "data"):
        self.data_root = Path(data_root)
        self.by_asin: Dict[str, CostcoSKU] = {}      # ASIN -> CostcoSKU
        self.by_item_id: Dict[str, CostcoSKU] = {}   # item_id -> CostcoSKU
        self.all_skus: List[CostcoSKU] = []
        self._loaded = False
    
    def load_all_sources(self) -> int:
        """Load all available Costco data sources. Returns count of SKUs loaded."""
        count = 0
        
        # 1. Costco Detail Manifest (has mapped_asins)
        count += self._load_costco_detail_manifest()
        
        # 2. Kirkland Catalog Manifests (latest)
        count += self._load_kirkland_catalogs()
        
        # 3. BrightData 180 Prepared Manifest
        count += self._load_brightdata_180()
        
        # 4. Layer1 Discovery Manifests
        count += self._load_layer1_discovery()
        
        # 5. Costco Detail Manifest (the one with items array)
        count += self._load_costco_detail_manifest_items()
        
        self._loaded = True
        return len(self.by_asin)
    
    def _load_costco_detail_manifest(self) -> int:
        """Load costco_detail_manifest.json which has items with mapped_asins."""
        path = self.data_root / "catalog" / "costco_detail_manifest.json"
        if not path.exists():
            return 0
        
        data = json.loads(path.read_text())
        items = data.get('items', [])
        count = 0
        
        for item in items:
            item_id = str(item.get('item_id', ''))
            requested_pack = item.get('requested_pack', '')
            mapped = item.get('mapped_asins', [])
            
            if not mapped:
                continue
            
            # Create SKU for each mapped ASIN
            for asin in mapped:
                if not asin or not asin.startswith('B0'):
                    continue
                sku = CostcoSKU(
                    item_id=item_id,
                    asin=asin,
                    requested_title=item.get('requested_title', ''),
                    requested_brand=item.get('requested_brand', ''),
                    requested_pack=requested_pack,
                    mapped_asins=mapped,
                )
                self._add_sku(sku)
                count += 1
        
        return count
    
    def _load_costco_detail_manifest_items(self) -> int:
        """Load the items array from costco_detail_manifest (different structure)."""
        # This is the same file but different structure - already handled above
        return 0
    
    def _load_kirkland_catalogs(self) -> int:
        """Load latest Kirkland catalog manifests."""
        catalog_dir = self.data_root / "catalog"
        files = sorted(catalog_dir.glob("kirkland_catalog_manifest_*.json"), reverse=True)
        
        count = 0
        for f in files[:10]:  # Latest 10
            try:
                data = json.loads(f.read_text())
                asins_data = data.get('asins', [])
                
                if isinstance(asins_data, list):
                    for item in asins_data:
                        asin = item.get('asin')
                        if not asin or not asin.startswith('B0'):
                            continue
                        sku = CostcoSKU(
                            item_id=str(item.get('asin', '')),
                            asin=asin,
                            requested_title=item.get('title', ''),
                            requested_brand=item.get('brand', ''),
                            requested_pack='',  # Not in this format
                        )
                        self._add_sku(sku)
                        count += 1
                elif isinstance(asins_data, dict):
                    for asin, details in asins_data.items():
                        if not asin.startswith('B0'):
                            continue
                        sku = CostcoSKU(
                            item_id=str(details.get('asin', asin)),
                            asin=asin,
                            requested_title=details.get('title', ''),
                            requested_brand=details.get('brand', ''),
                            requested_pack='',
                        )
                        self._add_sku(sku)
                        count += 1
            except Exception as e:
                print(f"Warning: Failed to load {f}: {e}")
        
        return count
    
    def _load_brightdata_180(self) -> int:
        """Load BrightData 180 prepared manifest."""
        path = self.data_root / "catalog" / "brightdata_costco_180_prepared_manifest.json"
        if not path.exists():
            return 0
        
        data = json.loads(path.read_text())
        items = data.get('items', [])
        count = 0
        
        for item in items:
            if not isinstance(item, dict):
                continue
            
            # BrightData items have item_id but mostly unresolved
            item_id = str(item.get('item_id', ''))
            requested_title = item.get('requested_title', '')
            requested_brand = item.get('requested_brand', '')
            requested_pack = item.get('requested_pack', '')
            resolution = item.get('resolution', '')
            
            # Only add if we have some identifier
            if item_id and item_id != 'None':
                # Try to find ASIN from other sources via item_id
                asin = self._find_asin_by_item_id(item_id)
                if not asin:
                    # Create placeholder - will be resolved later
                    asin = f"UNKNOWN_{item_id}"
                
                sku = CostcoSKU(
                    item_id=item_id,
                    asin=asin,
                    requested_title=requested_title,
                    requested_brand=requested_brand,
                    requested_pack=requested_pack,
                    costco_cost_reference=item.get('costco_cost_reference', 0),
                    resolution=resolution,
                )
                self._add_sku(sku)
                count += 1
        
        return count
    
    def _load_layer1_discovery(self) -> int:
        """Load Layer1 discovery manifests."""
        catalog_dir = self.data_root / "catalog"
        files = sorted(catalog_dir.glob("layer1_discovery_manifest_*.json"), reverse=True)
        
        count = 0
        for f in files[:3]:  # Latest 3
            try:
                data = json.loads(f.read_text())
                asins_data = data.get('asins', [])
                
                if isinstance(asins_data, list):
                    for item in asins_data:
                        asin = item.get('asin')
                        if not asin or not asin.startswith('B0'):
                            continue
                        sku = CostcoSKU(
                            item_id=str(item.get('asin', '')),
                            asin=asin,
                            requested_title=item.get('title', ''),
                            requested_brand=item.get('brand', ''),
                            requested_pack=item.get('requested_pack', ''),
                        )
                        self._add_sku(sku)
                        count += 1
            except Exception as e:
                print(f"Warning: Failed to load {f}: {e}")
        
        return count
    
    def _find_asin_by_item_id(self, item_id: str) -> Optional[str]:
        """Try to find ASIN by item_id from already loaded SKUs."""
        if item_id in self.by_item_id:
            return self.by_item_id[item_id].asin
        return None
    
    def _add_sku(self, sku: CostcoSKU):
        """Add SKU to registry, keeping the most complete version."""
        # Index by ASIN
        if sku.asin and sku.asin not in self.by_asin:
            self.by_asin[sku.asin] = sku
            self.all_skus.append(sku)
        elif sku.asin in self.by_asin:
            # Keep the one with more complete data
            existing = self.by_asin[sku.asin]
            if len(sku.requested_pack) > len(existing.requested_pack):
                self.by_asin[sku.asin] = sku
        
        # Index by item_id
        if sku.item_id and sku.item_id not in self.by_item_id:
            self.by_item_id[sku.item_id] = sku
    
    def get_by_asin(self, asin: str) -> Optional[CostcoSKU]:
        """Get Costco SKU by ASIN."""
        return self.by_asin.get(asin)
    
    def get_by_item_id(self, item_id: str) -> Optional[CostcoSKU]:
        """Get Costco SKU by Costco item_id."""
        return self.by_item_id.get(item_id)
    
    def get_all_asins(self) -> List[str]:
        """Get all ASINs in registry."""
        return list(self.by_asin.keys())
    
    def stats(self) -> dict:
        """Return registry statistics."""
        multipack = sum(1 for s in self.by_asin.values() if s.is_multipack)
        with_pack = sum(1 for s in self.by_asin.values() if s.requested_pack)
        return {
            'total_asins': len(self.by_asin),
            'total_skus': len(self.all_skus),
            'multipack_count': multipack,
            'with_pack_info': with_pack,
            'by_item_id_count': len(self.by_item_id),
        }


# Convenience function
def load_registry(data_root: str = "data") -> CostcoSKURegistry:
    """Load and return a fully populated CostcoSKURegistry."""
    registry = CostcoSKURegistry(data_root)
    registry.load_all_sources()
    return registry


# For testing
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    registry = load_registry("Northstar_backend/data")
    stats = registry.stats()
    print(f"Registry loaded: {stats}")
    
    # Show some samples
    print("\nSample SKUs:")
    for asin, sku in list(registry.by_asin.items())[:5]:
        q = sku.quantity
        q_str = f"{q.count} {q.unit} of {q.unit_type}" if q else "N/A"
        print(f"  {asin}: {sku.requested_title[:50]} | pack: {sku.requested_pack} | qty: {q_str}")