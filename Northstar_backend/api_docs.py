"""API documentation and OpenAPI schema for Northstar OS.

Provides auto-generated OpenAPI docs via FastAPI's built-in /docs and /redoc
endpoints, plus a comprehensive API reference in markdown format.
"""

API_METADATA = {
    "openapi": "3.1.0",
    "info": {
        "title": "Northstar OS API",
        "description": (
            "AI-powered Amazon arbitrage intelligence platform. "
            "Five services — SourceScout, ListingForge, AdPilot, SocialPulse, "
            "and AutothinK — sharing a unified data layer.\n\n"
            "## Authentication\n"
            "All endpoints require a Bearer token in the Authorization header. "
            "Get a token via `POST /api/v1/auth/login`.\n\n"
            "## Rate Limits\n"
            "Rate limits are enforced per plan tier:\n"
            "- Foundation: 30 req/min\n"
            "- Scout: 60 req/min\n"
            "- Mover: 120 req/min\n"
            "- AutothinK: 300 req/min\n\n"
            "## Data Privacy\n"
            "All AI processing runs locally via Ollama. No data is sent to "
            "external LLM APIs. Your business data never leaves your machine."
        ),
        "version": "1.0.0",
        "contact": {"name": "Northstar OS Support", "email": "support@northstaros.io"},
        "license": {"name": "Proprietary"},
    },
    "servers": [
        {"url": "http://localhost:8000", "description": "Local development"},
        {"url": "https://api.northstaros.io", "description": "Production"},
    ],
    "tags": [
        {"name": "Auth", "description": "Authentication and user management"},
        {"name": "Dashboard", "description": "Portfolio analytics and KPIs"},
        {"name": "SourceScout", "description": "Product sourcing intelligence"},
        {"name": "ListingForge", "description": "Listing generation and optimization"},
        {"name": "AdPilot", "description": "PPC advertising intelligence"},
        {"name": "SocialPulse", "description": "Social media content and attribution"},
        {"name": "AutothinK", "description": "AI workspace and orchestration"},
        {"name": "Memory", "description": "Per-account knowledge store"},
        {"name": "Health", "description": "System health and monitoring"},
    ],
}

# Endpoint registry for documentation
ENDPOINTS = {
    # Auth
    "POST /api/v1/auth/register": {
        "summary": "Register new account",
        "tags": ["Auth"],
        "plan": "foundation",
        "body": {"email": "string", "password": "string", "name": "string"},
        "response": {"user_id": "uuid", "email": "string", "plan": "foundation"},
    },
    "POST /api/v1/auth/login": {
        "summary": "Login and get JWT token",
        "tags": ["Auth"],
        "plan": "foundation",
        "body": {"email": "string", "password": "string"},
        "response": {"access_token": "string", "token_type": "bearer"},
    },
    "GET /api/v1/auth/me": {
        "summary": "Get current user profile",
        "tags": ["Auth"],
        "plan": "foundation",
        "auth": True,
    },

    # Dashboard
    "GET /api/v1/dashboard/portfolio": {
        "summary": "Portfolio KPIs (revenue, margin, inventory health)",
        "tags": ["Dashboard"],
        "plan": "foundation",
        "auth": True,
    },
    "GET /api/v1/dashboard/product/{asin}": {
        "summary": "Detailed product analytics",
        "tags": ["Dashboard"],
        "plan": "foundation",
        "auth": True,
    },

    # SourceScout
    "GET /api/v1/buy-list": {
        "summary": "Ranked buy list with margin analysis",
        "tags": ["SourceScout"],
        "plan": "scout",
        "auth": True,
    },
    "GET /api/v1/alerts": {
        "summary": "Active alerts (stockout, price war, crowding)",
        "tags": ["SourceScout"],
        "plan": "scout",
        "auth": True,
    },
    "POST /api/v1/sourcescout/enrich": {
        "summary": "Enrich product data from external providers",
        "tags": ["SourceScout"],
        "plan": "scout",
        "auth": True,
    },

    # ListingForge
    "POST /api/v1/listings/generate": {
        "summary": "Generate complete listing copy (title, bullets, description)",
        "tags": ["ListingForge"],
        "plan": "scout",
        "auth": True,
        "body": {"asin": "string", "keywords": ["string"], "brand_voice": "string"},
    },
    "POST /api/v1/listings/compliance-check": {
        "summary": "Check listing against Amazon TOS",
        "tags": ["ListingForge"],
        "plan": "scout",
        "auth": True,
    },
    "POST /api/v1/listings/rufus-score": {
        "summary": "Score listing for Rufus AI readiness",
        "tags": ["ListingForge"],
        "plan": "scout",
        "auth": True,
    },

    # AdPilot
    "POST /api/v1/ads/optimize-bids": {
        "summary": "Optimize PPC bids based on ACoS targets",
        "tags": ["AdPilot"],
        "plan": "mover",
        "auth": True,
    },
    "POST /api/v1/ads/negative-keywords": {
        "summary": "Detect and suggest negative keywords",
        "tags": ["AdPilot"],
        "plan": "mover",
        "auth": True,
    },
    "POST /api/v1/ads/campaign-structure": {
        "summary": "Generate four-tier campaign structure",
        "tags": ["AdPilot"],
        "plan": "mover",
        "auth": True,
    },
    "GET /api/v1/ads/keyword-lifecycle": {
        "summary": "Get keyword lifecycle stages and transitions",
        "tags": ["AdPilot"],
        "plan": "mover",
        "auth": True,
    },

    # SocialPulse
    "POST /api/v1/social/caption": {
        "summary": "Generate platform-specific caption",
        "tags": ["SocialPulse"],
        "plan": "mover",
        "auth": True,
    },
    "POST /api/v1/social/calendar": {
        "summary": "Generate 30-day content calendar",
        "tags": ["SocialPulse"],
        "plan": "mover",
        "auth": True,
    },
    "POST /api/v1/social/hashtags": {
        "summary": "Generate relevant hashtags for platform",
        "tags": ["SocialPulse"],
        "plan": "mover",
        "auth": True,
    },
    "POST /api/v1/social/attribution": {
        "summary": "Track social media attribution to Amazon",
        "tags": ["SocialPulse"],
        "plan": "mover",
        "auth": True,
    },

    # AutothinK
    "POST /api/v1/autothink/chat": {
        "summary": "Natural language AI workspace",
        "tags": ["AutothinK"],
        "plan": "autothink",
        "auth": True,
    },
    "POST /api/v1/autothink/orchestrate": {
        "summary": "Multi-agent orchestration",
        "tags": ["AutothinK"],
        "plan": "autothink",
        "auth": True,
    },

    # Memory
    "POST /api/v1/memory/ingest": {
        "summary": "Ingest knowledge into memory bank",
        "tags": ["Memory"],
        "plan": "scout",
        "auth": True,
    },
    "POST /api/v1/memory/search": {
        "summary": "Search memory bank by intent",
        "tags": ["Memory"],
        "plan": "scout",
        "auth": True,
    },

    # Health
    "GET /health": {
        "summary": "Basic health check",
        "tags": ["Health"],
        "plan": "foundation",
        "auth": False,
    },
    "GET /health/detailed": {
        "summary": "Detailed system health",
        "tags": ["Health"],
        "plan": "foundation",
        "auth": False,
    },
}
