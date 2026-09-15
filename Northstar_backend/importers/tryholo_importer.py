"""Tryholo.ai Content Importer

Imports AI-generated content from Tryholo.ai (tryholo.ai) into the
Northstar social_content table. Tryholo generates:
- Product images (lifestyle, infographic, A+ content)
- Social media posts (Instagram, TikTok, Facebook)
- Email marketing content
- Ad creatives (Sponsored Products, DSP)

Data source: Tryholo.ai API responses (JSON format) or downloaded files.

Usage:
    importer = TryholoImporter(db)
    result = importer.import_from_file("path/to/tryholo_response.json")
    result = importer.import_from_string(json_text, product_asin="B0123456789")
    result = importer.list_generated_content(asin="B0123456789")
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Content type classification
CONTENT_TYPES = {
    "image": ["image", "photo", "picture", "infographic", "lifestyle", "product_image"],
    "ad_creative": ["ad", "creative", "sponsored", "dsp", "banner", "headline"],
    "social_post": ["social", "post", "instagram", "tiktok", "facebook", "twitter"],
    "email": ["email", "newsletter", "promo", "marketing_email"],
    "a_plus": ["aplus", "a_plus", "a+", "brand_story", "enhanced_content"],
    "video": ["video", "reel", "short", "clip"],
}

# Channel name normalization
CHANNEL_MAP = {
    "instagram": "instagram",
    "ig": "instagram",
    "tiktok": "tiktok",
    "tk": "tiktok",
    "facebook": "facebook",
    "fb": "facebook",
    "twitter": "twitter",
    "x": "twitter",
    "youtube": "youtube",
    "yt": "youtube",
    "email": "email",
    "newsletter": "email",
    "amazon": "amazon",
    "sponsored_products": "amazon",
    "dsp": "amazon",
}


class TryholoImporter:
    """Import Tryholo.ai generated content into the Northstar data layer.

    Reads Tryholo API response JSON and maps content items to the
    social_content table. Tracks which content was generated for which
    products.

    Usage:
        importer = TryholoImporter(db)

        # Import from a JSON file
        result = importer.import_from_file("path/to/tryholo_response.json")

        # Import from a JSON string
        result = importer.import_from_string(json_text, product_asin="B0123456789")

        # List all generated content for a product
        content = importer.list_generated_content(asin="B0123456789")

        # Auto-discover and import all Tryholo files in data directory
        result = importer.import_all_from_directory()
    """

    def __init__(self, db=None, data_dir: Optional[str] = None):
        from data_layer import get_db, NorthstarDB

        if db is None:
            db = get_db()
        self.db = db
        self.nsdb = NorthstarDB()
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR

    @property
    def is_configured(self) -> bool:
        """Tryholo imports don't require API keys for file-based import."""
        return True

    # ---- File Import ----

    def import_from_file(
        self,
        file_path: str,
        product_asin: Optional[str] = None,
        brand: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import Tryholo content from a JSON file.

        Args:
            file_path: Path to the Tryholo API response JSON.
            product_asin: Override ASIN for all items in the file.
            brand: Override brand for all items.

        Returns:
            {"imported": int, "skipped": int, "errors": int, "details": [...]}
        """
        path = Path(file_path)
        if not path.exists():
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "details": [],
                "reason": f"file_not_found: {file_path}",
            }

        try:
            content = path.read_text(encoding="utf-8")
            return self.import_from_string(content, product_asin, brand)
        except Exception as e:
            logger.error(f"Failed to read Tryholo file {file_path}: {e}")
            return {
                "imported": 0,
                "skipped": 0,
                "errors": 0,
                "details": [],
                "reason": f"read_error: {e}",
            }

    # ---- String Import ----

    def import_from_string(
        self,
        json_content: str,
        product_asin: Optional[str] = None,
        brand: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import Tryholo content from a JSON string.

        Supports multiple JSON structures:
        1. Single content item: {"type": "...", "content": "...", ...}
        2. Array of items: [{...}, {...}]
        3. API response wrapper: {"data": [...]} or {"results": [...]}
        4. Nested by product: {"asin": "B0xxx", "content": [...]}

        Args:
            json_content: Raw JSON text.
            product_asin: Override ASIN.
            brand: Override brand.

        Returns:
            {"imported": int, "skipped": int, "errors": int, "details": [...]}
        """
        result = {"imported": 0, "skipped": 0, "errors": 0, "details": []}

        try:
            data = json.loads(json_content)
        except json.JSONDecodeError as e:
            result["errors"] = 1
            result["details"].append({"error": f"Invalid JSON: {e}"})
            return result

        # Normalize to a list of content items
        items = self._extract_items(data)

        if not items:
            result["reason"] = "no_content_items_found"
            return result

        for idx, item in enumerate(items):
            try:
                content_record = self._parse_content_item(
                    item, product_asin, brand
                )

                if not content_record:
                    result["skipped"] += 1
                    continue

                # Deduplication check
                dedup_source = content_record.get("media_urls", "")
                asin = content_record.get("asin", "")

                existing = self.db.execute(
                    """SELECT id FROM social_content
                       WHERE asin = ? AND channel = ? AND content_type = ?
                       AND body = ?""",
                    (
                        asin,
                        content_record.get("channel", ""),
                        content_record.get("content_type", ""),
                        content_record.get("body", "")[:200],
                    ),
                ).fetchone()

                if existing:
                    result["skipped"] += 1
                    continue

                # Insert into social_content
                record_channel = content_record.get("channel", "")
                record_id = f"tryholo-{hash(f'{asin}:{record_channel}:{idx}')[:16]}"

                self.db.execute(
                    """INSERT OR REPLACE INTO social_content
                       (id, asin, brand, channel, content_type, body,
                        hashtags, media_urls, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record_id,
                        asin,
                        content_record.get("brand", ""),
                        content_record.get("channel", ""),
                        content_record.get("content_type", ""),
                        content_record.get("body", ""),
                        content_record.get("hashtags", ""),
                        content_record.get("media_urls", ""),
                        content_record.get("status", "draft"),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                self.db.commit()

                result["imported"] += 1
                result["details"].append(
                    {
                        "index": idx,
                        "asin": asin,
                        "channel": content_record.get("channel", ""),
                        "content_type": content_record.get("content_type", ""),
                        "status": "imported",
                    }
                )

            except Exception as e:
                result["errors"] += 1
                logger.error(f"Error processing Tryholo item {idx}: {e}")

        logger.info(
            f"Tryholo import: {result['imported']} imported, "
            f"{result['skipped']} skipped, {result['errors']} errors"
        )
        return result

    # ---- Batch Import ----

    def import_all_from_directory(self) -> Dict[str, Any]:
        """Auto-discover and import all Tryholo JSON files in data dir.

        Returns:
            Combined results dict.
        """
        if not self.data_dir.exists():
            return {
                "results": {},
                "total_imported": 0,
                "total_errors": 0,
                "reason": f"directory_not_found: {self.data_dir}",
            }

        patterns = ["*tryholo*", "*try_holo*", "*tryholo.ai*"]
        files_found = set()
        for pattern in patterns:
            files_found.update(self.data_dir.glob(f"{pattern}.json"))

        if not files_found:
            return {
                "results": {},
                "total_imported": 0,
                "total_errors": 0,
                "reason": "no_tryholo_files_found",
            }

        results = {}
        for file_path in sorted(files_found):
            file_result = self.import_from_file(str(file_path))
            results[file_path.name] = file_result

        total_imported = sum(r.get("imported", 0) for r in results.values())
        total_errors = sum(r.get("errors", 0) for r in results.values())

        return {
            "results": results,
            "total_imported": total_imported,
            "total_errors": total_errors,
            "files_processed": len(results),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ---- Query ----

    def list_generated_content(
        self,
        asin: Optional[str] = None,
        channel: Optional[str] = None,
        content_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List Tryholo-generated content with optional filters.

        Args:
            asin: Filter by ASIN.
            channel: Filter by channel (instagram, email, etc.).
            content_type: Filter by content type (image, ad_creative, etc.).
            status: Filter by status (draft, published, etc.).
            limit: Max records to return.

        Returns:
            List of content records.
        """
        sql = "SELECT * FROM social_content WHERE 1=1"
        params = []

        if asin:
            sql += " AND asin = ?"
            params.append(asin)
        if channel:
            sql += " AND channel = ?"
            params.append(channel)
        if content_type:
            sql += " AND content_type = ?"
            params.append(content_type)
        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cur = self.db.execute(sql, tuple(params))
        return [dict(row) for row in cur.fetchall()]

    # ---- Parsing Helpers ----

    def _extract_items(self, data: Any) -> List[Dict[str, Any]]:
        """Extract content items from various JSON structures.

        Handles:
        - List of items
        - Dict with "data", "results", "content", "items", "creatives" key
        - Dict with "asin" and "content" keys
        - Single item dict
        """
        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            # Try common wrapper keys
            for key in ("data", "results", "content", "items", "creatives",
                        "generated_content", "outputs", "assets"):
                if key in data:
                    val = data[key]
                    if isinstance(val, list):
                        return val
                    if isinstance(val, dict):
                        return [val]

            # Check if this dict is itself a content item
            if self._is_content_item(data):
                return [data]

            # Nested by product
            if "asin" in data and ("content" in data or "items" in data):
                inner = data.get("content") or data.get("items", [])
                if isinstance(inner, list):
                    # Inject ASIN into each item
                    for item in inner:
                        if isinstance(item, dict):
                            item.setdefault("asin", data["asin"])
                            item.setdefault("brand", data.get("brand", ""))
                    return inner
                elif isinstance(inner, dict):
                    inner.setdefault("asin", data["asin"])
                    return [inner]

        return []

    def _is_content_item(self, obj: Dict[str, Any]) -> bool:
        """Check if a dict looks like a Tryholo content item."""
        has_content = any(
            k in obj
            for k in (
                "body", "text", "content", "caption", "copy",
                "image_url", "media_url", "output_url", "url",
                "headlines", "description",
            )
        )
        has_type = any(
            k in obj
            for k in ("type", "content_type", "format", "category")
        )
        return has_content or has_type

    def _parse_content_item(
        self,
        item: Dict[str, Any],
        asin_override: Optional[str] = None,
        brand_override: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Parse a Tryholo content item into a social_content record.

        Returns:
            Dict with fields for social_content table, or None to skip.
        """
        asin = asin_override or item.get("asin", "")
        brand = brand_override or item.get("brand", "")

        # Determine content type
        raw_type = (
            item.get("type")
            or item.get("content_type")
            or item.get("format")
            or item.get("category")
            or ""
        ).lower()
        content_type = self._classify_content_type(raw_type)

        # Determine channel
        raw_channel = (
            item.get("channel")
            or item.get("platform")
            or item.get("destination")
            or item.get("publish_to")
            or ""
        ).lower()
        channel = CHANNEL_MAP.get(raw_channel, raw_channel or "general")

        # Extract body/copy text
        body = (
            item.get("body")
            or item.get("text")
            or item.get("content")
            or item.get("caption")
            or item.get("copy")
            or item.get("headline")
            or ""
        )

        # Handle structured content (headlines + description)
        if not body:
            headlines = item.get("headlines", [])
            description = item.get("description", "")
            if isinstance(headlines, list):
                body = "\n".join(str(h) for h in headlines)
            if description:
                body = f"{body}\n\n{description}".strip()

        if not body and not item.get("image_url") and not item.get("media_url"):
            return None  # No usable content

        # Extract media URLs
        media_urls = []
        for key in ("image_url", "media_url", "output_url", "url",
                     "images", "media_urls", "assets"):
            val = item.get(key)
            if val:
                if isinstance(val, list):
                    media_urls.extend(str(v) for v in val if v)
                elif isinstance(val, str):
                    media_urls.append(val)

        # Extract hashtags
        hashtags = item.get("hashtags", "")
        if isinstance(hashtags, list):
            hashtags = " ".join(f"#{h.lstrip('#')}" for h in hashtags)

        # Determine status
        status = item.get("status", "draft")
        if status not in ("draft", "scheduled", "published", "archived"):
            status = "draft"

        return {
            "asin": asin,
            "brand": brand,
            "channel": channel,
            "content_type": content_type,
            "body": body[:4000] if body else "",  # Truncate very long content
            "hashtags": str(hashtags)[:500],
            "media_urls": json.dumps(media_urls) if media_urls else "",
            "status": status,
        }

    def _classify_content_type(self, raw_type: str) -> str:
        """Classify a raw content type string into a standard category."""
        if not raw_type:
            return "general"

        raw_lower = raw_type.lower().replace(" ", "_").replace("-", "_")

        for std_type, keywords in CONTENT_TYPES.items():
            if any(kw in raw_lower for kw in keywords):
                return std_type

        return raw_lower or "general"
