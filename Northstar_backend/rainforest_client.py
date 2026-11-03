"""Rainforest API adapter (opt-in / explicit-selection only).

Offline-first integration. This module is *inert by default*:

* It is never selected by the scanner unless the caller explicitly asks for
  it (``provider="rainforest"`` or the explicit routing flag
  ``RAINFOREST_ENABLED=1``). Existing routing defaults
  (``SCANNER_SEARCH_SOURCE``) are untouched.
* With no ``RAINFOREST_API_KEY`` configured it returns ``NOT_CONFIGURED`` and
  makes **no** HTTP call.
* It never falls back to Bright Data, Savio/Scavio, Chocodata or a browser
  path. A failure is returned as a failure.
* It never reads, prints, logs, or persists the API key. Receipts contain a
  scrubbed summary (provider, operation, status, request count, field *names*)
  — never the key, never the request URL/query (which carries the key).

Official Rainforest (Traject Data) documentation cross-checked for parameter
and response shapes (no API request was made while building this):

* Product parameters .......... https://docs.trajectdata.com/rainforestapi/product-data-api/parameters/product
* Search parameters ........... https://docs.trajectdata.com/rainforestapi/product-data-api/parameters/search
* Offers parameters ........... https://docs.trajectdata.com/rainforestapi/product-data-api/parameters/offers
* Product results ............. https://docs.trajectdata.com/rainforestapi/product-data-api/results/product
* Search results .............. https://docs.trajectdata.com/rainforestapi/product-data-api/results/search
* Offers results .............. https://docs.trajectdata.com/rainforestapi/product-data-api/results/offers
* GTIN/UPC/EAN -> ASIN ........ https://docs.trajectdata.com/rainforestapi/product-data-api/reference/gtin-upc-ean-to-asin
* Supported Amazon domains .... https://docs.trajectdata.com/rainforestapi/product-data-api/reference/amazon-domains
* Response codes .............. https://docs.trajectdata.com/rainforestapi/response-codes

Confirmed request facts used here:
* Endpoint ``GET https://api.rainforestapi.com/request`` with ``api_key``.
* ``type=product`` accepts ``asin`` (with ``amazon_domain``), ``gtin`` (any
  GTIN/ISBN/UPC/EAN, auto-converted to an ASIN), or ``url``.
* ``type=search`` accepts ``search_term`` (``amazon_domain``); there is **no**
  dedicated MPN/model parameter, so MPN lookup is performed as a keyword
  search on the MPN/model string.
* ``type=offers`` accepts ``asin`` (with ``amazon_domain``) or ``gtin`` and
  returns a ``offers`` array of seller offers.

Credit note: a plain product/search/offers request is 1 credit; optional
flags (``skip_gtin_cache``, ``include_*``) can raise that. This adapter sends
none of the surcharge flags, so the estimate is 1 credit per planned request.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

try:  # dotenv is present across the repo; tolerate its absence in tests.
    from env_bootstrap import load_project_env

    # Repo-root .env is authoritative (see env_bootstrap). A bare load_dotenv()
    # here would bind Northstar_backend/.env, which does not carry
    # RAINFOREST_API_KEY, and the adapter would report NOT_CONFIGURED.
    load_project_env()
except Exception:  # noqa: BLE001
    pass

# ---------------------------------------------------------------------------
# Constants (names only; no secret values live here)
# ---------------------------------------------------------------------------

PROVIDER_NAME = "rainforest"
ROUTING_FLAG_ENV = "RAINFOREST_ENABLED"
KEY_ENV = "RAINFOREST_API_KEY"  # variable NAME; value never read into a log

DEFAULT_REQUEST_URL = "https://api.rainforestapi.com/request"
DEFAULT_AMAZON_DOMAIN = "amazon.com"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_REQUESTS = 10

# Status vocabulary.
STATUS_OK = "OK"
STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
STATUS_DRY_RUN = "DRY_RUN"
STATUS_HTTP_ERROR = "HTTP_ERROR"
STATUS_TRANSPORT_ERROR = "TRANSPORT_ERROR"
STATUS_MALFORMED = "MALFORMED_RESPONSE"
STATUS_REQUEST_CAP_REACHED = "REQUEST_CAP_REACHED"
STATUS_UNKNOWN_OPERATION = "UNKNOWN_OPERATION"

# Normalized candidate status: never an assertion of an exact match.
CANDIDATE_UNVERIFIED = "CANDIDATE_UNVERIFIED"
UNKNOWN = "UNKNOWN"

# Operations -> Rainforest request type.
OPERATION_TYPES = {
    "product_by_gtin": "product",
    "product_by_asin": "product",
    "search_by_title": "search",
    "search_by_mpn": "search",
    "offers_by_asin": "offers",
}

# Default credit estimate per planned request (no surcharge flags used).
CREDITS_PER_REQUEST = 1.0


class _HttpLike(Protocol):
    def get(self, url: str, params: dict, timeout: float) -> Any: ...


class RainforestError(RuntimeError):
    """Adapter-level error (never carries the key)."""


# ---------------------------------------------------------------------------
# Result / receipt types
# ---------------------------------------------------------------------------


@dataclass
class RainforestReceipt:
    """Scrubbed, secret-free receipt. Safe to log or persist."""

    provider: str = PROVIDER_NAME
    operation: str = ""
    status: str = ""
    request_count: int = 0
    dry_run: bool = False
    estimated_credits: float = 0.0
    field_names: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "status": self.status,
            "request_count": self.request_count,
            "dry_run": self.dry_run,
            "estimated_credits": self.estimated_credits,
            "field_names": list(self.field_names),
            "notes": list(self.notes),
        }


@dataclass
class RainforestResult:
    """Typed adapter result. Duck-compatible with the provider registry
    contract (``ok`` / ``error_class`` / ``message``)."""

    ok: bool
    status: str
    operation: str = ""
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    error_class: Optional[str] = None
    message: Optional[str] = None
    request_count: int = 0
    receipt: Optional[RainforestReceipt] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "operation": self.operation,
            "candidates": list(self.candidates),
            "error_class": self.error_class,
            "message": self.message,
            "request_count": self.request_count,
            "receipt": self.receipt.to_dict() if self.receipt else None,
        }


# ---------------------------------------------------------------------------
# Explicit-selection gate
# ---------------------------------------------------------------------------


def _env_true(value: Optional[str]) -> bool:
    return str(value or "").strip().upper() in {"1", "TRUE", "YES", "ON", "ENABLED"}


def rainforest_selected(provider: Optional[str] = None, environ: Optional[dict] = None) -> bool:
    """True ONLY when explicitly requested.

    Selection requires either ``provider == "rainforest"`` (explicit request)
    or the explicit routing flag (``RAINFOREST_ENABLED``). There is no
    implicit/default-on path.
    """
    env = os.environ if environ is None else environ
    if str(provider or "").strip().lower() == PROVIDER_NAME:
        return True
    return _env_true(env.get(ROUTING_FLAG_ENV))


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _text(value: Any) -> str:
    if value is None:
        return UNKNOWN
    text = str(value).strip()
    return text if text else UNKNOWN


def _num(value: Any) -> Optional[float]:
    """Never fabricate 0 for a missing price — unknown stays None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    return None


# "pack of 24" (count after the phrase) and "12 count" / "12-pack" / "6 pk"
# (count before the unit) are the two shapes seen on Amazon titles.
_PACK_RES = (
    re.compile(r"\b(?:pack|pk|count|set)\s+of\s+(\d{1,4})\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,4})\s*(?:-|\s)?(?:pack|pk|ct|count)\b", re.IGNORECASE),
)


def detect_pack_count(title: Optional[str]) -> Optional[int]:
    """Best-effort pack/count parsed from a title. Unknown -> None."""
    if not title or title == UNKNOWN:
        return None
    for pattern in _PACK_RES:
        match = pattern.search(title)
        if match:
            try:
                return int(match.group(1))
            except (TypeError, ValueError):
                return None
    return None


def _amazon_is_seller(seller_name: Optional[str]) -> Optional[bool]:
    """True for Amazon itself; None when the seller is unknown."""
    if not seller_name or seller_name == UNKNOWN:
        return None
    return seller_name.strip().lower().startswith("amazon")


def _brand_direct(seller_name: Optional[str], brand: Optional[str]) -> bool:
    if not seller_name or not brand:
        return False
    if seller_name == UNKNOWN or brand == UNKNOWN:
        return False
    seller_tokens = {t for t in re.split(r"\W+", seller_name.lower()) if t}
    brand_tokens = {t for t in re.split(r"\W+", brand.lower()) if t}
    return bool(brand_tokens) and brand_tokens.issubset(seller_tokens)


def apply_hard_filters(
    candidate: Dict[str, Any],
    *,
    brand: Optional[str] = None,
    expected_pack_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Flag (never silently drop) Amazon-Retail / brand-direct / pack-count
    mismatches. Flags are appended to ``candidate["flags"]``.
    """
    flags = candidate.setdefault("flags", [])
    resolved_brand = brand if brand is not None else candidate.get("brand")
    seller = candidate.get("seller_name")

    if candidate.get("amazon_is_seller") is True:
        flags.append("AMAZON_RETAIL_SELLER")
    if _brand_direct(seller, resolved_brand):
        flags.append("BRAND_DIRECT_SELLER")

    if expected_pack_count is not None:
        found = detect_pack_count(candidate.get("title"))
        if found is not None and found != expected_pack_count:
            flags.append("PACK_COUNT_MISMATCH")

    # De-duplicate while preserving order.
    seen = set()
    candidate["flags"] = [f for f in flags if not (f in seen or seen.add(f))]
    return candidate


def _base_candidate(*, asin=None, title=None, brand=None, price=None,
                    currency=None, buybox=None, source_op="") -> Dict[str, Any]:
    return {
        "asin": _text(asin),
        "title": _text(title),
        "brand": _text(brand),
        "price": _num(price),
        "price_currency": _text(currency),
        "buybox_winner": _bool_or_none(buybox),
        "seller_name": UNKNOWN,
        "seller_id": UNKNOWN,
        "seller_rating": None,
        "is_prime": None,
        "is_new": None,
        "offer_id": UNKNOWN,
        "amazon_is_seller": None,
        "verification": CANDIDATE_UNVERIFIED,
        "match_basis": source_op,
        "flags": [],
    }


def normalize_product(payload: Dict[str, Any], source_op: str = "product_by_asin") -> List[Dict[str, Any]]:
    product = (payload or {}).get("product") or {}
    asin = product.get("asin")
    title = product.get("title")
    brand = product.get("brand")
    buybox = product.get("buybox_winner") or {}
    price_obj = buybox.get("price") if isinstance(buybox, dict) else None
    seller = buybox.get("seller") if isinstance(buybox, dict) else None
    # `buybox_winner` may be a bool or an object depending on the response.
    is_buybox = bool(buybox) if buybox is not None else None

    candidate = _base_candidate(
        asin=asin,
        title=title,
        brand=brand,
        price=(price_obj or {}).get("value") if isinstance(price_obj, dict) else None,
        currency=(price_obj or {}).get("currency") if isinstance(price_obj, dict) else None,
        buybox=is_buybox,
        source_op=source_op,
    )
    if isinstance(seller, dict):
        candidate["seller_name"] = _text(seller.get("name"))
        candidate["seller_id"] = _text(seller.get("id"))
        candidate["seller_rating"] = _num(seller.get("rating"))
        candidate["amazon_is_seller"] = _amazon_is_seller(candidate["seller_name"])
    return [apply_hard_filters(candidate)]


def normalize_search(payload: Dict[str, Any], source_op: str = "search_by_title") -> List[Dict[str, Any]]:
    results = (payload or {}).get("search_results") or []
    candidates: List[Dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        price_obj = item.get("price") if isinstance(item.get("price"), dict) else {}
        candidate = _base_candidate(
            asin=item.get("asin"),
            title=item.get("title"),
            brand=item.get("brand"),
            price=price_obj.get("value"),
            currency=price_obj.get("currency"),
            buybox=None,
            source_op=source_op,
        )
        candidate["is_prime"] = _bool_or_none(item.get("is_prime"))
        candidates.append(apply_hard_filters(candidate))
    return candidates


def normalize_offers(payload: Dict[str, Any], source_op: str = "offers_by_asin") -> List[Dict[str, Any]]:
    product = (payload or {}).get("product") or {}
    offers = (payload or {}).get("offers") or []
    candidates: List[Dict[str, Any]] = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        price_obj = offer.get("price") if isinstance(offer.get("price"), dict) else {}
        seller = offer.get("seller") if isinstance(offer.get("seller"), dict) else {}
        condition = offer.get("condition") if isinstance(offer.get("condition"), dict) else {}
        candidate = _base_candidate(
            asin=offer.get("offer_asin") or product.get("asin"),
            title=product.get("title"),
            brand=product.get("brand"),
            price=price_obj.get("value"),
            currency=price_obj.get("currency"),
            buybox=_bool_or_none(offer.get("buybox_winner")),
            source_op=source_op,
        )
        candidate["seller_name"] = _text(seller.get("name"))
        candidate["seller_id"] = _text(seller.get("id"))
        candidate["seller_rating"] = _num(seller.get("rating"))
        candidate["is_prime"] = _bool_or_none(offer.get("is_prime"))
        candidate["is_new"] = _bool_or_none(condition.get("is_new"))
        candidate["offer_id"] = _text(offer.get("offer_id"))
        candidate["amazon_is_seller"] = _amazon_is_seller(candidate["seller_name"])
        candidates.append(apply_hard_filters(candidate))
    return candidates


_NORMALIZERS = {
    "product": normalize_product,
    "search": normalize_search,
    "offers": normalize_offers,
}


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class RainforestClient:
    """Opt-in Rainforest client. No implicit selection, no fallback.

    Parameters
    ----------
    api_key:
        The Rainforest key. Held in memory only; never logged, returned, or
        written. ``None``/empty makes every operation return
        ``NOT_CONFIGURED`` without touching the network.
    http:
        Injectable HTTP client implementing ``get(url, params, timeout)``.
        Tests pass a mock; production omits it and the real ``requests``
        client is used lazily. The adapter never retries automatically.
    max_requests:
        Per-run request cap (default 10). Enforced *before* any HTTP call.
    dry_run:
        When True, plan the request(s) and estimate credits without calling.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        http: Optional[_HttpLike] = None,
        request_url: str = DEFAULT_REQUEST_URL,
        amazon_domain: str = DEFAULT_AMAZON_DOMAIN,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        dry_run: bool = False,
    ) -> None:
        self._api_key = api_key or None
        self._http = http
        self._request_url = request_url
        self._amazon_domain = amazon_domain
        self._timeout = float(timeout)
        self._max_requests = int(max_requests)
        self._dry_run = bool(dry_run)
        self._request_count = 0

    # -- introspection -----------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def max_requests(self) -> int:
        return self._max_requests

    @classmethod
    def from_env(cls, environ: Optional[dict] = None, **kwargs: Any) -> "RainforestClient":
        env = os.environ if environ is None else environ
        return cls(
            api_key=env.get(KEY_ENV),
            request_url=env.get("RAINFOREST_REQUEST_URL", DEFAULT_REQUEST_URL),
            amazon_domain=env.get("RAINFOREST_AMAZON_DOMAIN", DEFAULT_AMAZON_DOMAIN),
            timeout=float(env.get("RAINFOREST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
            max_requests=int(env.get("RAINFOREST_MAX_REQUESTS", str(DEFAULT_MAX_REQUESTS))),
            **kwargs,
        )

    # -- public operations -------------------------------------------------

    def product_by_asin(self, asin: str) -> RainforestResult:
        return self._run("product_by_asin", {"asin": asin})

    def product_by_gtin(self, gtin: str) -> RainforestResult:
        return self._run("product_by_gtin", {"gtin": gtin})

    def search_by_title(self, title: str) -> RainforestResult:
        return self._run("search_by_title", {"search_term": title})

    def search_by_mpn(self, mpn: str) -> RainforestResult:
        """MPN/model lookup. Rainforest exposes no dedicated MPN parameter
        (confirmed in the product/search docs), so this is a keyword search
        on the MPN/model string via ``search_term``."""
        return self._run("search_by_mpn", {"search_term": mpn})

    def offers_by_asin(self, asin: str) -> RainforestResult:
        return self._run("offers_by_asin", {"asin": asin})

    # Backwards-friendly alias.
    def search_by_upc(self, upc: str) -> RainforestResult:
        return self.product_by_gtin(upc)

    # -- internals ---------------------------------------------------------

    def _receipt(self, operation: str, status: str, field_names=None, notes=None) -> RainforestReceipt:
        return RainforestReceipt(
            operation=operation,
            status=status,
            request_count=self._request_count,
            dry_run=self._dry_run,
            estimated_credits=(CREDITS_PER_REQUEST
                               if status in (STATUS_OK, STATUS_DRY_RUN)
                               else 0.0),
            field_names=sorted(field_names or []),
            notes=list(notes or []),
        )

    def _build_params(self, operation: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        req_type = OPERATION_TYPES.get(operation)
        if req_type is None:
            raise RainforestError(f"unknown operation {operation!r}")
        params: Dict[str, Any] = {
            "api_key": self._api_key,
            "type": req_type,
            "amazon_domain": self._amazon_domain,
        }
        for key, value in inputs.items():
            if value is not None and value != "":
                params[key] = value
        return params

    def _run(self, operation: str, inputs: Dict[str, Any]) -> RainforestResult:
        # 0) unknown operation is a programming error, not a network event.
        if operation not in OPERATION_TYPES:
            return RainforestResult(
                ok=False, status=STATUS_UNKNOWN_OPERATION, operation=operation,
                error_class="unknown_operation",
                message=f"unsupported operation {operation!r}",
                request_count=self._request_count,
                receipt=self._receipt(operation, STATUS_UNKNOWN_OPERATION),
            )

        # 1) missing key: NOT_CONFIGURED, zero calls.
        if not self._api_key:
            return RainforestResult(
                ok=False, status=STATUS_NOT_CONFIGURED, operation=operation,
                error_class="not_configured",
                message=f"{KEY_ENV} is not configured",
                request_count=self._request_count,
                receipt=self._receipt(operation, STATUS_NOT_CONFIGURED,
                                      notes=[f"{KEY_ENV} missing"]),
            )

        # 2) request cap: refuse BEFORE any call.
        if self._request_count >= self._max_requests:
            return RainforestResult(
                ok=False, status=STATUS_REQUEST_CAP_REACHED, operation=operation,
                error_class="request_cap_reached",
                message=f"per-run request cap ({self._max_requests}) reached",
                request_count=self._request_count,
                receipt=self._receipt(operation, STATUS_REQUEST_CAP_REACHED,
                                      notes=[f"cap={self._max_requests}"]),
            )

        params = self._build_params(operation, inputs)

        # 3) dry run: plan only, no call, no key surfaced.
        if self._dry_run:
            return RainforestResult(
                ok=True, status=STATUS_DRY_RUN, operation=operation,
                request_count=self._request_count,
                receipt=self._receipt(
                    operation, STATUS_DRY_RUN,
                    notes=[f"planned type={params.get('type')}",
                           f"amazon_domain={params.get('amazon_domain')}"],
                ),
            )

        # 4) exactly one attempt, no automatic retry.
        self._request_count += 1
        try:
            response = self._get(params)
        except Exception as exc:  # noqa: BLE001 - transport failure is typed
            return RainforestResult(
                ok=False, status=STATUS_TRANSPORT_ERROR, operation=operation,
                error_class="transport_error",
                message=f"transport_error: {type(exc).__name__}",
                request_count=self._request_count,
                receipt=self._receipt(operation, STATUS_TRANSPORT_ERROR,
                                      notes=[f"exception={type(exc).__name__}"]),
            )

        status_code = getattr(response, "status_code", None)
        if status_code is None or int(status_code) >= 400:
            return RainforestResult(
                ok=False, status=STATUS_HTTP_ERROR, operation=operation,
                error_class="http_error",
                message=f"HTTP {status_code}",
                request_count=self._request_count,
                receipt=self._receipt(operation, STATUS_HTTP_ERROR,
                                      notes=[f"http_status={status_code}"]),
            )

        try:
            payload = response.json()
        except Exception:  # noqa: BLE001
            payload = None
        if not isinstance(payload, dict):
            return RainforestResult(
                ok=False, status=STATUS_MALFORMED, operation=operation,
                error_class="malformed_response",
                message="response was not a JSON object",
                request_count=self._request_count,
                receipt=self._receipt(operation, STATUS_MALFORMED),
            )

        req_type = OPERATION_TYPES[operation]
        candidates = _NORMALIZERS[req_type](payload, source_op=operation)
        field_names = list(payload.keys())

        return RainforestResult(
            ok=True, status=STATUS_OK, operation=operation,
            candidates=candidates,
            request_count=self._request_count,
            receipt=self._receipt(operation, STATUS_OK, field_names=field_names),
        )

    def _get(self, params: Dict[str, Any]):
        if self._http is not None:
            return self._http.get(self._request_url, params=params, timeout=self._timeout)
        import requests  # lazy: tests never reach here (network guard also blocks)

        return requests.get(self._request_url, params=params, timeout=self._timeout)


# ---------------------------------------------------------------------------
# Provider-registry integration (opt-in, not auto-bound at startup)
# ---------------------------------------------------------------------------


class RainforestAdapter:
    """Adapter bound to the foundation provider registry under the explicit
    name ``rainforest``. Behavior is identical to ``RainforestClient``; it is
    only reachable when the provider is explicitly selected and enabled."""

    provider_key = PROVIDER_NAME
    read_capable = True
    write_capable = False

    def __init__(self, client: Optional[RainforestClient] = None) -> None:
        self._client = client or RainforestClient.from_env()

    def capabilities(self) -> List[str]:
        return ["read"]

    def read(self, request: Dict[str, Any]) -> RainforestResult:
        operation = request.get("operation") or "product_by_asin"
        inputs = request.get("inputs") or {}
        if operation == "product_by_asin":
            return self._client.product_by_asin(inputs.get("asin", ""))
        if operation in ("product_by_gtin", "search_by_upc"):
            return self._client.product_by_gtin(inputs.get("gtin") or inputs.get("upc", ""))
        if operation == "search_by_title":
            return self._client.search_by_title(inputs.get("title", ""))
        if operation == "search_by_mpn":
            return self._client.search_by_mpn(inputs.get("mpn", ""))
        if operation == "offers_by_asin":
            return self._client.offers_by_asin(inputs.get("asin", ""))
        return RainforestResult(
            ok=False, status=STATUS_UNKNOWN_OPERATION, operation=operation,
            error_class="unknown_operation", message=f"unsupported operation {operation!r}",
        )

    def write(self, request: Dict[str, Any]) -> RainforestResult:
        return RainforestResult(
            ok=False, status="WRITE_NOT_PERMITTED", operation=request.get("operation", ""),
            error_class="write_not_permitted", message="Rainforest adapter is read-only",
        )


def rainforest_provider_definition():
    """Build the provider-registry definition (disabled by default)."""
    try:
        from foundation.models import ProviderDefinition  # top-level import
    except ImportError:  # pragma: no cover - package-qualified import path
        from .foundation.models import ProviderDefinition

    return ProviderDefinition(
        provider_key=PROVIDER_NAME,
        name="Rainforest API (opt-in)",
        category="discovery",
        adapter_module="rainforest_client",
        read_capable=True,
        write_capable=False,
        sandbox_supported=False,
        credential_ref_names=[KEY_ENV],  # NAMES only
        timeout_seconds=int(DEFAULT_TIMEOUT_SECONDS),
        enabled=False,  # explicit opt-in; registry never executes disabled providers
    )


def register_rainforest(registry, client: Optional[RainforestClient] = None):
    """Register the Rainforest definition + adapter on a ProviderRegistry.

    Deliberately NOT called during app startup: existing routing and the
    disabled-by-default provider row keep this inert until an operator opts in.
    """
    registry.register_definition(rainforest_provider_definition())
    registry.bind_adapter(RainforestAdapter(client=client))
    return registry


def receipt_to_json(receipt: RainforestReceipt) -> str:
    return json.dumps(receipt.to_dict(), sort_keys=True)
