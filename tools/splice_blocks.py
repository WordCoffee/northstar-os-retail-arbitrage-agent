"""
Splice plain-text replacement blocks into tools/browser_agent.py.

Anchors are found by CONTENT, never by hard-coded line numbers, so a block can
be re-applied or re-ordered safely. Each block declares its start anchor and its
end anchor; the end anchor is searched FORWARD from the start anchor only, so a
block can never swallow the next function.

Writes to a staging file. It does NOT overwrite the target. Review the diff,
then promote it.

Usage:
    python tools/splice_blocks.py                 # write browser_agent.staged.py
    python tools/splice_blocks.py --promote       # write browser_agent.py
    python tools/splice_blocks.py --diff          # print unified diff only
"""
import difflib
import io
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(os.path.dirname(ROOT), "tools", "browser_agent.py")
BLOCKDIR = os.path.join(ROOT, "_blocks")
STAGED = TARGET.replace(".py", ".staged.py")

# (block file, start-anchor predicate, end-anchor predicate)
# "after" markers mean the block begins one line BELOW the anchor line.
BLOCKS = [
    (
        "b1_header.txt",
        lambda l: l == "Usage:",
        lambda l: l == "sys.path.insert(0, str(PROJECT_ROOT))",
    ),
    (
        "b2_cloudflare.txt",
        lambda l: l.startswith("# CLOUDFLARE SIGNUP"),
        lambda l: l.strip() == 'return " | ".join(result_lines)',
    ),
    (
        "b3_screenshot.txt",
        lambda l: l.startswith("# SCREENSHOT HELPER"),
        lambda l: l.strip() == "return str(shot)",
    ),
    (
        "b4_cdp.txt",
        lambda l: l.startswith("# CDP TAKEOVER"),
        # last `return None, None, None` in the function: the one AFTER the
        # async_playwright().start() line. This is what prevents an orphaned
        # `except`/`finally` from being left behind.
        lambda l: l.strip() == "return None, None, None",
    ),
    (
        "b5_costco.txt",
        lambda l: l.startswith("# COSTCO BUSINESS CENTER SEARCH"),
        lambda l: l.strip() == 'return " | ".join(result_lines)',
    ),
    (
        "b6_interactive.txt",
        lambda l: l.startswith("# INTERACTIVE MODE"),
        lambda l: l.strip() == 'print(f"Error: {e}")',
    ),
]

# start offsets, one line above the anchor (the `# ====` banner line)
BACKTRACK = 1


def find(lines, pred, frm=0, strict_first=False):
    for i in range(frm, len(lines)):
        if pred(lines[i]):
            return i
    raise SystemExit("anchor not found")


def apply_block(lines, name, start_pred, end_pred):
    block = io.open(os.path.join(BLOCKDIR, name), encoding="utf-8").read().rstrip("\n").split("\n")

    # b4 has two `return None, None, None` before the real end anchor.
    if name == "b4_cdp.txt":
        s_anchor = find(lines, start_pred)
        # This string is the anchor that locates the CDP block, so it must match.
        pw = find(lines, lambda l: "async_playwright().start()" in l, frm=s_anchor)  # chromeconnect:audit-allow anchor string, not a driver
        e = find(lines, end_pred, frm=pw + 1)
    else:
        s_anchor = find(lines, start_pred)
        e = find(lines, end_pred, frm=s_anchor + 1)

    s = s_anchor - BACKTRACK
    if s < 0:
        raise SystemExit(f"{name}: start anchor has no banner line above it")

    removed = lines[s:e + 1]
    lines[s:e + 1] = block
    print(f"  {name}: lines {s + 1}-{e + 1} ({len(removed)} out) -> {len(block)} in")
    return lines


def read_lines(path):
    """Read preserving the file's own newline style, but normalize for matching."""
    raw = io.open(path, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    body = raw.replace("\r\n", "\n") if crlf else raw
    return body.split("\n"), crlf


def write_lines(path, lines, crlf):
    body = "\n".join(lines)
    io.open(path, "w", encoding="utf-8", newline="").write(
        body.replace("\n", "\r\n") if crlf else body
    )


def main():
    original, crlf = read_lines(TARGET)
    lines = list(original)

    print(f"target: {TARGET}  newlines: {'CRLF' if crlf else 'LF'}  lines: {len(lines)}")
    print("splicing blocks:")
    for name, sp, ep in BLOCKS:
        lines = apply_block(lines, name, sp, ep)

    out = "\n".join(lines)

    if "--diff" in sys.argv:
        a = "\n".join(original).replace("\r\n", "\n").split("\n")
        b = out.split("\n")
        diff = difflib.unified_diff(
            a, b,
            fromfile="tools/browser_agent.py", tofile="tools/browser_agent.py (patched)",
            lineterm="", n=3,
        )
        print("\n".join(diff))
        return

    write_lines(STAGED, lines, crlf)
    print(f"\nstaged -> {STAGED}")

    if "--promote" in sys.argv:
        write_lines(TARGET, lines, crlf)
        print(f"promoted -> {TARGET}")


if __name__ == "__main__":
    main()
