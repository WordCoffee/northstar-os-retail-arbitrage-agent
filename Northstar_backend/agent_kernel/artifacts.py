"""Artifact helpers: fence stripping and a conservative kind classifier."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple


def strip_markdown_fence(text: str) -> Tuple[str, bool]:
    """Remove one complete ``` / ```lang wrapper if it is the whole payload.

    The model often returns ` ```diff ... ``` ` for a file. The wrapper is a
    transport artefact, not the artifact. A partial or nested fence is left
    alone and reported as not stripped.
    """
    if not text:
        return text, False
    s = text.strip("\n")
    if not s.startswith("```"):
        return text, False
    first = s.find("\n")
    if first == -1:
        return text, False
    body = s[first + 1:]
    lines = body.splitlines()
    # Find a closing fence; it must be the last non-empty line.
    end = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            end = i
            break
    if end is None or not lines[end].strip().startswith("```"):
        return text, False
    inner = "\n".join(lines[:end]).rstrip("\n")
    return (inner + "\n" if inner else ""), True


def artifact_kind(path: str | Path) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    raw = p.read_bytes()[:16] if p.is_file() else b""
    if suffix == ".png":
        return "label_png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else "png_invalid"
    if suffix in (".jpg", ".jpeg"):
        # JPEG: SOI FF D8 FF, and an EOI marker in the tail. The EOI is searched in
        # the last 64 bytes rather than required as the final two, because real
        # files carry trailing padding and those are still valid images.
        if not raw.startswith(b"\xff\xd8\xff"):
            return "jpeg_invalid"
        try:
            size = p.stat().st_size
            with open(p, "rb") as fh:
                fh.seek(max(0, size - 64))
                tail = fh.read()
        except OSError:
            return "jpeg_invalid"
        return "image_jpeg" if b"\xff\xd9" in tail else "jpeg_invalid"
    if suffix in (".mp4", ".mov"):
        return "ad_video" if len(raw) >= 8 and raw[4:8] == b"ftyp" else "video_invalid"
    if suffix == ".json":
        return "json"
    if suffix in (".patch", ".diff"):
        return "patch"
    if suffix in (".md", ".txt", ".log"):
        return "text"
    return "binary" if raw else "empty"


def parse_json_text(text: str):
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1] if "\n" in body else body
        body = body.rsplit("```", 1)[0]
    return json.loads(body)
