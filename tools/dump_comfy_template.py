"""Dump a ComfyUI workflow template (UI format) incl. subgraph definitions."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))


def dump_nodes(nodes, indent="  "):
    for n in nodes:
        t = n.get("type")
        w = n.get("widgets_values")
        if t in ("MarkdownNote",):
            continue
        print(f"{indent}#{n['id']} {t} widgets={w}")


def dump_links(links, indent="  "):
    for l in links or []:
        if isinstance(l, list) and len(l) >= 5:
            print(f"{indent}{l[1]}:{l[2]} -> {l[3]}:{l[4]}")


print("TOP-LEVEL NODES:")
dump_nodes(d.get("nodes", []))
print("TOP-LEVEL LINKS:")
dump_links(d.get("links"))
defs = d.get("definitions") or {}
for sg in defs.get("subgraphs", []) or []:
    print(f"\nSUBGRAPH {sg.get('id')} name={sg.get('name')}")
    dump_nodes(sg.get("nodes", []), indent="    ")
    print("  SUBGRAPH LINKS:")
    dump_links(sg.get("links"), indent="    ")
    print("  INPUTS:", json.dumps(sg.get("inputs"), ensure_ascii=False)[:400])
    print("  OUTPUTS:", json.dumps(sg.get("outputs"), ensure_ascii=False)[:300])
