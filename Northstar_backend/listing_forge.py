"""ListingForge — AI-powered listing copy generation engine.

Generates optimized Amazon product listings (title, bullets, description,
backend keywords, search terms) using local LLM (Ollama/qwen3:14b) or
fallback template-based generation.

Each generation produces scored output with compliance checking and
Rufus AI readiness assessment.
"""

import json
import os
import re
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Amazon listing limits
MAX_TITLE_LENGTH = 200
MAX_BULLET_LENGTH = 500
MAX_BULLETS = 5
MAX_DESCRIPTION_LENGTH = 2000
MAX_BACKEND_BYTES = 250
MAX_SEARCH_TERM_BYTES = 250

# Prohibited words (Amazon policy)
PROHIBITED_WORDS = [
    "best", "best seller", "#1", "number one", "guaranteed",
    "money back", "free", "100%", "amazing", "incredible",
    "miracle", "cure", "heal", "medical", "fda approved",
    "as seen on tv", "limited time", "act now", "don't miss",
]

# Compliance rules
COMPLIANCE_RULES = [
    {"name": "title_length", "check": lambda t: len(t) <= MAX_TITLE_LENGTH, "max": MAX_TITLE_LENGTH},
    {"name": "no_prohibited_words", "check": lambda t: not any(w in t.lower() for w in PROHIBITED_WORDS)},
    {"name": "brand_in_title", "check": lambda t, brand="": brand.lower() in t.lower() if brand else True},
    {"name": "bullet_count", "check": lambda b: 3 <= len(b) <= MAX_BULLETS},
    {"name": "bullet_length", "check": lambda b: all(len(x) <= MAX_BULLET_LENGTH for x in b)},
    {"name": "description_length", "check": lambda d: len(d) <= MAX_DESCRIPTION_LENGTH},
    {"name": "backend_bytes", "check": lambda b: len(" ".join(b).encode("utf-8")) <= MAX_BACKEND_BYTES},
]


def generate_title(
    product: Dict[str, Any],
    brand_voice: Optional[Dict] = None,
    top_keywords: Optional[List[str]] = None,
    competitor_titles: Optional[List[str]] = None,
    model: str = "northstar-qwen3:rev1",
) -> Dict[str, Any]:
    """Generate optimized product title.

    Returns:
        title: Generated title (≤200 chars)
        score: Quality score 0-100
        compliance: Compliance check results
        alternatives: Alternative title options
    """
    # Build prompt context
    context = _build_title_prompt(product, brand_voice, top_keywords, competitor_titles)
    prompt = context["prompt"]

    # Try LLM generation, fall back to template
    titles = []
    try:
        llm_titles = _call_llm(prompt, model=model, num_options=3)
        titles.extend(llm_titles)
    except Exception:
        pass

    # Template fallback
    template_title = _template_title(product, top_keywords)
    titles.insert(0, template_title)

    # Score and select best
    scored = []
    for title in titles[:3]:
        score = _score_title(title, product, top_keywords)
        compliance = _check_compliance_title(title, product.get("brand", ""))
        scored.append({
            "title": title[:MAX_TITLE_LENGTH],
            "score": score,
            "compliance": compliance,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    best = scored[0] if scored else {"title": template_title, "score": 50, "compliance": []}

    return {
        "title": best["title"],
        "score": best["score"],
        "compliance": best["compliance"],
        "alternatives": scored[1:],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_bullets(
    product: Dict[str, Any],
    brand_voice: Optional[Dict] = None,
    top_keywords: Optional[List[str]] = None,
    model: str = "northstar-qwen3:rev1",
) -> Dict[str, Any]:
    """Generate optimized bullet points (5 feature bullets ≤500 chars each).

    Returns:
        bullets: List of bullet point strings
        scores: Per-bullet quality scores
        overall_score: Composite score 0-100
        compliance: Compliance check results
    """
    prompt = _build_bullets_prompt(product, brand_voice, top_keywords)

    bullets = []
    try:
        llm_bullets = _call_llm(prompt, model=model, num_options=1)
        if llm_bullets:
            # Parse bullet points from LLM output
            parsed = _parse_bullets(llm_bullets[0])
            bullets.extend(parsed)
    except Exception:
        pass

    # Template fallback
    if len(bullets) < 3:
        bullets.extend(_template_bullets(product, top_keywords))

    # Ensure exactly 5 bullets
    bullets = bullets[:MAX_BULLETS]
    while len(bullets) < MAX_BULLETS:
        bullets.append(f"High-quality {product.get('category', 'product')} from {product.get('brand', 'trusted brand')}")

    # Score each bullet
    scores = [_score_bullet(b, product, top_keywords) for b in bullets]
    overall = sum(scores) / len(scores) if scores else 0
    compliance = _check_compliance_bullets(bullets)

    return {
        "bullets": bullets,
        "scores": scores,
        "overall_score": round(overall, 1),
        "compliance": compliance,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_description(
    product: Dict[str, Any],
    brand_voice: Optional[Dict] = None,
    model: str = "northstar-qwen3:rev1",
) -> Dict[str, Any]:
    """Generate product description (≤2000 chars)."""
    prompt = _build_description_prompt(product, brand_voice)

    description = ""
    try:
        result = _call_llm(prompt, model=model, num_options=1)
        if result:
            description = result[0][:MAX_DESCRIPTION_LENGTH]
    except Exception:
        pass

    if not description:
        description = _template_description(product)

    score = _score_description(description, product)
    compliance = len(description) <= MAX_DESCRIPTION_LENGTH

    return {
        "description": description,
        "score": score,
        "compliant": compliance,
        "length": len(description),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_backend_terms(
    product: Dict[str, Any],
    top_keywords: Optional[List[str]] = None,
    exclude_in_title: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate backend keyword terms (250-byte cap)."""
    exclude = set(exclude_in_title or [])

    # Collect candidate terms
    candidates = []
    if top_keywords:
        candidates.extend(top_keywords)

    # Add product attributes
    for field in ["brand", "category", "subcategory"]:
        val = product.get(field)
        if val and val not in exclude:
            candidates.append(val.lower())

    # Deduplicate and fit within 250 bytes
    selected = []
    byte_count = 0
    seen = set()
    for kw in candidates:
        kw_clean = kw.strip().lower()
        if kw_clean in seen or kw_clean in exclude:
            continue
        kw_bytes = len(kw_clean.encode("utf-8"))
        if byte_count + kw_bytes + 1 > MAX_BACKEND_BYTES:
            break
        selected.append(kw_clean)
        seen.add(kw_clean)
        byte_count += kw_bytes + 1  # +1 for space separator

    return {
        "backend_terms": selected,
        "byte_count": byte_count,
        "max_bytes": MAX_BACKEND_BYTES,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_search_terms(
    product: Dict[str, Any],
    top_keywords: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate hidden search terms (250-byte cap)."""
    exclude_words = {
        (product.get("brand") or "").lower(),
        "kirkland", "signature",
    }

    candidates = []
    if top_keywords:
        candidates.extend(top_keywords)

    # Add category terms
    cat = (product.get("category") or "").lower()
    if cat:
        candidates.extend(cat.split())

    selected = []
    byte_count = 0
    seen = set()
    for kw in candidates:
        kw_clean = kw.strip().lower()
        if kw_clean in seen or kw_clean in exclude_words or len(kw_clean) < 2:
            continue
        kw_bytes = len(kw_clean.encode("utf-8"))
        if byte_count + kw_bytes + 1 > MAX_SEARCH_TERM_BYTES:
            break
        selected.append(kw_clean)
        seen.add(kw_clean)
        byte_count += kw_bytes + 1

    return {
        "search_terms": " ".join(selected),
        "byte_count": byte_count,
        "max_bytes": MAX_SEARCH_TERM_BYTES,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_title(title: str, product: Dict, keywords: Optional[List[str]] = None) -> float:
    """Score a title 0-100."""
    score = 60  # base
    if len(title) <= MAX_TITLE_LENGTH:
        score += 10
    if keywords and any(kw.lower() in title.lower() for kw in keywords[:3]):
        score += 15
    brand = (product.get("brand") or "").lower()
    if brand and brand in title.lower():
        score += 10
    if not any(w in title.lower() for w in PROHIBITED_WORDS):
        score += 5
    return min(100, score)


def _score_bullet(bullet: str, product: Dict, keywords: Optional[List[str]] = None) -> float:
    score = 50
    if len(bullet) <= MAX_BULLET_LENGTH:
        score += 15
    if keywords and any(kw.lower() in bullet.lower() for kw in keywords):
        score += 15
    if bullet[0].isupper():
        score += 5
    if bullet.strip().endswith("."):
        score += 5
    return min(100, score)


def _score_description(description: str, product: Dict) -> float:
    score = 50
    if len(description) <= MAX_DESCRIPTION_LENGTH:
        score += 20
    if len(description) > 100:
        score += 15
    if product.get("brand", "").lower() in description.lower():
        score += 10
    return min(100, score)


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------

def _check_compliance_title(title: str, brand: str) -> List[Dict]:
    violations = []
    if len(title) > MAX_TITLE_LENGTH:
        violations.append({"rule": "title_length", "issue": f"Title is {len(title)} chars (max {MAX_TITLE_LENGTH})"})
    prohibited_found = [w for w in PROHIBITED_WORDS if w in title.lower()]
    if prohibited_found:
        violations.append({"rule": "prohibited_words", "issue": f"Contains: {', '.join(prohibited_found)}"})
    return violations


def _check_compliance_bullets(bullets: List[str]) -> List[Dict]:
    violations = []
    if len(bullets) > MAX_BULLETS:
        violations.append({"rule": "bullet_count", "issue": f"Too many bullets: {len(bullets)}"})
    for i, b in enumerate(bullets):
        if len(b) > MAX_BULLET_LENGTH:
            violations.append({"rule": "bullet_length", "issue": f"Bullet {i+1} is {len(b)} chars"})
    return violations


# ---------------------------------------------------------------------------
# Template fallbacks
# ---------------------------------------------------------------------------

def _template_title(product: Dict, keywords: Optional[List[str]] = None) -> str:
    brand = product.get("brand", "")
    name = product.get("title") or product.get("name", "Product")
    kw_part = ""
    if keywords and len(keywords) > 0:
        kw_part = f" - {keywords[0]}"
    title = f"{brand} {name}{kw_part}"
    return title[:MAX_TITLE_LENGTH]


def _template_bullets(product: Dict, keywords: Optional[List[str]] = None) -> List[str]:
    name = product.get("title") or product.get("name", "this product")
    brand = product.get("brand", "Kirkland Signature")
    return [
        f"PREMIUM QUALITY: {name} from {brand}, made with care and attention to detail",
        f"TRUSTED BRAND: {brand} is known for delivering exceptional value and quality",
        f"GREAT VALUE: Get premium quality at a fraction of the cost of leading brands",
        f"VERSATILE: Perfect for everyday use, home, office, or on-the-go",
        f"SATISFACTION GUARANTEED: Buy with confidence from {brand}",
    ]


def _template_description(product: Dict) -> str:
    name = product.get("title") or product.get("name", "Product")
    brand = product.get("brand", "Kirkland Signature")
    return (
        f"Discover the quality and value of {name} from {brand}. "
        f"Designed for performance and built to last, this product delivers "
        f"exceptional results every time. Trusted by millions of customers worldwide."
    )[:MAX_DESCRIPTION_LENGTH]


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_title_prompt(product: Dict, brand_voice: Optional[Dict],
                        top_keywords: Optional[List[str]],
                        competitor_titles: Optional[List[str]]) -> Dict:
    parts = [
        "You are a world-class Amazon listing copywriter.",
        f"Product: {product.get('title') or product.get('name', 'Unknown')}",
        f"Brand: {product.get('brand', 'Unknown')}",
        f"Category: {product.get('category', 'Unknown')}",
    ]
    if top_keywords:
        parts.append(f"Top keywords: {', '.join(top_keywords[:10])}")
    if competitor_titles:
        parts.append(f"Competitor titles: {'; '.join(competitor_titles[:3])}")
    if brand_voice:
        parts.append(f"Brand voice: {json.dumps(brand_voice)}")
    parts.append(f"Rules: Max {MAX_TITLE_LENGTH} chars. Lead with most important keyword. Include brand name. No prohibited words.")
    parts.append("Generate 3 title options, one per line.")
    return {"prompt": "\n".join(parts), "context": product}


def _build_bullets_prompt(product: Dict, brand_voice: Optional[Dict],
                          top_keywords: Optional[List[str]]) -> str:
    parts = [
        "Generate 5 Amazon bullet points for this product:",
        f"Product: {product.get('title') or product.get('name', 'Unknown')}",
        f"Brand: {product.get('brand', 'Unknown')}",
        f"Category: {product.get('category', 'Unknown')}",
    ]
    if top_keywords:
        parts.append(f"Keywords: {', '.join(top_keywords[:5])}")
    parts.append(f"Rules: Each bullet max {MAX_BULLET_LENGTH} chars. Start with CAPS keyword. Be specific and benefit-focused.")
    return "\n".join(parts)


def _build_description_prompt(product: Dict, brand_voice: Optional[Dict]) -> str:
    parts = [
        "Generate an Amazon product description:",
        f"Product: {product.get('title') or product.get('name', 'Unknown')}",
        f"Brand: {product.get('brand', 'Unknown')}",
        f"Max {MAX_DESCRIPTION_LENGTH} characters.",
        "Be compelling, specific, and benefit-focused.",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# LLM integration
# ---------------------------------------------------------------------------

def _call_llm(prompt: str, model: str = "northstar-qwen3:rev1",
              num_options: int = 1) -> List[str]:
    """Call local Ollama LLM for generation."""
    import httpx
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    try:
        resp = httpx.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 500},
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return lines[:num_options]
    except Exception:
        return []


def _parse_bullets(llm_output: str) -> List[str]:
    """Parse bullet points from LLM output."""
    bullets = []
    for line in llm_output.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove bullet prefixes
        for prefix in ["•", "-", "●", "* ", "1.", "2.", "3.", "4.", "5."]:
            if line.startswith(prefix):
                line = line[len(prefix):].strip()
                break
        if line and len(line) > 10:
            bullets.append(line[:MAX_BULLET_LENGTH])
    return bullets[:MAX_BULLETS]
