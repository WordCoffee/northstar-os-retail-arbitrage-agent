"""SourceScout Dashboard API — production endpoints for the UI.

Provides aggregated data for the SourceScout dashboard views:
- Portfolio overview (KPIs, top products, alerts)
- Product detail with history
- Opportunity finder
- Buy list management
"""

import os
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent


def _db():
    """Get database connection."""
    import sys
    sys.path.insert(0, str(_BACKEND_DIR))
    from data_layer import get_db
    return get_db()


def portfolio_overview() -> Dict[str, Any]:
    """Get portfolio-level KPIs for the dashboard.

    Returns:
        total_products: Number of tracked products
        total_revenue_30d: Revenue in last 30 days
        total_profit_30d: Profit in last 30 days
        avg_roi: Average ROI across portfolio
        active_campaigns: Number of active ad campaigns
        alerts: List of actionable alerts
        top_products: Top 5 products by profit
    """
    db = _db()

    # Product counts
    cur = db.execute("SELECT COUNT(*) as cnt FROM products")
    total_products = cur.fetchone()["cnt"]

    cur = db.execute(
        "SELECT COUNT(*) as cnt FROM products WHERE net_profit > 0"
    )
    profitable_count = cur.fetchone()["cnt"]

    # Revenue (30-day)
    cur = db.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE transaction_type = 'sale'
        AND report_date >= date('now', '-30 days')
    """)
    revenue_30d = cur.fetchone()["total"]

    # Costs (30-day)
    cur = db.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE transaction_type IN ('cost', 'refund')
        AND report_date >= date('now', '-30 days')
    """)
    costs_30d = cur.fetchone()["total"]

    profit_30d = revenue_30d - costs_30d

    # Average ROI
    cur = db.execute(
        "SELECT AVG(roi_pct) as avg_roi FROM products WHERE roi_pct IS NOT NULL"
    )
    avg_roi = cur.fetchone()["avg_roi"] or 0

    # Active campaigns
    cur = db.execute(
        "SELECT COUNT(*) as cnt FROM campaigns WHERE status = 'enabled'"
    )
    active_campaigns = cur.fetchone()["cnt"]

    # Top products by profit
    cur = db.execute("""
        SELECT asin, title, net_profit, roi_pct, bsr_rank,
               monthly_sales_estimate, amazon_price, costco_cost
        FROM products
        WHERE net_profit IS NOT NULL
        ORDER BY net_profit DESC
        LIMIT 5
    """)
    top_products = [dict(row) for row in cur.fetchall()]

    # Alerts
    alerts = _generate_alerts()

    return {
        "total_products": total_products,
        "profitable_products": profitable_count,
        "revenue_30d": round(revenue_30d, 2),
        "costs_30d": round(costs_30d, 2),
        "profit_30d": round(profit_30d, 2),
        "avg_roi": round(avg_roi, 1),
        "active_campaigns": active_campaigns,
        "top_products": top_products,
        "alerts": alerts,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _generate_alerts() -> List[Dict[str, Any]]:
    """Generate actionable alerts for the dashboard."""
    db = _db()
    alerts = []

    # Low inventory alerts
    cur = db.execute("""
        SELECT asin, title, bsr_rank, monthly_sales_estimate
        FROM products
        WHERE bsr_rank IS NOT NULL
        AND monthly_sales_estimate > 100
        AND (authorization_status IS NULL OR authorization_status != 'blocked')
        ORDER BY monthly_sales_estimate DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        alerts.append({
            "type": "high_velocity",
            "asin": row["asin"],
            "title": row["title"],
            "message": f"BSR #{row['bsr_rank']:,} — est. {row['monthly_sales_estimate']:,} units/mo",
            "severity": "info",
        })

    # Products missing COGS
    cur = db.execute("""
        SELECT asin, title
        FROM products
        WHERE costco_cost IS NULL
        LIMIT 5
    """)
    for row in cur.fetchall():
        alerts.append({
            "type": "missing_cogs",
            "asin": row["asin"],
            "title": row["title"],
            "message": "Missing Costco COGS — cannot calculate true profit",
            "severity": "warning",
        })

    return alerts


def product_detail(asin: str) -> Dict[str, Any]:
    """Get detailed product data for the detail view."""
    db = _db()
    cur = db.execute("SELECT * FROM products WHERE asin = ?", (asin,))
    product = cur.fetchone()
    if not product:
        return {"error": f"Product {asin} not found"}

    product = dict(product)

    # Add history
    try:
        from bsr_history import get_history, compute_volatility
        product["bsr_history"] = get_history(asin, days=90)
        product["volatility"] = compute_volatility(asin, days=90)
    except ImportError:
        product["bsr_history"] = []
        product["volatility"] = {}

    # Add keyword performance
    cur = db.execute("""
        SELECT k.keyword, kp.organic_rank, kp.sponsored_rank,
               kp.impressions, kp.clicks, kp.orders, kp.acos, kp.tier
        FROM keyword_performance kp
        JOIN keywords k ON kp.keyword_id = k.id
        WHERE kp.asin = ?
        ORDER BY kp.impressions DESC
        LIMIT 20
    """, (asin,))
    product["keywords"] = [dict(row) for row in cur.fetchall()]

    # Add campaigns
    cur = db.execute(
        "SELECT * FROM campaigns WHERE asin = ? ORDER BY spend DESC",
        (asin,),
    )
    product["campaigns"] = [dict(row) for row in cur.fetchall()]

    # Add listings
    cur = db.execute(
        "SELECT * FROM listings WHERE asin = ? ORDER BY version DESC",
        (asin,),
    )
    product["listings"] = [dict(row) for row in cur.fetchall()]

    # Financial summary
    cur = db.execute("""
        SELECT transaction_type, SUM(amount) as total, SUM(quantity) as qty
        FROM transactions WHERE asin = ?
        GROUP BY transaction_type
    """, (asin,))
    product["financials"] = {row["transaction_type"]: {
        "total": row["total"], "quantity": row["qty"]
    } for row in cur.fetchall()}

    return product


def buy_list() -> List[Dict[str, Any]]:
    """Get the current buy list — products authorized for purchase."""
    db = _db()
    cur = db.execute("""
        SELECT asin, title, amazon_price, costco_cost, net_profit,
               roi_pct, bsr_rank, monthly_sales_estimate, seller_count,
               authorization_status
        FROM products
        WHERE authorization_status = 'authorized'
           OR authorization_status = 'invoice_pending'
        ORDER BY net_profit DESC
    """)
    return [dict(row) for row in cur.fetchall()]
