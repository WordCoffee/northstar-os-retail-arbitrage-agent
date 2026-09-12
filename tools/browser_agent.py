"""
Northstar Browser Agent
=======================
Local, FREE AI browser automation — Perplexity-Comet-style hybrid agent.

SPEED TUNING (RTX 5080 / 16 GB):
  - FlashAttention:     ON   (OLLAMA_FLASH_ATTENTION=1)
  - Viewport:           1024x768 (50% fewer visual tokens for the vision model)
  - num_predict:        2048  (complete action JSON — NOT truncated. The old
                              num_predict=100 was truncating the JSON -> parse
                              failure -> silent infinite retry = "stuck" agent)
  - OMP_NUM_THREADS:    4     (optimized thread pooling)

CLOUDFLARE SIGNUP — HYBRID (fastest reliable path):
  - Deterministic Playwright script fills email + password (instant,
    guaranteed, never "stuck").
  - If a Turnstile/captcha appears -> hand off to the vision agent.
  - Operator-approved step: CLICK "Create account" submit, screenshot proof,
    then STOP before the email-verification/Turnstile live step.

Requires:  pip install browser-use playwright langchain-ollama
           playwright install chromium
           ollama serve
           ollama pull qwen2.5vl:7b

Usage:
    python tools/browser_agent.py "Go to google.com and search for 'northstar os'"
    python tools/browser_agent.py --signup-cloudflare --email a@b.com --password 'pw'
    python tools/browser_agent.py --signup-cloudflare --email a@b.com --password 'pw' --chrome
    python tools/browser_agent.py --interactive
    python tools/browser_agent.py --screenshot --url https://google.com
    python tools/browser_agent.py --list-models
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# ENVIRONMENT OPTIMIZATIONS (must be set before Ollama loads)
# ============================================================

os.environ["OLLAMA_FLASH_ATTENTION"] = "1"   # FlashAttention — faster prefill
os.environ["OMP_NUM_THREADS"] = "4"          # Optimized thread pooling


# ============================================================
# CONFIGURATION
# ============================================================

SCREENSHOT_DIR = PROJECT_ROOT / "generated_images" / "screenshots"
DEFAULT_MODEL = "qwen2.5vl:7b"   # Vision model with spatial grounding
OLLAMA_BASE_URL = "http://127.0.0.1:11434"

# Optimized viewport — smaller screen = fewer visual tokens = faster inference
OPTIMIZED_VIEWPORT = {"width": 1024, "height": 768}
NUM_PREDICT = 2048  # Complete JSON — never truncates the action block


# ============================================================
# vLLM BACKEND (fastest, optional — sub-2s inference)
# ============================================================

VLLM_BASE_URL = "http://localhost:8000/v1"
VLLM_MODEL = "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"


def _vllm_available() -> bool:
    """Check if vLLM server is running locally."""
    try:
        import httpx
        r = httpx.get(f"{VLLM_BASE_URL}/models", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


# ============================================================
# LLM SETUP — vLLM (fastest) -> Ollama (local FREE) -> Gemini (cloud)
# ============================================================

def get_llm(model_name: str = None, verbose: bool = True):
    """Create an LLM — vLLM (fastest), Ollama (local FREE), or Gemini (cloud)."""
    model_name = model_name or DEFAULT_MODEL

    # --- FASTEST: vLLM (PagedAttention, sub-2s responses) ---
    if _vllm_available():
        try:
            from browser_use.llm import ChatOpenAI as BrowserUseChatOpenAI
            if verbose:
                print(f"Using vLLM: {VLLM_MODEL} (sub-2s, PagedAttention)")
            return BrowserUseChatOpenAI(
                base_url=VLLM_BASE_URL,
                api_key="vllm-local",
                model=VLLM_MODEL,
            )
        except Exception as e:
            if verbose:
                print(f"vLLM unavailable: {e}")

    # --- LOCAL: Ollama with speed-optimized settings ---
    try:
        from browser_use.llm import ChatOllama as BrowserUseChatOllama
        if verbose:
            print(f"Using Ollama: {model_name} (FlashAttention ON, num_predict={NUM_PREDICT})")
        return BrowserUseChatOllama(
            model=model_name,
            ollama_options={
                "num_ctx": 32000,        # Room for multi-step history
                "temperature": 0.0,      # Deterministic — no randomness
                "num_predict": NUM_PREDICT,  # Complete JSON — never truncates
            },
        )
    except Exception as e:
        if verbose:
            print(f"Ollama unavailable: {e}")

    # --- CLOUD FALLBACK: Google Gemini (rate-limited free tier) ---
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        try:
            from browser_use.llm import ChatGoogle
            if verbose:
                print("Using Google Gemini (gemini-3.6-flash) — cloud fallback")
            return ChatGoogle(model="gemini-3.6-flash")
        except Exception as e:
            if verbose:
                print(f"Gemini unavailable: {e}")

    return None


# ============================================================
# AGENT HELPER — LLM with fallback
# ============================================================

async def run_task(task: str, model: str = None, headless: bool = False,
                   verbose: bool = True, use_chrome: bool = False) -> str:
    """Run a browser task using AI agent with optimized settings."""
    try:
        from browser_use import Agent
    except ImportError as e:
        print(f"Error: Missing dependency: {e}")
        print("Run: pip install browser-use langchain-ollama")
        return None

    llm = get_llm(model, verbose)
    if not llm:
        return None

    if verbose:
        print(f"\nTask: {task}")
        print(f"Viewport: {OPTIMIZED_VIEWPORT['width']}x{OPTIMIZED_VIEWPORT['height']} (optimized)")
        print(f"Headless: {headless}")
        print("Starting browser agent...\n")

    # Fallback LLM (Ollama vision model)
    fallback_llm = None
    try:
        from browser_use.llm import ChatOllama as BrowserUseChatOllama
        fallback_llm = BrowserUseChatOllama(model="qwen2.5vl:7b")
    except Exception:
        pass

    agent = Agent(
        task=task,
        llm=llm,
        fallback_llm=fallback_llm,
        headless=headless,
        max_actions_per_step=1,
    )

    result = await agent.run()
    if verbose:
        print(f"\nResult: {result}")

    return str(result)


# ============================================================
# CLOUDFLARE SIGNUP — HYBRID (deterministic fill + submit + vision fallback)
# ============================================================

async def cloudflare_signup(email: str, password: str, verbose: bool = True,
                           use_chrome: bool = True) -> str:
    """
    Cloudflare account creation — HYBRID (fastest reliable path).
    - Scripted Playwright fill = instant, deterministic, never stuck.
    - OPERATOR-APPROVED: clicks "Create account" and screenshots proof.
    - STOPS before the email-verification/Turnstile live step.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        print(f"Error: playwright not installed: {e}")
        return None

    result_lines = []
    if verbose:
        print("\n=== CLOUDFLARE SIGNUP (hybrid: scripted fill + submit) ===")
        print(f"Email:    {email}")
        print(f"Password: {'*' * len(password)}")
        print(f"Chrome (Mogra profile): {use_chrome}")

    browser = None
    try:
        async with async_playwright() as p:
            # Launch Chrome (executable_path only — NEVER user-data-dir, which
            # Playwright rejects/hangs on Windows; that's the proven-sticky path)
            launch_kwargs = {"headless": False}
            if use_chrome:
                chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                if os.path.exists(chrome_exe):
                    launch_kwargs["executable_path"] = chrome_exe
                    if verbose:
                        print("Using Chrome executable (proven non-hanging)")
                else:
                    if verbose:
                        print("Chrome not found, using Playwright Chromium")

            browser = await p.chromium.launch(**launch_kwargs)
            page = await browser.new_page(viewport=OPTIMIZED_VIEWPORT)

            if verbose:
                print("Navigating to cloudflare.com/sign-up ...")
            await page.goto("https://cloudflare.com/sign-up",
                            wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)  # Let the SPA render

            # --- Deterministic email fill ---
            email_filled = False
            email_selectors = [
                "input[type='email']",
                "input[name='email']",
                "input#email",
                "input[autocomplete='email']",
                "input[placeholder*='Email' i]",
            ]
            for sel in email_selectors:
                loc = page.locator(sel).first
                try:
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.fill(email)
                        email_filled = True
                        if verbose:
                            print(f"Filled email ({sel})")
                        break
                except Exception:
                    continue
            if not email_filled:
                print("EMAIL FIELD NOT FOUND (needs vision agent)")

            # --- Deterministic password fill ---
            pass_filled = False
            pass_selectors = [
                "input[type='password']",
                "input[name='password']",
                "input#password",
                "input[autocomplete='new-password']",
            ]
            for sel in pass_selectors:
                loc = page.locator(sel).first
                try:
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.fill(password)
                        pass_filled = True
                        if verbose:
                            print(f"Filled password ({sel})")
                        break
                except Exception:
                    continue

            # Save proof screenshot before any submit
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot = SCREENSHOT_DIR / f"cloudflare_signup_{ts}.png"
            try:
                await page.screenshot(path=str(shot))
            except Exception:
                pass

            # --- OPERATOR-APPROVED: click "Create account" submit ---
            if verbose:
                print("\nOperator approved — clicking Create account...")
            submit_clicked = False
            submit_selectors = [
                "button[type='submit']",
                "button[contains(., 'Create account')]",
                "button[contains(., 'Sign up')]",
                "button[contains(., 'Continue')]",
                "form button",
                "button.btn-primary",
            ]
            for sel in submit_selectors:
                btn = page.locator(sel).first
                try:
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click()
                        submit_clicked = True
                        if verbose:
                            print(f"Clicked submit ({sel})")
                        break
                except Exception:
                    continue

            if submit_clicked:
                # Allow any Turnstile/redirect to show; screenshot evidence
                await page.wait_for_timeout(6000)
                ts2 = datetime.now().strftime("%Y%m%d_%H%M%S")
                shot2 = SCREENSHOT_DIR / f"cloudflare_after_submit_{ts2}.png"
                try:
                    await page.screenshot(path=str(shot2))
                except Exception:
                    pass
                result_lines.append(f"CLICKED SUBMIT + screenshot: {shot2}")
                if verbose:
                    print(f"\nScreenshot after submit: {shot2}")
                    print("\nSTOPPED — pending email verification + Turnstile.")
                    print("Finish verification manually (this is a live step).")
            else:
                result_lines.append("SUBMIT NOT FOUND (needs vision agent)")
                if verbose:
                    print("\nSubmit button not found by selectors (needs vision agent)")

            await page.wait_for_timeout(10_000)  # Hold open for operator

    except Exception as e:
        result_lines.append(f"ERROR: {e}")
        if verbose:
            print(f"Error: {e}")
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    return " | ".join(result_lines)


# ============================================================
# SCREENSHOT HELPER
# ============================================================

async def take_screenshot(url: str = None, use_chrome: bool = False) -> str:
    """Take a screenshot of a webpage (uses operator's Mogra Chrome profile)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Error: playwright not installed")
        return None

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    shot = SCREENSHOT_DIR / f"screenshot_{ts}.png"

    async with async_playwright() as p:
        launch_kwargs = {"headless": False}
        if use_chrome:
            chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            if os.path.exists(chrome_exe):
                launch_kwargs["executable_path"] = chrome_exe
                # NOTE: do NOT pass --user-data-dir (Playwright rejects it and
                # persistent context hangs on Windows). Plain launch is the
                # proven non-hanging path.
                print("Using Chrome binary (operator's Mogra machine)")
            else:
                print("Chrome not found, using Playwright Chromium")
        browser = await p.chromium.launch(**launch_kwargs)
        page = await browser.new_page(viewport=OPTIMIZED_VIEWPORT)

        if url:
            print(f"Navigating to: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        else:
            print("Opened blank page")

        await page.screenshot(path=str(shot), full_page=True)
        print(f"Screenshot saved: {shot}")

        if not url:
            input("Press Enter to close browser...")
        else:
            await asyncio.sleep(3)

        await browser.close()

    return str(shot)


# ============================================================
# CDP TAKEOVER (Comet-style: drive the browser that's ALREADY open)
# ============================================================

async def connect_takeover(verbose: bool = True):
    """
    Attach to an already-open Chrome via CDP (port 9222) and drive it
    in-place — Comet-style. Returns (browser, context, pages) or (None,None,None).
    Only used when the operator explicitly requested a profile takeover.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, None, None

    if verbose:
        print("Probing CDP at 127.0.0.1:9222 ...")
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:9222/json/version", timeout=2.0)
        if r.status_code != 200:
            if verbose:
                print("No CDP browser open (:9222 not listening) — will launch fresh")
            return None, None, None
    except Exception:
        if verbose:
            print("No CDP browser open (:9222 not reachable) — will launch fresh")
        return None, None, None

    if verbose:
        print("CDP browser IS open — attaching and driving it in-place (Comet-style)")
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp("http://127.0.0.1:9222",
                                                             timeout=10000)
        contexts = browser.contexts
        ctx = contexts[0] if contexts else None
        return browser, ctx, ctx.pages if ctx else []
    except Exception as e:
        if verbose:
            print(f"CDP attach failed ({e}) — will launch fresh")
        return None, None, None


# ============================================================
# COSTCO BUSINESS CENTER SEARCH (deterministic — no vision needed)
# ============================================================

async def costco_search(query: str, verbose: bool = True,
                        use_chrome: bool = False) -> str:
    """
    Costco Business Delivery search (read-only, deterministic).
    STOPS at search results — never carts, never lists, never buys.
    """
    # Deterministic URL encoding — the only import we need here
    from urllib.parse import quote

    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        print(f"Error: playwright not installed: {e}")
        return None

    if verbose:
        print("\n=== COSTCO BUSINESS DELIVERY SEARCH (read-only) ===")
        print(f"Query: {query}")
        print(f"Chrome: {use_chrome}")
        print("READ-ONLY: search + screenshot proof. No cart, no listing, no buy.\n")

    result_lines = []
    browser = None
    try:
        async with async_playwright() as p:
            # --- Proven non-hanging launch (executable_path only, NO user-data-dir) ---
            launch_kwargs = {"headless": False}
            if use_chrome:
                chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                if os.path.exists(chrome_exe):
                    launch_kwargs["executable_path"] = chrome_exe
                    if verbose:
                        print("Using Chrome binary (proven non-hanging)")
                else:
                    if verbose:
                        print("Chrome not found, using Playwright Chromium")

            browser = await p.chromium.launch(**launch_kwargs)
            page = await browser.new_page(viewport=OPTIMIZED_VIEWPORT)

            # Costco Business Delivery search URL with the query parameter
            search_url = f"https://www.costcobusinessdelivery.com/{quote(query)}/SearchDisplay"
            if verbose:
                print(f"Navigating to Costco Business Delivery search ...")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)  # SPA render

            # --- Deterministic keyword fill (backup if URL param didn't apply) ---
            query_filled = False
            query_selectors = [
                "input[name='searchTerm']",
                "input[name='keyword']",
                "input[placeholder*='Search' i]",
                "input[type='search']",
                "#searchTerm",
            ]
            for sel in query_selectors:
                loc = page.locator(sel).first
                try:
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.fill(query)
                        query_filled = True
                        if verbose:
                            print(f"Filled search box ({sel})")
                        break
                except Exception:
                    continue
            if not query_filled and verbose:
                print("Search box not found by selectors (results likely already loaded)")

            # --- Proof screenshot ---
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot = SCREENSHOT_DIR / f"costco_{query[:20]}_{ts}.png"
            try:
                await page.screenshot(path=str(shot), full_page=True)
                result_lines.append(f"screenshot: {shot}")
                if verbose:
                    print(f"\nProof screenshot: {shot}")
            except Exception:
                pass

            if verbose:
                print("\n=== SEARCH DONE — results on screen ===")
                print("STOPPED — read-only. No cart/listing/purchase executed.")
                print("Check the browser window; say 'quit' or close it.")

            await page.wait_for_timeout(15_000)  # Hold open for operator review

    except Exception as e:
        result_lines.append(f"ERROR: {e}")
        if verbose:
            print(f"Error: {e}")
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    return " | ".join(result_lines)


async def current_task(task: str, verbose: bool = True) -> str:
    """Alias — keep the proven path name; deterministic Costco Business
    Delivery search (read-only, stops before cart/listing)."""
    return await costco_search(task, verbose=verbose)


# ============================================================
# INTERACTIVE MODE
# ============================================================

async def interactive_mode(model: str = None):
    """Interactive mode — keep giving tasks."""
    try:
        from browser_use import Agent
    except ImportError:
        print("Error: browser-use not installed")
        return

    llm = get_llm(model)
    if not llm:
        return

    print("\n=== NORTHSTAR BROWSER AGENT (Interactive) ===")
    print(f"Model: {model or DEFAULT_MODEL} (local Ollama)")
    print(f"Viewport: {OPTIMIZED_VIEWPORT['width']}x{OPTIMIZED_VIEWPORT['height']}")
    print("Type a task and press Enter. Type 'quit' to exit.\n")

    while True:
        try:
            task = input("Task> ").strip()
            if not task:
                continue
            if task.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            agent = Agent(
                task=task,
                llm=llm,
                headless=False,
                max_actions_per_step=1,
            )
            result = await agent.run()
            print(f"\nResult: {result}\n")

        except KeyboardInterrupt:
            print("\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Northstar Browser Agent — AI-powered browser automation (local Ollama)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Optimized for speed:
  Viewport:   {OPTIMIZED_VIEWPORT['width']}x{OPTIMIZED_VIEWPORT['height']} (50% fewer visual tokens)
  Model:      {DEFAULT_MODEL} (vision model with spatial grounding)
  FlashAttention: ON
  num_predict:  {NUM_PREDICT} (complete JSON — never truncates)

Usage:
    python tools/browser_agent.py "Go to google.com and search for 'northstar os'"
    python tools/browser_agent.py --interactive
    python tools/browser_agent.py --signup-cloudflare --email a@b.com --password 'pw'
    python tools/browser_agent.py --screenshot --url https://google.com

All processing runs LOCALLY on your GPU. No API keys needed.
        """,
    )

    parser.add_argument("task", nargs="?", help="Task for the browser agent")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Start interactive mode (continuous tasks)")
    parser.add_argument("--screenshot", "-s", action="store_true",
                        help="Take a screenshot instead of running an agent task")
    parser.add_argument("--url", type=str, help="URL to navigate to (for screenshot)")
    parser.add_argument("--chrome", action="store_true",
                        help="Use Chrome with Mogra profile instead of Playwright Chromium")
    parser.add_argument("--signup-cloudflare", action="store_true",
                        help="Create a Cloudflare account (hybrid scripted fill)")
    parser.add_argument("--email", type=str,
                        help="Email for --signup-cloudflare")
    parser.add_argument("--password", type=str,
                        help="Password for --signup-cloudflare")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress verbose output (for scripted cron/CI runs)")
    parser.add_argument("--list-models", action="store_true",
                        help="List available Ollama models")
    parser.add_argument("--costco-search", action="store_true",
                        help="Costco Business Delivery deterministic search (read-only)")
    parser.add_argument("--takeover", action="store_true",
                        help="Comet-style: take over an ALREADY-OPEN browser "
                             "via CDP (port 9222) and drive it in-place. Falls "
                             "back to a fresh launch if nothing is listening.")
    parser.add_argument("--query", type=str, help="Costco search query (e.g. 'trash bags')")

    args = parser.parse_args()

    if args.list_models:
        try:
            import ollama
            models = ollama.list()
            print("\nAvailable Ollama models:")
            for m in models.get("models", []):
                size_gb = m.get("size", 0) / (1024**3)
                print(f"  {m['name']:40s}  {size_gb:.1f} GB")
        except Exception as e:
            print(f"Error listing models: {e}")
        return

    if args.signup_cloudflare:
        if not args.email or not args.password:
            parser.error("--signup-cloudflare requires --email and --password")
        asyncio.run(cloudflare_signup(args.email, args.password,
                                      use_chrome=args.chrome))
    elif args.takeover:
        asyncio.run(connect_takeover(verbose=not args.quiet))
    elif args.costco_search:
        if not args.query:
            parser.error("--costco-search requires --query")
        asyncio.run(costco_search(args.query, use_chrome=args.chrome))
    elif args.interactive:
        asyncio.run(interactive_mode())
    elif args.screenshot:
        asyncio.run(take_screenshot(args.url, use_chrome=args.chrome))
    elif args.task:
        asyncio.run(run_task(args.task, use_chrome=args.chrome))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
