#!/usr/bin/env python3
"""One-shot probe: send a single-file repair request and show the raw response shape."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from moe_agentic_build import FILE_RE, post  # noqa: E402

root = os.path.abspath(sys.argv[1])
target = sys.argv[2]
errors = sys.argv[3]
with open(os.path.join(root, *target.split("/")), encoding="utf-8") as f:
    body = f.read()

user = (
    f"File: {target}\n\n"
    "The TypeScript compiler reports the errors below in this file only. Fix all of them in this file.\n"
    "Return ONLY this file, complete, in this exact shape:\n"
    f"=== FILE: {target} ===\n```ts\n<complete corrected file>\n```\n\n"
    "Errors:\n" + errors + "\n\nCurrent content:\n```ts\n" + body + "\n```\n"
)
resp = post(
    {
        "messages": [
            {"role": "system", "content": "You are a senior TypeScript engineer. Repair exactly one file. Output only that file in the required block format."},
            {"role": "user", "content": user},
        ],
        "n_predict": 4096,
        "temperature": 0.1,
        "cache_prompt": True,
        "chat_template_kwargs": {"enable_thinking": False},
    },
    8080,
)
content = resp["choices"][0]["message"].get("content") or ""
print("len:", len(content))
print("file_re_matches:", FILE_RE.findall(content)[:1] and "yes" or "no")
print("fences:", content.count("```"))
print("--- first 500 ---")
print(content[:500])
print("--- last 400 ---")
print(content[-400:])
