"""확보된 raw 소스 전량 태깅 → data/findings.json 멱등 병합.

소스:
  1) ALIO 3년(alio_3yr.json, 1093) — 기존 ALIO 경로(doc_kind='alio', rtitle 분해).
     id 스킴 동일 → 기존 60건은 멱등 스킵, 나머지 추가.
  2) 국회결산(nabo_3yr.json, 6200) — map_nabo 매퍼(정형 → 스키마 매핑).
  3) 권익위 자체감사(raw_docs/자체감사/acrc, 5 PDF) — kordoc → _parse_report → 태깅.
     메타(_meta/건별 json)의 source_title·posted_date·source_url·document_url 채움.

원칙: source_excerpt 원문 verbatim(pii.mask만), 코드북 코드값만, disposition·법령 원문 근거,
위법단정·무근거요약 금지. 실패는 로그(성공 계상 금지). merge_incremental로 중복 0 멱등 병합.

사용: PYTHONUTF8=1 python pipeline/run_ingest_sources.py
"""
from __future__ import annotations
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pipeline import tag, map_nabo
from pipeline.kordoc_extract import extract

ROOT = Path(__file__).resolve().parent.parent
ALIO_JSON = ROOT / "data" / "raw_docs" / "alio_3yr.json"
NABO_JSON = ROOT / "data" / "raw_docs" / "nabo_3yr.json"
ACRC_DIR = ROOT / "data" / "raw_docs" / "자체감사" / "acrc"
FINDINGS = ROOT / "data" / "findings.json"
RUNS_DIR = ROOT / "data" / "runs"

ACRC_CAP = 60   # 파일당 지적 상한(폭주 방지)

log_lines: list[str] = []
failures: list[str] = []


def _log(msg: str) -> None:
    print(msg)
    log_lines.append(msg)


# ── 1) ALIO 전량 ──────────────────────────────────────────────────────────────
def _alio_audit_type(rec: dict) -> str | None:
    files = " ".join(rec.get("files") or [])
    for at in tag.AUDIT_TYPES:
        if at in files or at in rec.get("rtitle", ""):
            return at
    return None


def do_alio() -> list[dict]:
    docs = json.loads(ALIO_JSON.read_text(encoding="utf-8"))
    records: list[dict] = []
    ok = fail = skip = 0
    for rec in docs:
        if not rec.get("org_name") or not rec.get("year") or not rec.get("rtitle"):
            skip += 1
            continue
        try:
            meta = {
                "doc_kind": "alio",
                "source": "ALIO",
                "org_type": "공공기관",
                "org_name": rec["org_name"],
                "audit_org": None,
                "audit_type": _alio_audit_type(rec),
                "year": rec["year"],
                "source_url": rec["source_url"],
                "document_url": None,
                "record_type": "finding",
                "dockey": rec["submission_no"],
            }
            items = tag.parse_document(rec["rtitle"], meta)
            if not items:
                fail += 1
                continue
            for idx, it in enumerate(items, 1):
                records.append(tag.build_record(it, meta, idx))
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            failures.append(f"ALIO {rec.get('submission_no')}: {type(e).__name__} {e}")
    _log(f"[ALIO] 문서 {len(docs)} · 성공 {ok} · 실패 {fail} · 스킵 {skip} → 레코드 {len(records)}")
    return records


# ── 2) 국회결산(NABO) ─────────────────────────────────────────────────────────
def do_nabo() -> list[dict]:
    raws = json.loads(NABO_JSON.read_text(encoding="utf-8"))
    records = map_nabo.map_records(raws)
    _log(f"[국회결산] raw {len(raws)} → 레코드 {len(records)}")
    return records


# ── 3) 권익위 자체감사(ACRC) ──────────────────────────────────────────────────
def do_acrc() -> list[dict]:
    records: list[dict] = []
    metas = sorted(ACRC_DIR.glob("acrc_*.json"))
    ok = fail = 0
    for mp in metas:
        m = json.loads(mp.read_text(encoding="utf-8"))
        pdf = ROOT / m["local_file"]
        if not pdf.exists():
            pdf = mp.with_suffix(".pdf")
        try:
            md = extract(str(pdf))
            base_meta = {
                "source": "자체감사",
                "org_type": "중앙",
                "org_name": "국민권익위원회",
                "audit_org": m.get("audit_org"),
                "audit_type": tag._audit_type_from(md),
                "year": m.get("year"),
                "source_title": m.get("source_title"),
                "posted_date": m.get("posted_date"),
                "source_url": m.get("source_url"),
                "document_url": m.get("document_url"),
                "record_type": "finding",
                "dockey": pdf.stem,
            }
            items = tag.parse_document(md, {"doc_kind": "report"})
            if not items:
                fail += 1
                failures.append(f"ACRC {pdf.name}: 지적 0건")
                _log(f"  ✖ {pdf.name}: 지적 0건")
                continue
            for idx, it in enumerate(items[:ACRC_CAP], 1):
                # 피감기관은 항상 국민권익위원회(자체감사) — item org_name 무시
                records.append(tag.build_record(it, base_meta, idx))
            ok += 1
            _log(f"  ✔ {pdf.name}: {min(len(items), ACRC_CAP)}건 | {m.get('source_title')} | {m.get('posted_date')}")
        except Exception as e:  # noqa: BLE001
            fail += 1
            failures.append(f"ACRC {pdf.name}: {type(e).__name__} {e}")
            _log(f"  ✖ {pdf.name}: {type(e).__name__} {e}")
    _log(f"[자체감사] PDF {len(metas)} · 성공 {ok} · 실패 {fail} → 레코드 {len(records)}")
    return records


def main() -> int:
    _log(f"# raw 소스 전량 태깅 — {date.today().isoformat()}")
    alio = do_alio()
    nabo = do_nabo()
    acrc = do_acrc()

    all_recs = alio + nabo + acrc
    # ALIO submissionNo 를 seen_ids 에 축적(다음 collect_alio 증분용)
    alio_subs = sorted({r["id"].split("-")[2] for r in alio}) if alio else None
    res = tag.merge_incremental(all_recs, seen_source_ids=alio_subs)
    _log("")
    _log(f"병합: 신규 {res['added']} · 전체 {res['total']} · 스킵 {res['skipped']}")
    _log(f"소스별 생성 레코드 — ALIO {len(alio)} · 국회결산 {len(nabo)} · 자체감사 {len(acrc)}")
    if failures:
        _log(f"\n## 실패 {len(failures)}건")
        for f in failures[:50]:
            _log(f"  - {f}")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / f"{date.today().isoformat()}-ingest-sources.md").write_text(
        "\n".join(log_lines) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
