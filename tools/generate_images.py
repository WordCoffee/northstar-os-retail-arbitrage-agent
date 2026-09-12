"""
Northstar Image Generator v2 — Multi-Backend
==============================================
FREE image generation with multiple backends:
  - pollinations  : Pollinations.ai (zero-config, no API key)
  - cloudflare    : Cloudflare Workers AI (free tier, 100k/day, needs deploy)
  - huggingface   : Hugging Face Inference API (free tier, needs token)
  - local         : Local ComfyUI / diffusers (best quality, your GPU)

Usage:
    python tools/generate_images.py                                    # List concepts
    python tools/generate_images.py --concept analysts-desk            # Generate one concept
    python tools/generate_images.py --backend cloudflare --concept ... # Use specific backend
    python tools/generate_images.py --prompt "..." --filename out.jpg  # Custom prompt
    python tools/generate_images.py --backend local --concept ...      # Use local GPU
    python tools/generate_images.py --list-backends                    # Show available backends

Environment:
    CLOUDFLARE_ACCOUNT_ID  : Your Cloudflare account ID
    CLOUDFLARE_API_TOKEN   : Your Cloudflare Workers AI API token
    HF_TOKEN               : Your Hugging Face API token
    COMFYUI_URL            : ComfyUI server URL (default: http://127.0.0.1:8188)
"""

import os
import sys
import time
import json
import base64
import hashlib
import argparse
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_DIR = Path(__file__).parent.parent / "generated_images"

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_MODEL = "flux"

# Retry config
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds between retries


# ============================================================
# BACKEND REGISTRY
# ============================================================

BACKENDS = {}


def register_backend(name):
    """Decorator to register a generation backend."""
    def decorator(cls):
        BACKENDS[name] = cls
        return cls
    return decorator


# ============================================================
# DESIGN CONCEPT PROMPTS
# ============================================================

DESIGN_CONCEPTS = {
    # ---- NORTH STAR OS ----
    "analysts-desk": {
        "name": "North Star OS — The Analyst's Desk",
        "category": "northstar-os",
        "prompt": (
            "A high-fidelity UI design of a neo-skeuomorphic Amazon seller dashboard "
            "called 'North Star OS: The Analyst's Desk'. The screen looks like a dark "
            "wooden desk with a leather desk pad. The UI features a vertical sidebar "
            "that looks like a 'Drawer' with leather-bound 'Notebooks' for navigation. "
            "The main area is a high-density data table where each row is a physical "
            "'Index Card' with a drop shadow. On the right, a 'Bulletin Board' with "
            "digital sticky notes pinned to it. High-fidelity metal knobs for settings. "
            "A 3D paperclip assistant sits on the edge of the screen. The vibe is "
            "'premium craftsman' meets 'high-tech'. 8k, hyper-detailed, Dribbble style, "
            "high contrast, professional UI design mockup."
        ),
    },
    "living-dashboard": {
        "name": "North Star OS — The Living Dashboard",
        "category": "northstar-os",
        "prompt": (
            "A high-fidelity UI design of a minimalist, glassmorphism Amazon seller "
            "dashboard called 'North Star OS: The Living Dashboard'. The screen is a "
            "deep navy gradient. The UI features semi-transparent 'frosted glass' cards "
            "that seem to float in 3D space. In the center, a large 'Pulsing' profit "
            "number. Surrounding it are 'Floating Bubbles' representing KPIs (Sales, "
            "Units, Reviews). A glass 'Action Dock' at the bottom. A toggle button "
            "that 'explodes' the view into a 3D topographical map of Amazon niches. "
            "Clean, airy, futuristic, Apple-inspired, 8k, high contrast, neon accents, "
            "professional UI design mockup."
        ),
    },
    # ---- NORTH STAR AUTOTHINK ----
    "spatial-canvas": {
        "name": "North Star AutoThink — The Spatial Canvas",
        "category": "northstar-autothink",
        "prompt": (
            "A high-fidelity UI of a futuristic 3D web interface for an AI coding tool "
            "called 'North Star AutoThink: Spatial Canvas'. The screen shows a dark "
            "'space' environment where project files and tasks are 'floating nodes' "
            "connected by glowing neon lines. The nodes are 3D cubes that glow blue "
            "when active. A 'Cockpit' style sidebar with translucent glass panels floats "
            "on the left. The user 'navigates' through a 3D project. Cinematic lighting, "
            "8k, 'Ready Player One' aesthetic, high-tech but clean, professional UI "
            "design mockup."
        ),
    },
    "architects-studio": {
        "name": "North Star AutoThink — The AI Architect's Studio",
        "category": "northstar-autothink",
        "prompt": (
            "A high-fidelity UI for an AI coding assistant called 'North Star AutoThink: "
            "Architect's Studio'. The screen looks like a high-tech architect's drafting "
            "table. The background is a 'Blueprint' grid. The AI's code and plans look "
            "like 'ink sketches' and 'handwritten notes' on the side. A sidebar of "
            "'Drafting Tools' (ruler, compass, pen) allows the user to direct the AI. "
            "A 3D paperclip assistant sits on the edge. The vibe is 'Master Craftsman' "
            "meets 'Cyberpunk'. 8k, hyper-detailed, beautiful lighting, professional "
            "UI design mockup."
        ),
    },
    # ---- BRAND / LOGO (5 CONCEPTS) ----
    "logo-compass-diamond": {
        "name": "North Star Logo — Compass Diamond",
        "category": "branding",
        "prompt": (
            "A modern logo icon for a tech company. A sleek, geometric compass needle "
            "pointing upward, enclosed in a thin diamond/rhombus outline. The needle "
            "is a sharp elongated triangle split vertically — left half white, right "
            "half electric blue. The diamond frame has rounded corners and a subtle "
            "glow. Dark charcoal background. Minimal, flat design with one accent "
            "color. Think Stripe or Linear logo quality. Vector style, clean edges, "
            "no text, icon only, 8k resolution, professional brand identity."
        ),
    },
    "logo-pathway-nodes": {
        "name": "North Star Logo — Pathway Nodes",
        "category": "branding",
        "prompt": (
            "A modern abstract logo icon for a tech company. Five small circles "
            "(nodes) connected by thin glowing lines forming an upward-angled path "
            "from bottom-left to top-right. The final top-right node is slightly "
            "larger and pulses with a soft white glow. The connecting lines gradient "
            "from dim gray to bright electric blue. Dark background. Represents "
            "data-driven direction and navigation. Minimalist, geometric, no text, "
            "icon only. Think Figma or Notion logo quality. 8k, vector style, "
            "professional brand identity."
        ),
    },
    "logo-beacon-tower": {
        "name": "North Star Logo — Beacon Tower",
        "category": "branding",
        "prompt": (
            "A modern logo icon for a tech company. A stylized lighthouse beam seen "
            "from above — three concentric arcs radiating upward from a small solid "
            "circle at the bottom center. The arcs are thin, clean lines in electric "
            "blue that fade from bright near the center to faint at the edges. The "
            "small circle is bright white. Dark background. Represents a guiding "
            "signal. Minimal, elegant, no text, icon only. Think Vercel or Supabase "
            "logo quality. 8k, vector style, sharp edges, professional brand identity."
        ),
    },
    "logo-peak-summit": {
        "name": "North Star Logo — Peak Summit",
        "category": "branding",
        "prompt": (
            "A modern logo icon for a tech company. A single clean geometric mountain "
            "peak silhouette made of two overlapping triangles — a larger dark blue "
            "triangle behind a smaller white triangle in front, creating a layered "
            "depth effect. At the very peak of the white triangle, a small bright "
            "glowing dot. Dark charcoal background. Represents reaching the top. "
            "Minimal, flat geometric style, no text, icon only. Think Atlas or Peak "
            "branding quality. 8k, vector style, professional brand identity."
        ),
    },
    "logo-monogram-n": {
        "name": "North Star Logo — Monogram N",
        "category": "branding",
        "prompt": (
            "A modern monogram logo for a tech company. A bold letter 'N' constructed "
            "from two vertical bars and a diagonal — but the diagonal stroke extends "
            "beyond the right vertical bar into a sharp upward-pointing arrow tip, "
            "suggesting upward momentum. The letterform is white, the arrow tip "
            "glows electric blue. Dark background. Think the letter N is carved from "
            "a single geometric shape. Minimal, sharp, confident, no text, icon only. "
            "8k, vector style, professional brand identity."
        ),
    },
    # ---- LANDING PAGE / MARKETING ----
    "os-landing-hero": {
        "name": "North Star OS — Landing Page Hero",
        "category": "marketing",
        "prompt": (
            "A cinematic hero section for a SaaS product landing page. A floating "
            "glassmorphism dashboard with Amazon FBA profit data, sales charts, and "
            "inventory metrics floats in a dark space environment with subtle star "
            "particles. A glowing 8-pointed star logo hovers above. Text reads "
            "'North Star OS'. Professional web design, 4k, clean, modern, "
            "high contrast."
        ),
    },
    "autothink-landing-hero": {
        "name": "North Star AutoThink — Landing Page Hero",
        "category": "marketing",
        "prompt": (
            "A cinematic hero section for an AI coding assistant landing page. "
            "A holographic 3D workspace showing code nodes connected by glowing "
            "neon lines floats in dark space. An AI robot assistant hovers near "
            "a code editor. Text reads 'North Star AutoThink'. Professional web "
            "design, 4k, futuristic, clean, high contrast."
        ),
    },
}


# ============================================================
# BACKEND: POLLINATIONS.AI (free, no key)
# ============================================================

@register_backend("pollinations")
class PollinationsBackend:
    """Free, no API key required. Uses base Flux model."""

    BASE_URL = "https://image.pollinations.ai/prompt"

    @staticmethod
    def is_available():
        return True  # Always available

    @staticmethod
    def info():
        return {
            "name": "Pollinations.ai",
            "cost": "Free (unlimited)",
            "models": ["flux", "turbo"],
            "requires_key": False,
            "quality": "Good — best for UI mockups, logos",
            "best_for": "Quick generation, no setup needed",
        }

    @staticmethod
    def generate(prompt, output_path, width=1280, height=720, model="flux",
                 seed=None, nologo=True, verbose=True):
        encoded_prompt = urllib.parse.quote(prompt)
        params = {
            "width": width,
            "height": height,
            "model": model,
            "nologo": str(nologo).lower(),
        }
        if seed is not None:
            params["seed"] = seed

        query = urllib.parse.urlencode(params)
        url = f"{PollinationsBackend.BASE_URL}/{encoded_prompt}?{query}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if verbose:
                    print(f"  [Pollinations] Attempt {attempt}/{MAX_RETRIES}...")

                req = urllib.request.Request(url, headers={
                    "User-Agent": "NorthstarOS-ImageGen/2.0",
                    "Accept": "image/*",
                })

                with urllib.request.urlopen(req, timeout=120) as response:
                    data = response.read()

                    if len(data) < 1000:
                        if verbose:
                            print(f"  [Warning] Response too small ({len(data)} bytes)")
                        time.sleep(RETRY_DELAY)
                        continue

                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(data)

                    if verbose:
                        print(f"  [Success] {len(data)/1024:.1f} KB -> {output_path.name}")
                    return True

            except (urllib.error.HTTPError, urllib.error.URLError) as e:
                if verbose:
                    print(f"  [Error] {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
            except Exception as e:
                if verbose:
                    print(f"  [Error] {type(e).__name__}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)

        if verbose:
            print(f"  [Failed] All {MAX_RETRIES} attempts failed.")
        return False


# ============================================================
# BACKEND: CLOUDFLARE WORKERS AI (free tier, 100k/day)
# ============================================================

@register_backend("cloudflare")
class CloudflareBackend:
    """Cloudflare Workers AI — 100,000 free requests/day.
    Requires: CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in env.
    """

    MODELS = {
        "flux-schnell": "@cf/black-forest-labs/flux-1-schnell",
        "sdxl": "@cf/stabilityai/stable-diffusion-xl-base-1.0",
        "sdxl-lightning": "@cf/bytedance/stable-diffusion-xl-lightning",
        "dreamshaper": "@cf/lykon/dreamshaper-8-lcm",
    }

    @staticmethod
    def is_available():
        return bool(os.environ.get("CLOUDFLARE_ACCOUNT_ID") and
                    os.environ.get("CLOUDFLARE_API_TOKEN"))

    @staticmethod
    def info():
        account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "NOT SET")
        return {
            "name": "Cloudflare Workers AI",
            "cost": "Free tier: 100,000 requests/day",
            "models": list(CloudflareBackend.MODELS.keys()),
            "requires_key": True,
            "key_env_vars": ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"],
            "account_id": account[:8] + "..." if len(account) > 8 else account,
            "quality": "Very Good — Flux Schnell is fast + clean, SDXL strong for people",
            "best_for": "Daily use, high volume, multiple model choices",
        }

    @staticmethod
    def generate(prompt, output_path, width=1024, height=1024,
                 model="flux-schnell", verbose=True):
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        api_token = os.environ.get("CLOUDFLARE_API_TOKEN")

        if not account_id or not api_token:
            if verbose:
                print("  [Error] Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN")
            return False

        cf_model = CloudflareBackend.MODELS.get(model, CloudflareBackend.MODELS["flux-schnell"])

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{cf_model}"

        payload = json.dumps({
            "prompt": prompt,
            "width": width,
            "height": height,
            "seed": int(time.time()) % 100000,
        }).encode("utf-8")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if verbose:
                    print(f"  [Cloudflare:{model}] Attempt {attempt}/{MAX_RETRIES}...")

                req = urllib.request.Request(url, data=payload, headers={
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                })

                with urllib.request.urlopen(req, timeout=120) as response:
                    result = json.loads(response.read().decode("utf-8"))

                    if not result.get("success"):
                        error_msg = result.get("errors", [{"message": "Unknown error"}])
                        if verbose:
                            print(f"  [Error] {error_msg}")
                        time.sleep(RETRY_DELAY)
                        continue

                    # Cloudflare returns base64-encoded image
                    image_b64 = result["result"]["image"]
                    image_data = base64.b64decode(image_b64)

                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(image_data)

                    if verbose:
                        print(f"  [Success] {len(image_data)/1024:.1f} KB -> {output_path.name}")
                    return True

            except (urllib.error.HTTPError, urllib.error.URLError) as e:
                if verbose:
                    print(f"  [Error] {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
            except Exception as e:
                if verbose:
                    print(f"  [Error] {type(e).__name__}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)

        if verbose:
            print(f"  [Failed] All {MAX_RETRIES} attempts failed.")
        return False


# ============================================================
# BACKEND: HUGGING FACE (free tier with token)
# ============================================================

@register_backend("huggingface")
class HuggingFaceBackend:
    """Hugging Face Inference API — free tier with HF_TOKEN.
    Access to FLUX.1 Dev, SD3.5, and more.
    """

    MODELS = {
        "flux-dev": "black-forest-labs/FLUX.1-dev",
        "sd3.5": "stabilityai/stable-diffusion-3.5-large",
        "sdxl": "stabilityai/stable-diffusion-xl-base-1.0",
    }

    @staticmethod
    def is_available():
        return bool(os.environ.get("HF_TOKEN"))

    @staticmethod
    def info():
        token = os.environ.get("HF_TOKEN", "NOT SET")
        return {
            "name": "Hugging Face Inference API",
            "cost": "Free tier (monthly credits)",
            "models": list(HuggingFaceBackend.MODELS.keys()),
            "requires_key": True,
            "key_env_vars": ["HF_TOKEN"],
            "token_status": "SET" if token and token != "NOT SET" else "NOT SET",
            "quality": "Excellent — FLUX.1 Dev is the open-weight quality king",
            "best_for": "Highest quality free generation, photorealism",
        }

    @staticmethod
    def generate(prompt, output_path, width=1024, height=1024,
                 model="flux-dev", verbose=True):
        token = os.environ.get("HF_TOKEN")
        if not token:
            if verbose:
                print("  [Error] Missing HF_TOKEN env var")
            return False

        hf_model = HuggingFaceBackend.MODELS.get(model, HuggingFaceBackend.MODELS["flux-dev"])

        url = f"https://api-inference.huggingface.co/models/{hf_model}"

        payload = json.dumps({
            "inputs": prompt,
            "parameters": {
                "width": width,
                "height": height,
            }
        }).encode("utf-8")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if verbose:
                    print(f"  [HuggingFace:{model}] Attempt {attempt}/{MAX_RETRIES}...")

                req = urllib.request.Request(url, data=payload, headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "image/png",
                })

                with urllib.request.urlopen(req, timeout=180) as response:
                    content_type = response.headers.get("Content-Type", "")

                    if "application/json" in content_type:
                        # Model is loading — HF returns JSON status
                        status = json.loads(response.read().decode("utf-8"))
                        if verbose:
                            estimated = status.get("estimated_time", "unknown")
                            print(f"  [Info] Model loading... ETA: {estimated:.0f}s")
                        # Wait and retry
                        wait_time = min(estimated + 5, 120) if isinstance(estimated, (int, float)) else 30
                        time.sleep(wait_time)
                        continue

                    # Got image data
                    data = response.read()
                    if len(data) < 1000:
                        if verbose:
                            print(f"  [Warning] Response too small ({len(data)} bytes)")
                        time.sleep(RETRY_DELAY)
                        continue

                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(data)

                    if verbose:
                        print(f"  [Success] {len(data)/1024:.1f} KB -> {output_path.name}")
                    return True

            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", errors="replace")[:200]
                except:
                    pass
                if verbose:
                    print(f"  [Error] HTTP {e.code}: {body}")
                if e.code == 503:
                    # Model loading — wait and retry
                    if verbose:
                        print("  [Info] Model loading, waiting 30s...")
                    time.sleep(30)
                elif attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
            except (urllib.error.URLError, Exception) as e:
                if verbose:
                    print(f"  [Error] {type(e).__name__}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)

        if verbose:
            print(f"  [Failed] All {MAX_RETRIES} attempts failed.")
        return False


# ============================================================
# BACKEND: LOCAL (ComfyUI or diffusers)
# ============================================================

@register_backend("local")
class LocalBackend:
    """Local generation via ComfyUI server.
    Best quality — runs on your GPU.
    Requires ComfyUI running at COMFYUI_URL (default: http://127.0.0.1:8188).
    """

    @staticmethod
    def is_available():
        comfyui_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
        try:
            req = urllib.request.Request(f"{comfyui_url}/system_stats",
                                         headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except:
            return False

    @staticmethod
    def info():
        comfyui_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
        status = "Connected" if LocalBackend.is_available() else "Not running"
        return {
            "name": "Local (ComfyUI)",
            "cost": "Free (runs on your GPU)",
            "models": ["Whatever is loaded in ComfyUI"],
            "requires_key": False,
            "requires_running": "ComfyUI server",
            "comfyui_url": comfyui_url,
            "status": status,
            "quality": "Best — full GPU power, FLUX Dev / HiDream / SDXL",
            "best_for": "Maximum quality, unlimited generations, privacy",
            "recommended_models_for_16gb": [
                "FLUX.1 Dev FP8 (~12GB VRAM) — best balance of quality/speed",
                "FLUX.2 Klein 4B FP16 (~13GB) — fastest, Apache 2.0 licensed",
                "HiDream-I1-Fast NF4 (~14GB) — best for photorealistic people",
                "SDXL — well-established, huge LoRA ecosystem",
            ],
        }

    @staticmethod
    def generate(prompt, output_path, width=1024, height=1024,
                 model=None, verbose=True):
        comfyui_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")

        if not LocalBackend.is_available():
            if verbose:
                print(f"  [Error] ComfyUI not reachable at {comfyui_url}")
                print("  [Info] Start ComfyUI first, or set COMFYUI_URL")
            return False

        # Build a basic FLUX txt2img workflow
        # This is a simplified workflow — for production, use custom ComfyUI workflows
        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": int(time.time()) % 1000000,
                    "steps": 20,
                    "cfg": 1.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": model or "flux1-dev-fp8.safetensors"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1,
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["4", 1],
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "blurry, low quality, distorted",
                    "clip": ["4", 1],
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2],
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "northstar",
                    "images": ["8", 0],
                }
            },
        }

        payload = json.dumps({"prompt": workflow}).encode("utf-8")

        try:
            if verbose:
                print(f"  [Local/ComfyUI] Submitting workflow...")

            # Queue the prompt
            req = urllib.request.Request(
                f"{comfyui_url}/prompt",
                data=payload,
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                prompt_id = result.get("prompt_id")

                if not prompt_id:
                    if verbose:
                        print(f"  [Error] No prompt_id in response: {result}")
                    return False

                if verbose:
                    print(f"  [Info] Queued (ID: {prompt_id}), waiting...")

            # Poll for completion
            start_time = time.time()
            timeout = 300  # 5 minutes max

            while time.time() - start_time < timeout:
                time.sleep(2)

                try:
                    req = urllib.request.Request(
                        f"{comfyui_url}/history/{prompt_id}",
                        headers={"Accept": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        history = json.loads(resp.read().decode("utf-8"))

                    if prompt_id in history:
                        outputs = history[prompt_id].get("outputs", {})
                        # Find the first image output
                        for node_id, node_output in outputs.items():
                            if "images" in node_output:
                                img_info = node_output["images"][0]
                                # Download the image
                                img_url = (f"{comfyui_url}/view"
                                          f"?filename={img_info['filename']}"
                                          f"&subfolder={img_info.get('subfolder', '')}"
                                          f"&type={img_info.get('type', 'output')}")

                                req = urllib.request.Request(img_url)
                                with urllib.request.urlopen(req, timeout=30) as img_resp:
                                    data = img_resp.read()

                                output_path.parent.mkdir(parents=True, exist_ok=True)
                                with open(output_path, "wb") as f:
                                    f.write(data)

                                if verbose:
                                    elapsed = time.time() - start_time
                                    print(f"  [Success] {len(data)/1024:.1f} KB "
                                          f"({elapsed:.1f}s) -> {output_path.name}")
                                return True

                        if verbose:
                            print(f"  [Error] No images in output")
                        return False

                except Exception:
                    continue

            if verbose:
                print(f"  [Error] Timeout after {timeout}s")
            return False

        except Exception as e:
            if verbose:
                print(f"  [Error] {type(e).__name__}: {e}")
            return False


# ============================================================
# BATCH OPERATIONS
# ============================================================

def get_backend(name):
    """Get a backend class by name."""
    if name not in BACKENDS:
        print(f"Error: Unknown backend '{name}'")
        print(f"Available: {', '.join(BACKENDS.keys())}")
        sys.exit(1)
    return BACKENDS[name]


def generate_all_concepts(backend_name, width, height, model, verbose=True):
    """Generate images for all design concepts."""
    backend = get_backend(backend_name)

    if not backend.is_available():
        print(f"\n[Error] Backend '{backend_name}' is not available.")
        info = backend.info()
        if info.get("requires_key"):
            print(f"  Set these env vars: {info.get('key_env_vars', [])}")
        elif info.get("requires_running"):
            print(f"  Start {info['requires_running']} first")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = OUTPUT_DIR / f"batch_{timestamp}"

    results = {
        "timestamp": timestamp,
        "backend": backend_name,
        "resolution": f"{width}x{height}",
        "model": model or "default",
        "concepts": {},
    }

    total = len(DESIGN_CONCEPTS)

    print(f"\n{'='*60}")
    print(f"  NORTHSTAR IMAGE GENERATOR v2")
    print(f"  Backend: {backend_name} ({backend.info()['name']})")
    print(f"  Resolution: {width}x{height}")
    print(f"  Output: {batch_dir}")
    print(f"  Concepts: {total}")
    print(f"{'='*60}\n")

    for i, (key, concept) in enumerate(DESIGN_CONCEPTS.items(), 1):
        print(f"[{i}/{total}] {concept['name']}")

        filename = f"{concept['category']}_{key}.jpg"
        output_path = batch_dir / filename

        success = backend.generate(
            prompt=concept["prompt"],
            output_path=output_path,
            width=width,
            height=height,
            model=model,
            verbose=verbose,
        )

        results["concepts"][key] = {
            "name": concept["name"],
            "success": success,
            "file": str(output_path) if success else None,
        }

        # Pause between requests (kind to free APIs)
        if i < total:
            time.sleep(2)

    # Save manifest
    manifest_path = batch_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    successes = sum(1 for c in results["concepts"].values() if c["success"])
    failures = total - successes

    print(f"\n{'='*60}")
    print(f"  COMPLETE: {successes}/{total} generated successfully")
    if failures:
        print(f"  FAILED: {failures}")
    print(f"  Output: {batch_dir}")
    print(f"{'='*60}\n")

    return results


def generate_single_concept(backend_name, concept_key, width, height, model, verbose=True):
    """Generate a single concept."""
    backend = get_backend(backend_name)

    if not backend.is_available():
        print(f"\n[Error] Backend '{backend_name}' is not available.")
        info = backend.info()
        if info.get("requires_key"):
            print(f"  Set these env vars: {info.get('key_env_vars', [])}")
        return False

    if concept_key not in DESIGN_CONCEPTS:
        print(f"Error: Unknown concept '{concept_key}'")
        print(f"Available: {', '.join(DESIGN_CONCEPTS.keys())}")
        return False

    concept = DESIGN_CONCEPTS[concept_key]
    print(f"\nGenerating: {concept['name']} (via {backend_name})")

    filename = f"{concept['category']}_{concept_key}.jpg"
    output_path = OUTPUT_DIR / filename

    return backend.generate(
        prompt=concept["prompt"],
        output_path=output_path,
        width=width,
        height=height,
        model=model,
        verbose=verbose,
    )


def generate_custom(backend_name, prompt, filename, width, height, model, verbose=True):
    """Generate from a custom prompt."""
    backend = get_backend(backend_name)

    if not backend.is_available():
        print(f"\n[Error] Backend '{backend_name}' is not available.")
        return False

    output_path = OUTPUT_DIR / filename
    print(f"\nGenerating custom image: {filename} (via {backend_name})")

    return backend.generate(
        prompt=prompt,
        output_path=output_path,
        width=width,
        height=height,
        model=model,
        verbose=verbose,
    )


def list_concepts():
    """Print all available design concepts."""
    print(f"\n{'='*60}")
    print(f"  NORTHSTAR DESIGN CONCEPTS")
    print(f"{'='*60}\n")

    by_category = {}
    for key, concept in DESIGN_CONCEPTS.items():
        cat = concept["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append((key, concept))

    for cat, concepts in by_category.items():
        print(f"  [{cat.upper()}]")
        for key, concept in concepts:
            print(f"    --concept {key:25s} {concept['name']}")
        print()


def list_backends():
    """Print all available backends and their status."""
    print(f"\n{'='*60}")
    print(f"  IMAGE GENERATION BACKENDS")
    print(f"{'='*60}\n")

    for name, cls in BACKENDS.items():
        info = cls.info()
        available = cls.is_available()
        status = "[OK] READY" if available else "[--] NOT READY"

        print(f"  [{name.upper()}] {info['name']} - {status}")
        print(f"    Cost: {info['cost']}")
        print(f"    Quality: {info['quality']}")
        print(f"    Best for: {info['best_for']}")
        print(f"    Models: {', '.join(info.get('models', []))}")

        if not available and info.get("requires_key"):
            print(f"    Setup: Set env vars: {', '.join(info.get('key_env_vars', []))}")
        elif not available and info.get("requires_running"):
            print(f"    Setup: Start {info['requires_running']}")

        if info.get("recommended_models_for_16gb"):
            print(f"    Recommended for 16GB VRAM:")
            for rec in info["recommended_models_for_16gb"]:
                print(f"      - {rec}")

        print()


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Northstar Image Generator v2 — Multi-Backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Backends (pick the best one for your needs):
  pollinations  Free, no key. Good for quick tests.
  cloudflare    Free 100k/day. Needs CF account + token.
  huggingface   Free tier. Needs HF token. Best free quality.
  local         Your GPU (ComfyUI). Best quality, unlimited.

Examples:
  python tools/generate_images.py --list-backends
  python tools/generate_images.py --list
  python tools/generate_images.py --backend pollinations --concept analysts-desk
  python tools/generate_images.py --backend cloudflare --concept northstar-logo
  python tools/generate_images.py --backend huggingface --prompt "A woman coding"
  python tools/generate_images.py --backend local --concept living-dashboard
        """,
    )

    parser.add_argument("--list", action="store_true", help="List all design concepts")
    parser.add_argument("--list-backends", action="store_true", help="List all backends and status")
    parser.add_argument("--backend", "-b", type=str, default="pollinations",
                        help=f"Backend to use (default: pollinations). Options: {', '.join(BACKENDS.keys())}")
    parser.add_argument("--concept", type=str, help="Generate a specific concept by key")
    parser.add_argument("--prompt", type=str, help="Generate from a custom prompt")
    parser.add_argument("--filename", type=str, default="custom_image.jpg",
                        help="Filename for custom prompt output")
    parser.add_argument("--all", action="store_true", help="Generate all concepts (default)")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help=f"Width (default: {DEFAULT_WIDTH})")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help=f"Height (default: {DEFAULT_HEIGHT})")
    parser.add_argument("--model", type=str, default=None, help="Model name (backend-specific)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    args = parser.parse_args()

    if args.list:
        list_concepts()
        return

    if args.list_backends:
        list_backends()
        return

    if args.concept:
        generate_single_concept(args.backend, args.concept, args.width, args.height,
                                args.model, not args.quiet)
    elif args.prompt:
        generate_custom(args.backend, args.prompt, args.filename, args.width, args.height,
                        args.model, not args.quiet)
    else:
        generate_all_concepts(args.backend, args.width, args.height, args.model, not args.quiet)


if __name__ == "__main__":
    main()
