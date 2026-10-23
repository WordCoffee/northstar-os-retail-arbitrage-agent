# Marco Kaz shorts → repo scan (2026-10-22)

Source: `https://www.youtube.com/@MarcoKaz` (Shorts-only channel; the Facebook reels
are the same clips). His GitHub account `Kazandjieff` is empty (0 repos, created
2026-03-16) — he is a curator, not a builder, so the signal is the repos he points at.

## What was scanned

| Layer | Count | How |
|---|---|---|
| Shorts enumerated | 263 | `yt-dlp --flat-playlist` on `/@MarcoKaz/shorts` |
| Captions downloaded | 526 VTT | `--write-auto-subs --sub-langs "en.*"` (en + en-orig per video) |
| Transcripts parsed | 263 | `extract_repos.py` |
| GitHub URLs in captions/descriptions | **0** | he says "comment X for the repo"; descriptions are empty |
| Named tools recovered from speech | 38 | `called` / `named` / `search for` patterns |

Because there are no URLs, every name below was resolved to a real repository and
**metadata-verified through the GitHub API on 2026-10-22** (stars, SPDX licence,
language, last push, archived flag). Auto-captions garble product names, so a few
identifications are marked *probable* rather than certain.

## Re-run

```sh
yt-dlp --flat-playlist --print "%(id)s|%(title)s|%(description)s" \
  "https://www.youtube.com/@MarcoKaz/shorts" > shorts_meta.tsv
yt-dlp --skip-download --write-auto-subs --sub-langs "en.*" --sub-format vtt \
  -o "subs/%(id)s.%(ext)s" "https://www.youtube.com/@MarcoKaz/shorts"
python extract_repos.py
```

`subs/` is git-ignored (1.7 MB of third-party captions, reproducible in one command).
`mentions.csv` and `repos_found.jsonl` keep the extracted names plus the caption
lines they came from, so every claim stays traceable.

## Files

- `extract_repos.py` — VTT cleaner + name/URL extractor (no network)
- `mentions.csv` — flat `video id, title, kind, value`
- `repos_found.jsonl` — per-video urls / github / called names / repo lines
- `shorts_meta.tsv` — id, title, description (descriptions are empty in practice)
