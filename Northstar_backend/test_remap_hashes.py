"""The remap tool must rewrite commits and nothing else.

A history rewrite invalidates every hash the queue, tags and reports cite. The remap is the
step that keeps those citations honest, so its two failure modes matter more than its happy
path: rewriting a number that was never a commit, and leaving a real commit hash pointing at
a commit that no longer exists. Both are pinned here.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from remap_hashes import find_hashes, parse_map, rewrite  # noqa: E402

OLD = "a" * 7 + "0" * 33          # aaaaaaa… (full)
NEW = "b" * 7 + "1" * 33          # bbbbbbb…
OLD2 = "c0ffee1" + "2" * 33       # c0ffee1…
NEW2 = "d00dfed" + "3" * 33       # d00dfed…


def _map(tmp_path: Path) -> dict:
    path = tmp_path / "commit-map"
    path.write_text(
        "old new\n"
        f"{OLD} {NEW}\n"
        f"{OLD2} {NEW2}\n"
        f"{'e' * 40} {'0' * 40}\n"
        "this line is not a pair\n",
        encoding="utf-8")
    return parse_map(path)


def test_parse_map_reads_pairs_and_skips_the_header(tmp_path: Path):
    mapping = _map(tmp_path)
    assert len(mapping) == 3
    assert mapping[OLD] == NEW
    assert mapping["e" * 40] == "0" * 40


def test_full_hash_is_rewritten(tmp_path: Path):
    mapping = _map(tmp_path)
    text = f"merged at {OLD} and again {OLD2}"
    new_text, counts, unmapped = rewrite(text, mapping)
    assert counts["full"] == 2
    assert NEW in new_text and NEW2 in new_text
    assert OLD not in new_text
    assert not unmapped


def test_short_prefix_is_rewritten_to_the_new_short(tmp_path: Path):
    mapping = _map(tmp_path)
    new_text, counts, _ = rewrite(f"see {OLD[:8]} for the commit", mapping)
    assert counts["short"] == 1
    assert NEW[:8] in new_text


def test_a_number_that_is_not_a_hash_is_never_touched(tmp_path: Path):
    mapping = _map(tmp_path)
    text = "run 1234567890 rows, timestamp 2026110901, count 7654321"
    new_text, counts, _ = rewrite(text, mapping)
    assert new_text == text
    assert counts["full"] == 0 and counts["short"] == 0


def test_an_unmapped_full_hash_is_reported_not_silently_kept(tmp_path: Path):
    mapping = _map(tmp_path)
    stray = "f" * 40
    new_text, _, unmapped = rewrite(f"unknown commit {stray}", mapping)
    assert new_text == f"unknown commit {stray}"
    assert unmapped == [stray]


def test_a_dropped_commit_short_prefix_is_not_rewritten(tmp_path: Path):
    mapping = _map(tmp_path)
    dropped = "e" * 40
    new_text, counts, _ = rewrite(f"commit {dropped[:9]}", mapping)
    assert counts["short"] == 0
    assert new_text == f"commit {dropped[:9]}"


def test_find_hashes_separates_full_from_short_and_ignores_digits():
    full, short = find_hashes(f"{OLD} and {OLD[:8]} and 1234567890 and abcdef12")
    assert full == 1
    assert short == 2  # aaaaaaa and abcdef12; the digit run is not a hash
