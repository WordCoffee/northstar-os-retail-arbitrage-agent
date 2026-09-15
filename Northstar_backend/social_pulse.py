"""SocialPulse — Brand-aware social media content generation.

Creates platform-specific social media posts, captions, hashtags,
ad creatives, and email content. All content matches the brand's
voice and is optimized for each platform.

Supported platforms:
- Instagram (image captions, stories, reels scripts)
- Facebook (posts, event descriptions)
- TikTok (video scripts, captions)
- Twitter/X (short-form posts)
- Email (review requests, marketing)
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Brand Voice Profiles
# ---------------------------------------------------------------------------

_DEFAULT_VOICE = {
    "tone": "professional",
    "style": "friendly",
    "hashtags_per_post": 10,
    "emoji_usage": "moderate",
    "call_to_action": True,
}


def load_brand_voice(brand: str) -> Dict[str, Any]:
    """Load brand voice profile from memory or return defaults."""
    try:
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from data_layer import get_db
        db = get_db()
        cur = db.execute(
            "SELECT content FROM memory_entries WHERE entry_type = 'brand_voice' AND tags LIKE ?",
            (f"%{brand}%",),
        )
        row = cur.fetchone()
        if row:
            return json.loads(row["content"])
    except Exception:
        pass
    return {**_DEFAULT_VOICE, "brand": brand}


# ---------------------------------------------------------------------------
# Caption Generation
# ---------------------------------------------------------------------------

def generate_caption(
    product: Dict[str, Any],
    platform: str = "instagram",
    brand: str = "Kirkland Signature",
    angle: str = "quality",
    voice: Optional[Dict] = None,
    model: str = "northstar-qwen3:rev1",
) -> Dict[str, Any]:
    """Generate a social media caption for a product.

    Args:
        product: Product data dict (title, brand, price, category, etc.)
        platform: Target platform (instagram, facebook, tiktok, twitter)
        brand: Brand name
        angle: Content angle (quality, value, lifestyle, seasonal, gift)
        voice: Brand voice profile override
        model: LLM model to use

    Returns:
        caption, hashtags, cta, platform_spec, score
    """
    voice = voice or load_brand_voice(brand)

    # Build prompt
    platform_specs = _get_platform_spec(platform)
    prompt = _build_caption_prompt(product, platform, brand, angle, voice, platform_specs)

    # Try LLM
    caption = ""
    try:
        import httpx
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        resp = httpx.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.8, "num_predict": 300},
            },
            timeout=30,
        )
        resp.raise_for_status()
        caption = resp.json().get("response", "").strip()
    except Exception:
        pass

    # Template fallback
    if not caption or len(caption) < 20:
        caption = _template_caption(product, platform, angle, brand)

    # Enforce platform limits
    caption = caption[:platform_specs["max_caption_length"]]

    # Generate hashtags
    hashtags = _generate_hashtags(product, platform, brand, voice.get("hashtags_per_post", 10))

    # CTA
    cta = _get_cta(platform, angle)

    score = _score_caption(caption, platform, hashtags, voice)

    return {
        "caption": caption,
        "hashtags": hashtags,
        "cta": cta,
        "platform": platform,
        "platform_spec": platform_specs,
        "angle": angle,
        "score": score,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_content_calendar(
    products: List[Dict[str, Any]],
    brand: str = "Kirkland Signature",
    days: int = 7,
    platforms: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Generate a weekly content calendar.

    Returns a list of scheduled posts across platforms and products.
    """
    platforms = platforms or ["instagram", "facebook", "tiktok"]
    angles = ["quality", "value", "lifestyle", "seasonal", "gift"]
    calendar = []

    start_date = datetime.now(timezone.utc).date()
    post_times = {
        "instagram": "11:00",
        "facebook": "13:00",
        "tiktok": "19:00",
        "twitter": "09:00",
    }

    for day_offset in range(days):
        date = start_date + timedelta(days=day_offset)
        # 2-3 posts per day
        posts_today = min(3, len(products))
        for post_idx in range(posts_today):
            product = products[post_idx % len(products)]
            platform = platforms[post_idx % len(platforms)]
            angle = angles[(day_offset + post_idx) % len(angles)]

            content = generate_caption(
                product=product,
                platform=platform,
                brand=brand,
                angle=angle,
            )

            calendar.append({
                "date": date.isoformat(),
                "time": post_times.get(platform, "12:00"),
                "platform": platform,
                "product_asin": product.get("asin"),
                "product_title": product.get("title"),
                "angle": angle,
                "caption": content["caption"],
                "hashtags": content["hashtags"],
                "cta": content["cta"],
                "status": "draft",
            })

    return calendar


# ---------------------------------------------------------------------------
# Email Generation
# ---------------------------------------------------------------------------

def generate_review_request_email(
    product: Dict[str, Any],
    brand: str = "Kirkland Signature",
    tone: str = "friendly",
) -> Dict[str, Any]:
    """Generate an Amazon-compliant review request email.

    Must comply with Amazon TOS — no incentivized reviews,
    no external links, no discount offers.
    """
    name = product.get("title", "your recent purchase")

    if tone == "friendly":
        subject = f"How was your {name}?"
        body = (
            f"Hi there!\n\n"
            f"We hope you're enjoying your {name}. "
            f"We'd love to hear about your experience — your feedback helps us "
            f"continue to deliver the best products.\n\n"
            f"If you have a moment, we'd appreciate you sharing your thoughts "
            f"by leaving a review on Amazon.\n\n"
            f"Thank you for choosing {brand}!\n\n"
            f"Best regards,\n{brand} Team"
        )
    else:
        subject = f"Your feedback matters — {name}"
        body = (
            f"Dear Customer,\n\n"
            f"Thank you for purchasing {name} from {brand}. "
            f"Your opinion is valuable to us and helps other customers "
            f"make informed decisions.\n\n"
            f"We invite you to share your experience by leaving a product "
            f"review on Amazon.\n\n"
            f"We appreciate your time and trust in {brand}.\n\n"
            f"Sincerely,\n{brand} Team"
        )

    return {
        "subject": subject,
        "body": body,
        "tone": tone,
        "compliant": True,  # no external links, no incentives
        "platform": "email",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Influencer Outreach
# ---------------------------------------------------------------------------

def generate_influencer_outreach(
    product: Dict[str, Any],
    influencer_name: str,
    platform: str = "instagram",
    brand: str = "Kirkland Signature",
) -> Dict[str, Any]:
    """Generate an influencer outreach message."""
    name = product.get("title", "our product")

    if platform == "instagram":
        message = (
            f"Hi {influencer_name}! 👋\n\n"
            f"We love your content and think {name} from {brand} would be "
            f"a great fit for your audience. We'd love to send you the product "
            f"to try — no strings attached. If you enjoy it, we'd be thrilled "
            f"if you shared your honest experience with your followers.\n\n"
            f"Interested? We'd be happy to send details!\n\n"
            f"Best,\nThe {brand} Team"
        )
    else:
        message = (
            f"Hi {influencer_name},\n\n"
            f"I'm reaching out from {brand}. We think {name} would resonate "
            f"with your audience. We'd love to send you the product for an "
            f"honest review or feature.\n\n"
            f"Let us know if you're interested!\n\n"
            f"Best regards,\nThe {brand} Team"
        )

    return {
        "to": influencer_name,
        "platform": platform,
        "message": message,
        "product": name,
        "brand": brand,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_platform_spec(platform: str) -> Dict[str, Any]:
    specs = {
        "instagram": {"max_caption_length": 2200, "max_hashtags": 30, "aspect_ratio": "1:1"},
        "facebook": {"max_caption_length": 63206, "max_hashtags": 5, "aspect_ratio": "16:9"},
        "tiktok": {"max_caption_length": 300, "max_hashtags": 5, "aspect_ratio": "9:16"},
        "twitter": {"max_caption_length": 280, "max_hashtags": 3, "aspect_ratio": "16:9"},
    }
    return specs.get(platform, specs["instagram"])


def _build_caption_prompt(product, platform, brand, angle, voice, spec):
    return (
        f"Write a {platform} post for {brand}.\n"
        f"Product: {product.get('title', 'Unknown')}\n"
        f"Angle: {angle}\n"
        f"Tone: {voice.get('tone', 'professional')}\n"
        f"Max {spec['max_caption_length']} characters.\n"
        f"Include a call to action. Be authentic and engaging."
    )


def _template_caption(product, platform, angle, brand):
    title = product.get("title", "this product")
    templates = {
        "quality": f"Quality you can trust. {title} from {brand} delivers every time. 🌟 #QualityMatters",
        "value": f"Premium quality, honest price. That's the {brand} promise with {title}. 💪 #ValuePicks",
        "lifestyle": f"Elevate your everyday with {title} from {brand}. Made for moments that matter. ✨",
        "seasonal": f"Season favorites from {brand}! Have you tried {title}? Perfect for any time of year. 🎉",
        "gift": f"Looking for the perfect gift? {title} from {brand} always delivers a smile. 🎁",
    }
    caption = templates.get(angle, templates["quality"])
    if platform == "twitter":
        caption = caption[:280]
    return caption


def _generate_hashtags(product, platform, brand, count):
    brand_tag = brand.replace(" ", "").replace(".", "")
    base_tags = [brand_tag, "KirklandSignature", "QualityValue", "AmazonFinds"]
    category = product.get("category", "")
    if category:
        base_tags.append(category.replace(" & ", "").replace(" ", ""))
    base_tags.extend(["ShopSmart", "HomeEssentials", "TopPicks", "MustHaves", "DailyDeals"])
    return [f"#{tag}" for tag in base_tags[:count]]


def _get_cta(platform, angle):
    ctas = {
        "instagram": "Link in bio 👆",
        "facebook": "Shop now on Amazon",
        "tiktok": "Link in bio!",
        "twitter": "Shop: amzn.to/link",
    }
    return ctas.get(platform, "Learn more")


def _score_caption(caption, platform, hashtags, voice):
    score = 50
    spec = _get_platform_spec(platform)
    if len(caption) <= spec["max_caption_length"]:
        score += 15
    if len(hashtags) > 0:
        score += 10
    if any(emoji in caption for emoji in ["🌟", "💪", "✨", "🎉", "🎁", "❤️", "👍"]):
        score += 5
    if "shop" in caption.lower() or "link" in caption.lower():
        score += 10
    if len(caption) > 50:
        score += 10
    return min(100, score)
