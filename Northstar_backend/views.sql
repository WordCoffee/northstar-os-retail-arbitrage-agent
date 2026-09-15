-- Northstar OS — Database Views for Analytics
-- These views provide pre-computed analytics for the dashboard and API endpoints.
-- Compatible with both SQLite and PostgreSQL (use conditional syntax where needed).

-- =========================================================================
-- View: Product Summary
-- Joins products with latest keyword performance, campaigns, and listings.
-- =========================================================================
CREATE VIEW IF NOT EXISTS v_product_summary AS
SELECT
    p.asin,
    p.title,
    p.brand,
    p.category,
    p.amazon_price,
    p.costco_cost,
    p.net_profit,
    p.roi_pct,
    p.bsr_rank,
    p.monthly_sales_estimate,
    p.review_count,
    p.rating,
    p.seller_count,
    p.risk_score,
    p.authorization_status,
    p.last_enriched_at,
    -- Best keyword performance
    (SELECT kp.organic_rank FROM keyword_performance kp
     WHERE kp.asin = p.asin AND kp.organic_rank IS NOT NULL
     ORDER BY kp.recorded_at DESC LIMIT 1) AS latest_organic_rank,
    -- Campaign performance
    (SELECT c.acos FROM campaigns c
     WHERE c.asin = p.asin AND c.status = 'enabled'
     ORDER BY c.updated_at DESC LIMIT 1) AS active_acos,
    (SELECT c.spend FROM campaigns c
     WHERE c.asin = p.asin AND c.status = 'enabled'
     ORDER BY c.updated_at DESC LIMIT 1) AS active_spend,
    -- Listing scores
    (SELECT l.overall_score FROM listings l
     WHERE l.asin = p.asin
     ORDER BY l.version DESC LIMIT 1) AS listing_score,
    (SELECT l.rufus_score FROM listings l
     WHERE l.asin = p.asin
     ORDER BY l.version DESC LIMIT 1) AS rufus_score,
    -- Transaction summary (30-day)
    (SELECT COALESCE(SUM(t.amount), 0) FROM transactions t
     WHERE t.asin = p.asin AND t.transaction_type = 'sale'
     AND t.report_date >= date('now', '-30 days')) AS revenue_30d,
    (SELECT COALESCE(SUM(t.amount), 0) FROM transactions t
     WHERE t.asin = p.asin AND t.transaction_type = 'sale'
     AND t.report_date >= date('now', '-90 days')) AS revenue_90d
FROM products p;


-- =========================================================================
-- View: Keyword Performance Summary
-- Latest performance per keyword per ASIN.
-- =========================================================================
CREATE VIEW IF NOT EXISTS v_keyword_summary AS
SELECT
    k.id AS keyword_id,
    k.keyword,
    k.search_volume,
    k.competition_level,
    k.associated_asins,
    kp.asin,
    kp.organic_rank,
    kp.sponsored_rank,
    kp.impressions,
    kp.clicks,
    kp.spend,
    kp.orders,
    kp.revenue,
    kp.acos,
    kp.tier,
    kp.movement,
    kp.recorded_at
FROM keywords k
INNER JOIN keyword_performance kp ON k.id = kp.keyword_id
WHERE kp.id IN (
    SELECT kp2.id FROM keyword_performance kp2
    WHERE kp2.keyword_id = kp.keyword_id AND kp2.asin = kp.asin
    ORDER BY kp2.recorded_at DESC
    LIMIT 1
);


-- =========================================================================
-- View: Campaign Performance Dashboard
-- =========================================================================
CREATE VIEW IF NOT EXISTS v_campaign_dashboard AS
SELECT
    c.id AS campaign_id,
    c.asin,
    p.title AS product_title,
    c.campaign_type,
    c.campaign_name,
    c.status,
    c.daily_budget,
    c.targeting_type,
    c.impressions,
    c.clicks,
    c.spend,
    c.orders,
    c.revenue,
    c.acos,
    c.roas,
    CASE
        WHEN c.acos IS NULL THEN 'no_data'
        WHEN c.acos < 15 THEN 'excellent'
        WHEN c.acos < 30 THEN 'good'
        WHEN c.acos < 45 THEN 'needs_optimization'
        ELSE 'losing_money'
    END AS performance_tier,
    c.updated_at
FROM campaigns c
LEFT JOIN products p ON c.asin = p.asin;


-- =========================================================================
-- View: Financial Summary
-- Revenue, costs, profit per ASIN.
-- =========================================================================
CREATE VIEW IF NOT EXISTS v_financial_summary AS
SELECT
    t.asin,
    p.title,
    p.costco_cost,
    p.amazon_price,
    SUM(CASE WHEN t.transaction_type = 'sale' THEN t.amount ELSE 0 END) AS total_revenue,
    SUM(CASE WHEN t.transaction_type = 'cost' THEN t.amount ELSE 0 END) AS total_costs,
    SUM(CASE WHEN t.transaction_type = 'refund' THEN t.amount ELSE 0 END) AS total_refunds,
    SUM(CASE WHEN t.transaction_type = 'sale' THEN t.amount ELSE 0 END)
        - SUM(CASE WHEN t.transaction_type IN ('cost', 'refund') THEN t.amount ELSE 0 END) AS net_profit,
    COUNT(CASE WHEN t.transaction_type = 'sale' THEN 1 END) AS total_orders,
    MIN(t.report_date) AS first_sale_date,
    MAX(t.report_date) AS last_sale_date
FROM transactions t
LEFT JOIN products p ON t.asin = p.asin
GROUP BY t.asin;


-- =========================================================================
-- View: Search Query Performance
-- Brand Analytics data with derived metrics.
-- =========================================================================
CREATE VIEW IF NOT EXISTS v_search_queries AS
SELECT
    sqp.query,
    sqp.asin,
    sqp.impressions,
    sqp.clicks,
    sqp.cart_adds,
    sqp.purchases,
    sqp.impression_share,
    sqp.click_share,
    sqp.purchase_share,
    sqp.search_frequency_rank,
    sqp.date_start,
    sqp.date_end,
    -- Derived metrics
    CASE WHEN sqp.impressions > 0 THEN sqp.clicks * 100.0 / sqp.impressions ELSE 0 END AS ctr_pct,
    CASE WHEN sqp.clicks > 0 THEN sqp.purchases * 100.0 / sqp.clicks ELSE 0 END AS conversion_pct,
    p.title AS product_title,
    p.category
FROM search_query_performance sqp
LEFT JOIN products p ON sqp.asin = p.asin;


-- =========================================================================
-- View: System Health Dashboard
-- =========================================================================
CREATE VIEW IF NOT EXISTS v_system_health AS
SELECT
    (SELECT COUNT(*) FROM products) AS total_products,
    (SELECT COUNT(*) FROM products WHERE last_enriched_at > datetime('now', '-7 days')) AS products_enriched_7d,
    (SELECT COUNT(*) FROM keywords) AS total_keywords,
    (SELECT COUNT(*) FROM listings) AS total_listings,
    (SELECT COUNT(*) FROM campaigns WHERE status = 'enabled') AS active_campaigns,
    (SELECT COUNT(*) FROM transactions WHERE transaction_type = 'sale'
     AND report_date >= date('now', '-30 days')) AS orders_30d,
    (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE transaction_type = 'sale'
     AND report_date >= date('now', '-30 days')) AS revenue_30d,
    (SELECT COUNT(*) FROM memory_entries WHERE retired_at IS NULL) AS active_memories,
    (SELECT COUNT(*) FROM audit_log WHERE created_at > datetime('now', '-24 hours')) AS audit_entries_24h;


-- =========================================================================
-- View: Keyword Lifecycle (tier tracking)
-- =========================================================================
CREATE VIEW IF NOT EXISTS v_keyword_lifecycle AS
SELECT
    kp.asin,
    kp.keyword_id,
    k.keyword,
    kp.tier,
    kp.movement,
    kp.days_in_tier,
    kp.impressions,
    kp.clicks,
    kp.orders,
    kp.acos,
    kp.recorded_at,
    CASE
        WHEN kp.tier = 'winner' THEN 1
        WHEN kp.tier = 'almost_winner' THEN 2
        WHEN kp.tier = 'performer' THEN 3
        WHEN kp.tier = 'bench' THEN 4
        ELSE 5
    END AS tier_rank
FROM keyword_performance kp
LEFT JOIN keywords k ON kp.keyword_id = k.id
ORDER BY tier_rank ASC, kp.impressions DESC;


-- =========================================================================
-- View: Product Performance Scorecard
-- Composite scoring for dashboard display.
-- =========================================================================
CREATE VIEW IF NOT EXISTS v_product_scorecard AS
SELECT
    p.asin,
    p.title,
    p.brand,
    p.category,
    p.costco_cost,
    p.amazon_price,
    p.net_profit,
    p.roi_pct,
    p.bsr_rank,
    p.monthly_sales_estimate,
    -- Composite score (0-100)
    (
        -- Profit margin component (0-30)
        MIN(30, MAX(0, CASE
            WHEN p.net_profit IS NULL THEN 0
            WHEN p.net_profit >= 50 THEN 30
            WHEN p.net_profit >= 20 THEN 20
            WHEN p.net_profit >= 10 THEN 10
            ELSE 5
        END))
        +
        -- Velocity component (0-25)
        MIN(25, MAX(0, CASE
            WHEN p.monthly_sales_estimate IS NULL THEN 0
            WHEN p.monthly_sales_estimate >= 5000 THEN 25
            WHEN p.monthly_sales_estimate >= 2000 THEN 20
            WHEN p.monthly_sales_estimate >= 500 THEN 15
            WHEN p.monthly_sales_estimate >= 100 THEN 10
            ELSE 5
        END))
        +
        -- Competition component (0-20)
        MIN(20, MAX(0, CASE
            WHEN p.seller_count IS NULL THEN 10
            WHEN p.seller_count <= 2 THEN 20
            WHEN p.seller_count <= 5 THEN 15
            WHEN p.seller_count <= 10 THEN 10
            ELSE 5
        END))
        +
        -- Listing quality component (0-15)
        MIN(15, MAX(0, COALESCE(
            (SELECT l.overall_score * 0.15 FROM listings l
             WHERE l.asin = p.asin ORDER BY l.version DESC LIMIT 1),
            0
        )))
        +
        -- Risk component (0-10)
        MIN(10, MAX(0, CASE
            WHEN p.risk_score IS NULL THEN 5
            WHEN p.risk_score >= 80 THEN 10
            WHEN p.risk_score >= 60 THEN 7
            ELSE 3
        END))
    ) AS composite_score
FROM products p
ORDER BY composite_score DESC;
