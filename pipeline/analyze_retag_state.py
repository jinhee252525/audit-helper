# -*- coding: utf-8 -*-
"""정밀 상태 분석: retag_out vs shards vs golden vs findings."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
from collections import Counter, defaultdict

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(os.environ["USERPROFILE"]) / "Desktop" / "audit-helper"
SHARDS = ROOT / "data" / "retag_shards"
OUT = ROOT / "data" / "retag_out"
GOLDEN = ROOT / "data" / "golden" / "golden_result.json"
FINDINGS_ALL = ROOT / "data" / "findings.all.json"
FINDINGS_PAP = ROOT / "data" / "findings.pap.json"
FINDINGS = ROOT / "data" / "findings.json"
REPORT = ROOT / "data" / "retag_work" / "_state_report.json"

CLAUDE_DONE = {"002", "007", "011"}  # careful LLM
HYBRID_000 = "000"  # 900 dec + rules


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    report = {"shards": {}, "totals": {}, "golden": {}, "findings": {}, "recommendation": []}

    all_out = {}
    source_tag = {}  # id -> claude|hybrid|rule
    for i in range(12):
        name = f"{i:03d}"
        shard = load(SHARDS / f"retag_{name}.json")
        outp = OUT / f"retag_{name}.json"
        if not outp.exists():
            report["shards"][name] = {"status": "missing_out", "n_in": len(shard)}
            continue
        out = load(outp)
        by_in = {x["id"]: x for x in shard}
        changed = 0
        confs = []
        need = 0
        stay19 = 0
        leave_basket = 0  # cur in basket codes and still same
        for x in out:
            inn = by_in.get(x["id"], {})
            cur = str(inn.get("cur") or "")
            wt = str(x.get("work_type") or "")
            if cur != wt:
                changed += 1
            confs.append(float(x.get("confidence") or 0))
            if x.get("need_deep"):
                need += 1
            if wt == "19":
                stay19 += 1
            if cur in {"01", "03", "08", "09", "10", "13", "14", "16", "19"} and wt == cur:
                leave_basket += 1
            all_out[x["id"]] = x
            if name in CLAUDE_DONE:
                source_tag[x["id"]] = "claude"
            elif name == HYBRID_000:
                # first 900 from dec roughly — approximate via confidence patterns hard; mark hybrid
                source_tag[x["id"]] = "hybrid"
            else:
                source_tag[x["id"]] = "rule"

        avg_conf = sum(confs) / len(confs) if confs else 0
        report["shards"][name] = {
            "status": "ok",
            "source": "claude" if name in CLAUDE_DONE else ("hybrid" if name == "000" else "rule"),
            "n": len(out),
            "changed_vs_cur": changed,
            "changed_pct": round(100 * changed / len(out), 1),
            "need_deep": need,
            "need_deep_pct": round(100 * need / len(out), 1),
            "avg_confidence": round(avg_conf, 3),
            "work_type_top": Counter(x["work_type"] for x in out).most_common(8),
            "still_19": stay19,
            "still_19_pct": round(100 * stay19 / len(out), 1),
            "left_as_basket_cur": leave_basket,
        }

    # totals by source
    by_src = defaultdict(list)
    for id_, src in source_tag.items():
        by_src[src].append(all_out[id_])
    report["totals"] = {
        "n_retag_ids": len(all_out),
        "by_source": {
            s: {
                "n": len(xs),
                "need_deep_pct": round(100 * sum(1 for x in xs if x.get("need_deep")) / len(xs), 1),
                "avg_conf": round(sum(float(x.get("confidence") or 0) for x in xs) / len(xs), 3),
                "wt19_pct": round(100 * sum(1 for x in xs if x.get("work_type") == "19") / len(xs), 1),
            }
            for s, xs in by_src.items()
        },
    }

    # golden overlap
    if GOLDEN.exists():
        g = load(GOLDEN)
        # expect list or dict id->gold
        gold_map = {}
        if isinstance(g, list):
            for row in g:
                gid = row.get("id")
                gw = row.get("gold_work_type") or row.get("work_type")
                if gid and gw is not None:
                    gold_map[gid] = str(gw)
        elif isinstance(g, dict):
            # maybe {results: [...]} or id keyed
            if "results" in g and isinstance(g["results"], list):
                for row in g["results"]:
                    gid = row.get("id")
                    gw = row.get("gold_work_type") or row.get("work_type")
                    if gid and gw is not None:
                        gold_map[gid] = str(gw)
            else:
                for gid, row in g.items():
                    if isinstance(row, dict):
                        gw = row.get("gold_work_type") or row.get("work_type")
                        if gw is not None:
                            gold_map[gid] = str(gw)
                    elif isinstance(row, str):
                        gold_map[gid] = row

        overlap = [gid for gid in gold_map if gid in all_out]
        correct = sum(1 for gid in overlap if str(all_out[gid].get("work_type")) == gold_map[gid])
        by_src_acc = {}
        for src in ("claude", "hybrid", "rule"):
            ids = [gid for gid in overlap if source_tag.get(gid) == src]
            if not ids:
                by_src_acc[src] = {"n": 0, "acc": None}
                continue
            ok = sum(1 for gid in ids if str(all_out[gid].get("work_type")) == gold_map[gid])
            by_src_acc[src] = {"n": len(ids), "acc": round(100 * ok / len(ids), 1)}

        # also current cur accuracy on overlap (before retag)
        cur_correct = 0
        for gid in overlap:
            # find cur from shards
            cur = None
            for i in range(12):
                # slow but ok once - build map
                pass
        # build cur map
        cur_map = {}
        for i in range(12):
            for row in load(SHARDS / f"retag_{i:03d}.json"):
                cur_map[row["id"]] = str(row.get("cur") or "")
        cur_ok = sum(1 for gid in overlap if cur_map.get(gid) == gold_map[gid])
        retag_ok = correct

        report["golden"] = {
            "n_gold": len(gold_map),
            "overlap_with_retag": len(overlap),
            "acc_before_cur_pct": round(100 * cur_ok / len(overlap), 1) if overlap else None,
            "acc_after_retag_pct": round(100 * retag_ok / len(overlap), 1) if overlap else None,
            "acc_by_source": by_src_acc,
            "delta_pp": round(100 * (retag_ok - cur_ok) / len(overlap), 1) if overlap else None,
        }
    else:
        report["golden"] = {"error": "golden_result.json missing"}

    # findings state
    def fstats(path: Path):
        if not path.exists():
            return {"exists": False}
        # stream count without full parse if huge - but we need tag stats; load
        data = load(path)
        n = len(data)
        methods = Counter(x.get("tag_method") for x in data)
        conf_none = sum(1 for x in data if x.get("tag_confidence") is None)
        wt19 = sum(1 for x in data if x.get("work_type") == "19")
        review = sum(1 for x in data if x.get("review"))
        retag_ids_in = sum(1 for x in data if x.get("id") in all_out)
        return {
            "exists": True,
            "n": n,
            "size_mb": round(path.stat().st_size / 1024 / 1024, 1),
            "tag_method_top": methods.most_common(8),
            "tag_confidence_null": conf_none,
            "wt19_pct": round(100 * wt19 / n, 1) if n else None,
            "review_pct": round(100 * review / n, 1) if n else None,
            "retag_target_ids_present": retag_ids_in,
        }

    report["findings"] = {
        "findings.all.json": fstats(FINDINGS_ALL),
        "findings.pap.json": fstats(FINDINGS_PAP),
        "findings.json": fstats(FINDINGS),
        "apply_retag_targets": ["findings.pap.json", "findings.json"],
        "note": "apply_retag.py does NOT write findings.all.json",
    }

    # quality risk signals
    rule_need = report["totals"]["by_source"].get("rule", {})
    claude = report["totals"]["by_source"].get("claude", {})
    risks = []
    if rule_need.get("need_deep_pct", 0) > 45:
        risks.append("rule_shards_high_need_deep")
    if report.get("golden", {}).get("acc_by_source", {}).get("rule", {}).get("acc") is not None:
        ra = report["golden"]["acc_by_source"]["rule"]["acc"]
        ca = report["golden"]["acc_by_source"].get("claude", {}).get("acc")
        if ca is not None and ra is not None and ra + 5 < ca:
            risks.append("rule_golden_acc_below_claude")
    report["risks"] = risks

    # recommendation engine
    rec = []
    g = report.get("golden", {})
    if g.get("overlap_with_retag", 0) >= 50:
        if (g.get("acc_after_retag_pct") or 0) >= (g.get("acc_before_cur_pct") or 0):
            rec.append("golden_improved_or_same_on_overlap → safe to apply_retag then remeasure full golden")
        else:
            rec.append("golden_worsened_on_overlap → do NOT apply yet; LLM-refine need_deep on rule shards first")
    else:
        rec.append("golden_overlap_small → apply on pap/json after marking tag_method; then full golden remeasure")

    # always prefer: mark rule outputs, apply, measure, then optional LLM on need_deep if acc low
    rec.append("patch apply_retag to honor tag_method + also update findings.all.json if present")
    rec.append("after apply: run golden remeasure script if exists; else custom compare")
    report["recommendation"] = rec

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
