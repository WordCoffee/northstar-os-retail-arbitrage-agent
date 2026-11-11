# D-027 — every pack carries its own illustration

Unit `design-motifs`. Tag `ty-dir-design-motifs`. Rollback `rollback/pre-d027-20261111`.

## The defect

`brand_art._spec` did `spec.setdefault("motif", "bean")`, and no design declared one. So
every folding carton the app printed drew **three coffee beans** — on a mushroom box, on a
tea sachet box, and on the two box-art designs pack-03 added: a drill carton and a kettle
carton carried three coffee beans as their only illustration.

## What changed

| file | change |
|---|---|
| `Northstar_backend/package_art.py` | a motif library of **original line art** — `bean` (kept, unchanged), `tool` (body, grip, chuck, bit), `appliance` (kettle body, lid, spout, handle), `bottle` (shoulders, neck, cap), `leaf` (pointed leaf with midrib) — behind one `draw_motif()` that returns **False** for a name it cannot draw |
| `Northstar_backend/brand_art.py` | `_spec` no longer invents a motif; each design declares its own: `t2-drill-box` → `tool`, `t2-kettle-box` → `appliance`, `harbor-body-oil` → `bottle`, `word-coffee*` → `bean`, `mogra-tee` / `pine-paws-joint` → `leaf` |
| `Northstar_backend/test_design_motifs.py` | nine checks written first: `_spec` invents nothing; every carton design names a motif the renderer can draw; the two box designs do not share one; an unknown name draws nothing and says so; and nailing a motif changes the panel **inside the hero band only** |

A pack that names no motif now prints **no illustration** rather than someone else's. That is
the rule the defect asked for: a loaner illustration is worse than a blank hero area, because
it is wrong in a way nobody notices.

## Measured

`python -m tools.seller_tester product --catalog ty/_briefs_boxart.json --renderer drawn`
→ `reports/ty/d027_boxart_motifs_pass.json`, `renders/d027/`

| brief | design | motif | score |
|---|---|---|---|
| ST-012 kettle | `t2-kettle-box` | `appliance` — kettle outline with spout and handle | **100.0**, passed |
| ST-028 drill | `t2-drill-box` | `tool` — drill body, grip, chuck and bit | **100.0**, passed |

2 selected, 2 scored, 2 passed, mean 100.0, 0 refused — the same numbers as pack-03, which is
the point: the illustration changed and the pass did not move.

**Instrument check:** the two renders of the drill face (named motif vs no motif) differ by
more than 200 px, and every differing row sits between 50 % and 75 % of the panel height —
the hero band. So the motif is the only thing that changed.

## Honest limit

These are **line drawings**, not artwork. They are recognisable at panel size and they are
original, but a real pack carries photography or a commissioned illustration; a drawn drill
outline is a placeholder that is honest about being one. The next real lift here is a plate
lane that renders the product itself (D-025's matte route already supports it).

## Tests

```
python -m pytest Northstar_backend/test_design_motifs.py -q                          -> 9 passed
python -m pytest Northstar_backend/test_boxart_form.py test_apparel_form.py -q       -> 13 passed
```
