# -*- coding: utf-8 -*-
"""Conservative merge of retag_out then apply to findings.

- Claude shards (002,007,011): keep as-is
- Rule/hybrid: accept change only if confidence>=0.65 and need_deep is False
  else keep original cur from shard
- Writes merged retag_out/_merged.json and applies to pap/json/all
- Marks tag_method retag-careful vs retag-rule
"""
from __future__ import annotations
import json, os, sys, glob
from pathlib import Path
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(os.environ["USERPROFILE"]) / "Desktop" / "audit-helper"
SHARDS = ROOT / "data" / "retag_shards"
OUT = ROOT / "data" / "retag_out"
CB = json.loads((ROOT / "data" / "codebook.json").read_text(encoding="utf-8"))
WT = set(CB["work_type_관련기능"].keys())
SEC = set(CB["sector_발생분야"].keys())
CLAUDE = {"002", "007", "011"}
CONF_MIN = 0.65


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def merge():
    merged = {}
    stats = Counter()
    for i in range(12):
        name = f"{i:03d}"
        shard = load(SHARDS / f"retag_{name}.json")
        out = load(OUT / f"retag_{name}.json")
        by_out = {x["id"]: x for x in out}
        for row in shard:
            oid = row["id"]
            cur = str(row.get("cur") or "19")
            t = by_out.get(oid)
            if not t:
                stats["missing"] += 1
                continue
            wt = str(t.get("work_type") or "19")
            sec = t.get("sector")
            conf = float(t.get("confidence") or 0)
            nd = bool(t.get("need_deep"))
            if name in CLAUDE:
                use = t
                method = "retag-careful"
                stats["claude_keep"] += 1
            else:
                # conservative: only high-conf non-deep changes
                if wt != cur and conf >= CONF_MIN and not nd:
                    use = {
                        "id": oid,
                        "work_type": wt if wt in WT else "19",
                        "sector": sec if sec in SEC else None,
                        "confidence": conf,
                        "need_deep": False,
                    }
                    method = "retag-rule"
                    stats["rule_accept"] += 1
                else:
                    use = {
                        "id": oid,
                        "work_type": cur if cur in WT else "19",
                        "sector": None,
                        "confidence": 0.45 if cur != "19" else 0.3,
                        "need_deep": cur in {"01", "03", "08", "09", "10", "13", "14", "16", "19"},
                    }
                    method = "retag-hold-cur"
                    stats["rule_hold_cur"] += 1
            use = dict(use)
            use["tag_method"] = method
            if use["work_type"] not in WT:
                use["work_type"] = "19"
            if use.get("sector") not in SEC:
                use["sector"] = None
            merged[oid] = use
    path = OUT / "_merged_conservative.json"
    path.write_text(json.dumps(list(merged.values()), ensure_ascii=False), encoding="utf-8")
    print("merged", len(merged), dict(stats))
    return merged, stats


def apply(merged):
    results = {}
    for rel in ["data/findings.pap.json", "data/findings.json", "data/findings.all.json"]:
        path = ROOT / rel
        if not path.exists():
            results[rel] = {"skipped": True}
            continue
        data = load(path)
        ch = 0
        for x in data:
            t = merged.get(x["id"])
            if not t:
                continue
            wt = t["work_type"] if t["work_type"] in WT else "19"
            sec = t["sector"] if t.get("sector") in SEC else None
            x["work_type"] = wt
            x["finding_type"] = wt + "z"
            x["sector"] = sec
            x["tag_method"] = t.get("tag_method") or "retag-careful"
            x["tag_confidence"] = t.get("confidence")
            x["review"] = bool(t.get("need_deep")) or (t.get("confidence") or 0) < 0.6
            ch += 1
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        results[rel] = {"updated": ch, "n": len(data)}
        print(rel, "updated", ch, "/", len(data))
    return results


def golden_check(merged):
    gpath = ROOT / "data" / "golden" / "golden_result.json"
    g = load(gpath)
    gold = {}
    rows = g if isinstance(g, list) else g.get("results", [])
    if isinstance(g, dict) and not rows:
        for k, v in g.items():
            if isinstance(v, dict) and ("gold_work_type" in v or "work_type" in v):
                gold[k] = str(v.get("gold_work_type") or v.get("work_type"))
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            gold[row["id"]] = str(row.get("gold_work_type") or row.get("work_type"))

    # cur map
    cur = {}
    for i in range(12):
        for row in load(SHARDS / f"retag_{i:03d}.json"):
            cur[row["id"]] = str(row.get("cur") or "")

    overlap = [gid for gid in gold if gid in merged]
    before = sum(1 for gid in overlap if cur.get(gid) == gold[gid])
    after = sum(1 for gid in overlap if str(merged[gid].get("work_type")) == gold[gid])
    out = {
        "n_gold": len(gold),
        "overlap": len(overlap),
        "acc_before_pct": round(100 * before / len(overlap), 1) if overlap else None,
        "acc_after_conservative_pct": round(100 * after / len(overlap), 1) if overlap else None,
        "delta_pp": round(100 * (after - before) / len(overlap), 1) if overlap else None,
    }
    print("golden", out)
    return out


def main():
    merged, stats = merge()
    g1 = golden_check(merged)
    # only apply if not worse than before
    if g1["acc_after_conservative_pct"] is not None and g1["acc_after_conservative_pct"] < g1["acc_before_pct"]:
        print("ABORT apply: conservative still worse than cur on golden overlap")
        report = {"stats": dict(stats), "golden": g1, "applied": False}
        (OUT / "_apply_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 2
    applied = apply(merged)
    # remeasure on findings.all for gold ids
    fall = {x["id"]: x for x in load(ROOT / "data" / "findings.all.json")}
    gpath = ROOT / "data" / "golden" / "golden_result.json"
    g = load(gpath)
    gold = {}
    rows = g if isinstance(g, list) else g.get("results", [])
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            gold[row["id"]] = str(row.get("gold_work_type") or row.get("work_type"))
    if isinstance(g, dict) and not rows:
        for k, v in g.items():
            if isinstance(v, dict) and ("gold_work_type" in v or "work_type" in v):
                gold[k] = str(v.get("gold_work_type") or v.get("work_type"))
    hit = [gid for gid in gold if gid in fall]
    ok = sum(1 for gid in hit if str(fall[gid].get("work_type")) == gold[gid])
    g2 = {
        "n_gold": len(gold),
        "present_in_findings_all": len(hit),
        "acc_findings_all_pct": round(100 * ok / len(hit), 1) if hit else None,
    }
    print("post-apply golden on findings.all", g2)
    report = {"stats": dict(stats), "golden_pre_apply": g1, "applied": applied, "golden_post": g2}
    (OUT / "_apply_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DONE", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
