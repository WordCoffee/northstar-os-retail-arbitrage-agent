"""SSRF defenses (Phase 2).

The resolver is INJECTED: the kernel never dials DNS itself in tests, and the
production gateway wires the system resolver explicitly. Design guarantees:

- resolve **once** per check; the returned IPs are pinned into the result
  (rebinding defense — the gateway must connect to the pinned IPs only);
- **every** resolved IP must be public — a mixed public+private answer set
  (classic rebinding trick) is denied;
- private/loopback/link-local/metadata/multicast/reserved ranges are blocked
  (IPv4 + IPv6, incl. v4-mapped IPv6).
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from .errors import PolicyDenied
from .urls import is_ip_literal

Resolver = Callable[[str], Sequence[str]]

_BLOCKED_V4 = tuple(
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "224.0.0.0/4",
        "255.255.255.255/32",
    )
)
_BLOCKED_V6 = tuple(
    ipaddress.ip_network(n) for n in ("::/128", "::1/128", "fc00::/7", "fe80::/10", "ff00::/8")
)


@dataclass(frozen=True)
class ResolvedTarget:
    host: str
    ips: tuple[str, ...]


def blocked_reason(ip_text: str) -> Optional[str]:
    """Return a reason string when the IP is not publicly routable, else None."""
    try:
        ip = ipaddress.ip_address(ip_text.strip())
    except ValueError:
        return "invalid_ip"
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    nets = _BLOCKED_V4 if ip.version == 4 else _BLOCKED_V6
    for net in nets:
        if ip in net:
            return f"blocked_range:{net}"
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return "blocked_range"
    return None


def resolve_and_pin(
    host: str, resolve: Optional[Resolver], *, max_ips: int = 8
) -> ResolvedTarget:
    """Resolve once and pin; deny when any answer is not public."""
    host = host.strip().lower().rstrip(".")
    if is_ip_literal(host):
        ips = (str(ipaddress.ip_address(host)),)
    else:
        if resolve is None:
            raise PolicyDenied("resolver_unavailable", host)
        try:
            answers = list(resolve(host))
        except PolicyDenied:
            raise
        except Exception as exc:  # resolver failures are denials, not crashes
            raise PolicyDenied("dns_failure", f"{host}:{type(exc).__name__}") from exc
        if not answers:
            raise PolicyDenied("dns_no_answer", host)
        if len(answers) > max_ips:
            raise PolicyDenied("dns_too_many_answers", host)
        canonical = []
        for answer in answers:
            try:
                canonical.append(str(ipaddress.ip_address(str(answer).strip())))
            except ValueError as exc:
                raise PolicyDenied("dns_invalid_answer", host) from exc
        ips = tuple(canonical)
    for ip in ips:
        reason = blocked_reason(ip)
        if reason:
            raise PolicyDenied("private_ip", f"{host}->{ip} ({reason})")
    return ResolvedTarget(host=host, ips=ips)
