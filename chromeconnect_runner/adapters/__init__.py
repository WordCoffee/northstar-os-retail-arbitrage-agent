"""Chrome Connect site adapters (P6-T3)."""

try:
    from .costco import CostcoAdapter
    from .amazon_public import AmazonPublicAdapter
    from .vendor_dashboards import VendorDashboardsAdapter
    from .sellersprite import SellerSpriteAdapter
    from .palletfly import PalletFlyAdapter
    from .prime_national_distribution import PrimeNationalDistributionAdapter
except ImportError:
    import sys, os
    _p = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from adapters.costco import CostcoAdapter
    from adapters.amazon_public import AmazonPublicAdapter
    from adapters.vendor_dashboards import VendorDashboardsAdapter
    from adapters.sellersprite import SellerSpriteAdapter
    from adapters.palletfly import PalletFlyAdapter
    from adapters.prime_national_distribution import PrimeNationalDistributionAdapter

__all__ = [
    "CostcoAdapter", "AmazonPublicAdapter", "VendorDashboardsAdapter",
    "SellerSpriteAdapter", "PalletFlyAdapter", "PrimeNationalDistributionAdapter",
]
