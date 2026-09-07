# -*- coding: utf-8 -*-
"""FlexSearch + sharding index builder (방식 A).

Usage:
  python pipeline/build_index.py --input data/findings.all.json --out app/data/index
  python pipeline/build_index.py --input data/findings.sample.json --out app/data/index --limit 500

Does NOT invent defaults that silently read production findings without --input.
Hides education individual-school bulk behind meta flag (filter default off in UI).
Emits:
  app/data/index/manifest.json
  app/data/index/shards/shard-XXXX.json   (docs for FlexSearch Document)
  app/data/index/dashboard-agg.json       (pre-agg for insights)

Each doc keeps quality badge fields for UI routing:
  text_quality: list_only | body | matched
  review: bool
  tag_confidence: float|null
"""
from __future__ import annotations
import argparse, json, sys, hashlib
from pathlib import Path
from collections import Counter, defaultdict

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]


def text_quality(rec: dict) -> str:
    excerpt = (rec.get("source_excerpt") or "").strip()
    method = rec.get("tag_method") or ""
    if not excerpt:
        return "list_only"
    if method in {"retag-careful", "deep"} and (rec.get("tag_confidence") or 0) >= 0.7 and not rec.get("review"):
        return "matched"
    return "body"


def is_edu_school(rec: dict) -> bool:
    oid = (rec.get("org_name") or "") + " " + (rec.get("id") or "")
    # individual schools often in local_edu pap ids; hide by default in UI
    return "local_edu" in (rec.get("id") or "") or "학교" in (rec.get("org_name") or "")


def doc_from(rec: dict) -> dict:
    excerpt = (rec.get("source_excerpt") or "")[:400]
    title = rec.get("source_title") or rec.get("summary") or ""
    return {
        "id": rec.get("id"),
        "record_type": rec.get("record_type") or "finding",
        "work_type": rec.get("work_type"),
        "sector": rec.get("sector"),
        "year": rec.get("year"),
        "org_type": rec.get("org_type"),
        "org_name": rec.get("org_name"),
        "audit_org": rec.get("audit_org"),
        "disposition": rec.get("disposition"),
        "title": title[:200],
        "excerpt": excerpt,
        "search_text": f"{title} {excerpt}"[:800],
        "source_url": rec.get("source_url"),
        "document_url": rec.get("document_url"),
        "text_quality": text_quality(rec),
        "review": bool(rec.get("review")),
        "tag_confidence": rec.get("tag_confidence"),
        "tag_method": rec.get("tag_method"),
        "edu_school": is_edu_school(rec),
        "hide_by_default": is_edu_school(rec),
    }


def shard_key(rec: dict) -> str:
    year = rec.get("year") or "unknown"
    ot = rec.get("org_type") or "unknown"
    return f"{year}__{ot}"


def build(input_path: Path, out_dir: Path, limit: int | None, min_conf_expose: float):
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("input must be a JSON list of findings")
    if limit:
        data = data[:limit]

    shards_dir = out_dir / "shards"
    shards_dir.mkdir(parents=True, exist_ok=True)

    buckets: dict[str, list] = defaultdict(list)
    for rec in data:
        buckets[shard_key(rec)].append(doc_from(rec))

    manifest_shards = []
    quality = Counter()
    wt = Counter()
    years = Counter()
    rtypes = Counter()
    hide_n = 0
    high_trust = 0

    # stable shard ids
    for i, key in enumerate(sorted(buckets.keys())):
        docs = buckets[key]
        sid = f"shard-{i:04d}"
        path = shards_dir / f"{sid}.json"
        payload = {
            "id": sid,
            "key": key,
            "n": len(docs),
            "docs": docs,
            "flexsearch_fields": ["search_text", "title", "excerpt", "org_name", "work_type"],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        manifest_shards.append({
            "id": sid,
            "key": key,
            "file": f"shards/{sid}.json",
            "n": len(docs),
            "bytes": path.stat().st_size,
        })
        for d in docs:
            quality[d["text_quality"]] += 1
            wt[d.get("work_type") or "?"] += 1
            years[str(d.get("year") or "?")] += 1
            rtypes[d.get("record_type") or "?"] += 1
            if d.get("hide_by_default"):
                hide_n += 1
            if (d.get("tag_confidence") or 0) >= min_conf_expose and not d.get("review"):
                high_trust += 1

    manifest = {
        "version": 1,
        "scheme": "A-flexsearch-sharding",
        "source": str(input_path.as_posix()),
        "n_docs": len(data),
        "n_shards": len(manifest_shards),
        "default_filters": {
            "hide_edu_school": True,
            "require_body_for_memo_grounds": True,
            "min_confidence_expose_hint": min_conf_expose,
        },
        "shards": manifest_shards,
        "quality_counts": dict(quality),
        "high_trust_n": high_trust,
        "edu_school_hidden_n": hide_n,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # dashboard pre-agg
    dash = {
        "n_docs": len(data),
        "quality": dict(quality),
        "work_type_top": wt.most_common(15),
        "year_top": years.most_common(20),
        "record_type": dict(rtypes),
        "high_trust_pct": round(100 * high_trust / len(data), 1) if data else 0,
        "edu_school_hidden_n": hide_n,
        "insight": "본문 확보·고신뢰 비중을 늘리면 검토메모 근거 품질이 올라갑니다.",
    }
    (out_dir / "dashboard-agg.json").write_text(json.dumps(dash, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "out": str(out_dir),
        "n_docs": len(data),
        "n_shards": len(manifest_shards),
        "quality": dict(quality),
        "high_trust_pct": dash["high_trust_pct"],
    }, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Build FlexSearch shard index (scheme A)")
    ap.add_argument("--input", required=True, help="Path to findings JSON list")
    ap.add_argument("--out", default="app/data/index", help="Output directory")
    ap.add_argument("--limit", type=int, default=None, help="Optional cap for smoke builds")
    ap.add_argument("--min-conf", type=float, default=0.6, help="High-trust threshold hint")
    args = ap.parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")
    build(input_path, out_dir, args.limit, args.min_conf)


if __name__ == "__main__":
    raise SystemExit(main() or 0)
