"""Consume an MCP server over stdio.

Northstar has *served* MCP since ``tools/northstar_mcp_server.py`` (six read-only
tools). Nothing could *consume* one, so every MCP server in the ecosystem -
filesystem, git, docs, databases - was unreachable. This is the client half.

The surface is deliberately small, because the protocol is:

    initialize()      handshake
    list_tools()      what the server offers, with input schemas
    call_tool()       run exactly one named tool with JSON arguments
    list_resources()  optional: resources the server publishes
    read_resource()   optional: one resource by URI

Every connection is a short-lived child process with a hard timeout, and every
call is appended to ``logs/mcp_client.jsonl``. A server that fails to start is a
reported failure, never an empty tool list.

This is an egress path, so it is governed before it spawns:

  * the server command must be an executable or a script path - ``cmd``,
    ``powershell``, ``bash`` and ``sh`` (any casing, any path, ``.exe`` or not)
    are refused, because a shell is not an MCP server;
  * indirection **one hop from a shell** is refused too: ``wsl``, ``docker``,
    ``podman``, ``env``, ``xargs`` and the like, plus any executable whose own
    arguments carry a code flag (``-c``, ``-e``, ``/c``, ``-lc``, ``-Command``)
    together with a URL-shaped or shell-shaped payload - because
    ``python -c "urllib.request.urlopen(...)"`` is a shell in all but name;
  * URL-shaped substrings are screened **anywhere** in an argument, not only at
    the start: absolute (``https?://``), protocol-relative (``//host/path``) and
    bare host forms (``www.amazon.com/dp/X``, ``amazon.com/...``,
    ``amzn.to/...``) are all passed to ``tools/egress_guard.check()`` before the
    tool call is dispatched;
  * the audit line records the tool and the argument paths that were screened,
    plus each decision, so a refusal is diagnosable after the fact.

Stated limit, so nobody over-trusts it: this reads the *text* of an argument. It
cannot read what a payload means - a base64 blob, a scheme assembled at runtime
(``"ht" + "tps://host"``), or a server's own network stack are outside this
control. The refusal set is a denylist at the client boundary, not a sandbox.

CLI:

    python tools/mcp_client.py --arg tools/northstar_mcp_server.py --list
    python tools/mcp_client.py --arg tests/fixtures/mcp_echo_server.py --call add --args '{"a": 2, "b": 3}'
    python tools/mcp_client.py --arg tools/northstar_mcp_server.py --call northstar_health

Exit codes: 0 ok, 2 transport/timeout failure.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG = ROOT / "logs" / "mcp_client.jsonl"

#: A server is an executable or a script. These are shells, so they are refused:
#: a shell wrapper turns the client into an ungoverned "run anything" primitive.
SHELL_WRAPPERS = frozenset({"cmd", "powershell", "pwsh", "bash", "sh", "dash",
                            "zsh", "ksh", "fish", "csh", "tcsh", "ash", "mksh",
                            "busybox"})

#: One hop from a shell, measured 2026-11-06: ``wsl -e bash -lc "curl ..."`` and
#: ``docker run --rm curlimages/curl`` both reached the network while ``wsl`` and
#: ``docker`` are not shells by name. These run another command line, so their
#: arguments are code, not data, and the client cannot screen them as arguments.
LAUNCHERS = frozenset({"wsl", "docker", "podman", "nerdctl", "env", "xargs",
                       "sudo", "doas", "su", "runuser", "chroot", "nohup",
                       "setsid", "nice", "timeout", "script", "expect", "ssh",
                       "curl", "wget"})

#: Flags that make the next argument a program or a snippet: a code flag plus a
#: payload is an interpreter, which is a shell with extra steps.
CODE_FLAGS = frozenset({"-c", "/c", "-e", "/e", "-lc", "-ic", "-ec", "-xc",
                        "-eval", "/eval", "--eval", "--exec", "-exec",
                        "-command", "/command", "-encodedcommand",
                        "/encodedcommand"})

#: Shell-shaped payload: command separators, substitution, or a shell/egress
#: program named inside the string.
SHELL_SHAPED = re.compile(
    r"(?i)(?:&&|\|\||\$\(|`|\|\s|;\s*"
    r"|\b(?:bash|sh|zsh|cmd|powershell|pwsh|wsl|docker|podman|env|xargs"
    r"|curl|wget|nc|ncat|socat|subprocess|os\.system|shell=true)\b)")

#: URL-shaped, matched **anywhere** in a string, because
#: ``{"q": "fetch https://www.amazon.com/dp/X"}`` is the same request as
#: ``{"url": "https://www.amazon.com/dp/X"}`` with the label filed off.
_URL_LABEL = r"[a-z0-9](?:[a-z0-9_\-]{0,61}[a-z0-9])?"
_URL_HOST = rf"(?:{_URL_LABEL}\.){{1,8}}[a-z]{{2,63}}"
_SCHEME = r"[a-z][a-z0-9+.\-]*://"
URL_SHAPED = re.compile(
    rf"(?ix)"
    rf"(?<![\w.\-\\/:])"                 # not mid-word, not mid-path, not after a dot
    rf"(?:{_SCHEME}|//)?"                # absolute scheme, or protocol-relative
    rf"{_URL_HOST}"                      # host: www.amazon.com, amazon.de, amzn.to
    rf"(?::[0-9]{{1,5}})?"               # optional port
    rf"(?:[/?#][^\s\"'<>()\[\]{{}}|\\^`]*)?")

#: A bare candidate whose last label is one of these is a filename, not a host
#: (``mcp_echo_server.py``), so it is not screened as a URL. Candidates *with* a
#: path or a scheme are always screened, whatever their last label says.
_FILE_EXTENSIONS = frozenset({
    "py", "pyc", "pyi", "js", "mjs", "cjs", "jsx", "ts", "tsx", "json", "jsonl",
    "md", "txt", "rst", "exe", "dll", "so", "dylib", "bat", "ps1", "whl", "egg",
    "lock", "toml", "ini", "cfg", "yaml", "yml", "log", "html", "htm", "css",
    "scss", "png", "jpg", "jpeg", "gif", "svg", "webp", "pdf", "csv", "zip",
    "tar", "gz", "7z", "rar", "mp4", "mp3", "wav", "xlsx", "docx", "ipynb",
    "sqlite", "db", "venv", "psm1", "psd1",
})


_EGRESS_GUARD: Any = None
_EGRESS_GUARD_FAILED = False


class McpFailure(RuntimeError):
    """The server could not be reached or the call did not complete."""


class McpRefused(McpFailure):
    """The client declined before spawning or dispatching. Never a result."""

    def __init__(self, message: str, *, checks: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(message)
        self.checks: List[Dict[str, Any]] = list(checks or [])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_egress_guard() -> Any:
    """Import ``tools/egress_guard.py`` whether tools/ is a module or a path."""
    global _EGRESS_GUARD, _EGRESS_GUARD_FAILED
    if _EGRESS_GUARD is not None or _EGRESS_GUARD_FAILED:
        return _EGRESS_GUARD
    try:
        import egress_guard as mod  # noqa: PLC0415 - tools/ on sys.path
    except ImportError:
        try:
            from tools import egress_guard as mod  # noqa: PLC0415
        except ImportError:
            _EGRESS_GUARD_FAILED = True
            return None
    _EGRESS_GUARD = mod
    return mod


def _command_stem(command: Any) -> str:
    """The bare program name: no quotes, no directory, no extension, lowercased."""
    text = str(command or "").strip().strip('"').strip("'").strip()
    name = re.split(r"[\\/]", text)[-1].strip()
    return name.split(".")[0].lower()


def _assert_launchable(command: Any, args: Sequence[str] = ()) -> None:
    """An MCP server is an executable or a script path, never a shell or a code payload.

    Four refusals by name, all before anything is spawned:

      * ``empty_command`` - there is nothing to run;
      * ``shell_wrapper_refused`` - the program name *is* a shell;
      * ``launcher_chain_refused`` - the program runs another command line
        (``wsl``, ``docker``, ``env``, ``xargs``, ``curl``), so its arguments are
        code and the client cannot screen them as arguments;
      * ``interpreter_payload_refused`` - the program takes a code flag and one of
        its own arguments carries a URL-shaped or shell-shaped payload, which is
        an interpreter, which is a shell one hop away.
    """
    if not str(command or "").strip():
        raise McpRefused("empty_command: an MCP server needs an executable or a script path")
    stem = _command_stem(command)
    if stem in SHELL_WRAPPERS:
        raise McpRefused(
            f"shell_wrapper_refused: {stem!r} is a shell, not an MCP server "
            f"(command={str(command)[:200]!r})")
    if stem in LAUNCHERS:
        raise McpRefused(
            f"launcher_chain_refused: {stem!r} runs another command line, so its "
            f"arguments are code, not data (command={str(command)[:200]!r})")

    flow = [str(a) for a in (args or ())]
    flag = next((a.strip() for a in flow if a.strip().lower() in CODE_FLAGS), None)
    if flag is None:
        return
    payload = " ".join(a for a in flow if a.strip().lower() not in CODE_FLAGS)
    urls = list(_iter_url_shaped(payload))
    if urls:
        # Report the strongest candidate: an explicit scheme or ``//host`` beats a
        # dotted token that merely looks like one (``urllib.request``).
        explicit = [u for u in urls if _is_absolute(u) or u.startswith("//")]
        shown = (explicit or urls)[0]
        raise McpRefused(
            f"interpreter_payload_refused: {stem!r} {flag!r} carries a URL-shaped "
            f"payload ({shown[:120]!r}); a code flag is a shell one hop away")
    if SHELL_SHAPED.search(payload):
        raise McpRefused(
            f"interpreter_payload_refused: {stem!r} {flag!r} carries a shell-shaped "
            f"payload ({payload[:120]!r}); a code flag is a shell one hop away")


def _is_absolute(candidate: str) -> bool:
    return bool(re.match(rf"(?i){_SCHEME}", candidate))


def _iter_url_shaped(text: str) -> Iterator[str]:
    """Every URL-shaped substring of ``text``: absolute, ``//host`` or bare host."""
    for match in URL_SHAPED.finditer(str(text)):
        candidate = match.group(0)
        if not candidate:
            continue
        if not _is_absolute(candidate) and not candidate.startswith("//"):
            host_head = candidate.split("/", 1)[0].rsplit(":", 1)[0]
            last_label = host_head.rsplit(".", 1)[-1].lower()
            if "/" not in candidate and last_label in _FILE_EXTENSIONS:
                continue  # a path to a file, not a host
        yield candidate


def _screened_url(candidate: str) -> str:
    """Give a scheme-less candidate a shape a host parser can read.

    ``www.amazon.com/dp/X`` and ``//www.amazon.com/dp/X`` are the same request as
    ``https://www.amazon.com/dp/X``; the guard sees the one form it parses.
    """
    text = candidate.strip()
    if _is_absolute(text):
        return text
    return "https://" + text.lstrip("/")


def _walk_urls(value: Any, path: str) -> Iterator[Tuple[str, str]]:
    """Every URL-shaped substring under ``value``, with the path that holds it."""
    if isinstance(value, str):
        for candidate in _iter_url_shaped(value):
            yield path, candidate
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_urls(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _walk_urls(item, f"{path}[{index}]")


def _screen(command: Any, args: Sequence[str], arguments: Optional[Dict[str, Any]], *,
            caller: str) -> List[Dict[str, Any]]:
    """Refuse the launcher, then screen every URL-shaped argument.

    Runs before the server process is spawned and before the tool is dispatched,
    so a refusal costs no child process and no request.
    """
    _assert_launchable(command, args)

    candidates: List[Tuple[str, str]] = []
    if isinstance(command, str):
        candidates.extend(("command", found) for found in _iter_url_shaped(command))
    for index, item in enumerate(args or ()):
        candidates.extend(_walk_urls(item, f"server_args[{index}]"))
    if arguments is not None:
        candidates.extend(_walk_urls(arguments, "arguments"))

    checks: List[Dict[str, Any]] = []
    for path, raw in candidates:
        guard = _load_egress_guard()
        if guard is None:
            checks.append({"path": path, "url": raw.strip()[:400],
                           "decision": "refused", "reason": "egress_guard_unavailable"})
            raise McpRefused(
                f"egress_guard_unavailable: cannot screen {path}; refusing to dispatch",
                checks=checks)
        url = _screened_url(raw)
        try:
            guard.check(url, caller=caller)
        except guard.EgressRefused as exc:
            checks.append({"path": path, "url": raw.strip()[:400],
                           "decision": "refused", "reason": str(exc)})
            raise McpRefused(f"{exc} (argument {path})", checks=checks) from exc
        checks.append({"path": path, "url": raw.strip()[:400],
                       "host": guard.host_of(url), "decision": "allowed"})
    return checks


def _log(record: Dict[str, Any]) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": _now(), **record}, ensure_ascii=False) + "\n")


def _text(content: Sequence[Any]) -> Any:
    """MCP returns a list of content blocks; keep text, note anything else."""
    parts: List[Any] = []
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append({"type": getattr(block, "type", "unknown")})
    if len(parts) == 1:
        return parts[0]
    return parts


def _params(command: str, args: Sequence[str], cwd: Optional[str]) -> Any:
    from mcp import StdioServerParameters

    return StdioServerParameters(command=command, args=list(args), cwd=cwd)


async def _run(command: str, args: Sequence[str], *,
               cwd: Optional[str] = None,
               tool: Optional[str] = None,
               arguments: Optional[Dict[str, Any]] = None,
               timeout: float = 60.0) -> Dict[str, Any]:
    caller = f"tools/mcp_client.py:{tool or 'list_tools'}"
    checks = _screen(command, args, arguments, caller=caller)

    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    params = _params(command, args, cwd)

    async def body() -> Dict[str, Any]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                tools = [{"name": t.name, "description": (t.description or "")[:300],
                          "input_schema": getattr(t, "input_schema", None) or
                                          getattr(t, "inputSchema", None)}
                         for t in listed.tools]
                result: Dict[str, Any] = {"server_tools": tools,
                                          "tool_count": len(tools),
                                          "egress_checked": checks}
                if tool:
                    call = await session.call_tool(tool, arguments or {})
                    result["called"] = tool
                    result["arguments"] = arguments or {}
                    result["is_error"] = bool(getattr(call, "isError", False))
                    result["content"] = _text(call.content)
                return result

    try:
        return await asyncio.wait_for(body(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise McpFailure(f"timeout after {timeout}s: {command} {' '.join(args)}") from exc
    except McpFailure:
        raise
    except Exception as exc:  # noqa: BLE001 - every failure is reported, none hidden
        raise McpFailure(f"{type(exc).__name__}: {exc}") from exc


def list_tools(command: str = sys.executable, args: Sequence[str] = (), *,
               cwd: Optional[str] = None, timeout: float = 60.0) -> Dict[str, Any]:
    base = {"action": "list_tools", "command": command, "args": list(args)}
    try:
        out = asyncio.run(_run(command, args, cwd=cwd, timeout=timeout))
    except McpRefused as exc:
        _log({**base, "status": "refused", "tool": None,
              "arguments_checked": exc.checks, "error": str(exc)})
        raise
    _log({**base, "status": "ok", "tool": None, "tool_count": out["tool_count"],
          "arguments_checked": out.get("egress_checked", [])})
    return out


def call_tool(tool: str, arguments: Optional[Dict[str, Any]] = None, *,
              command: str = sys.executable, args: Sequence[str] = (),
              cwd: Optional[str] = None, timeout: float = 120.0) -> Dict[str, Any]:
    base = {"action": "call_tool", "command": command, "args": list(args),
            "tool": tool}
    try:
        out = asyncio.run(_run(command, args, cwd=cwd, tool=tool,
                               arguments=arguments or {}, timeout=timeout))
    except McpRefused as exc:
        _log({**base, "status": "refused",
              "arguments_checked": exc.checks, "error": str(exc)})
        raise
    _log({**base, "status": "error" if out.get("is_error") else "ok",
          "arguments_checked": out.get("egress_checked", []),
          "sha256": hashlib.sha256(
              json.dumps(out.get("content"), sort_keys=True, default=str).encode()).hexdigest()})
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MCP client over stdio.")
    parser.add_argument("--command", default=sys.executable,
                        help="server executable (default: this Python)")
    parser.add_argument("--arg", action="append", default=[],
                        help="server argument; repeat for each")
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--list", action="store_true", help="list the server's tools")
    parser.add_argument("--call", default=None, help="tool name to call")
    parser.add_argument("--args", default="{}", help="JSON object of tool arguments")
    parser.add_argument("--args-file", default=None,
                        help="read tool arguments from a JSON file (shell-quoting safe)")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    if not ns.list and not ns.call:
        parser.print_help()
        return 2

    try:
        raw_args = ns.args
        if ns.args_file:
            raw_args = Path(ns.args_file).read_text(encoding="utf-8")
        arguments = json.loads(raw_args)
        if not isinstance(arguments, dict):
            raise ValueError("--args must be a JSON object")
        out = asyncio.run(_run(ns.command, ns.arg, cwd=ns.cwd,
                               tool=ns.call, arguments=arguments,
                               timeout=ns.timeout))
    except McpRefused as exc:
        _log({"action": "refused", "tool": ns.call, "command": ns.command,
              "args": ns.arg, "status": "refused",
              "arguments_checked": exc.checks, "error": str(exc)})
        print(f"MCP REFUSED (not a result): {exc}", file=sys.stderr)
        return 2
    except (McpFailure, ValueError) as exc:
        _log({"action": "connect", "tool": ns.call, "command": ns.command,
              "args": ns.arg, "status": "failed", "error": str(exc)})
        print(f"MCP FAILURE (not a result): {exc}", file=sys.stderr)
        return 2

    _log({"action": "probe", "tool": ns.call, "command": ns.command,
          "args": ns.arg, "status": "ok", "tool_count": out["tool_count"],
          "arguments_checked": out.get("egress_checked", [])})
    if ns.json:
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0
    print(f"connected: {out['tool_count']} tool(s)")
    for tool in out["server_tools"]:
        print(f"  - {tool['name']}: {tool['description'][:100]}")
    if ns.call:
        print(f"called {ns.call} -> is_error={out.get('is_error')}")
        print(json.dumps(out.get("content"), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
