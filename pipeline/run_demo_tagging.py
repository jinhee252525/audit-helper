"""데모 태깅 실행 — 실데이터 3소스를 태깅해 data/findings.json 생성.

소스:
  1) ALIO      — data/raw_docs/alio_5yr.json 표본(문서 누적 ~60 지적)
  2) 감사원     — data/inbox/감사원/ PDF 3개(kordoc→파싱)  record_type=finding
  3) 사전컨설팅 — data/inbox/사전컨설팅/ PDF 1개(kordoc→폴백→파싱) record_type=consult

의미분류(work_type/sector/finding_type)는 규칙(tag.assign_codes) 기본 + 명백한 오배정만
드라이버에서 판단 보정(_OVERRIDE). source_excerpt 는 원문 verbatim(무근거 차단).

사용: PYTHONUTF8=1 python pipeline/run_demo_tagging.py
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pipeline import tag
from pipeline.kordoc_extract import extract

ROOT = Path(__file__).resolve().parent.parent
ALIO_JSON = ROOT / "data" / "raw_docs" / "alio_5yr.json"
BAI_DIR = ROOT / "data" / "inbox" / "감사원"
CONSULT_PDF = ROOT / "data" / "inbox" / "사전컨설팅" / "2025 사전컨설팅 사례집.pdf"

BAI_FILES = ["공개문 전문 (1).pdf", "공개문 전문 (3).pdf", "공개문 전문 (5).pdf"]
ALIO_TARGET = 60            # 목표 지적(레코드) 수
CONSULT_TAKE = 8           # 사전컨설팅 표본 사례 수

# 의미분류 판단 보정(=이 Claude의 판단): 규칙이 놓치거나 어긋난 건만 codebook 코드로 교정.
# - 환경표지 '인증' → 검정·평가(01)/인증(01b)
# - 이해충돌·금품요구(청렴) 지적은 관련기능 19종에 해당 기능 없음 → 기타(19z)
# - 디젤발전기 '구매' → 물품계약(02c)
_OVERRIDE: dict[str, dict] = {
    "감사원-2024-공개문전문3-2": {"work_type": "01", "sector": "18", "finding_type": "01b"},
    "감사원-2024-공개문전문5-1": {"work_type": "19", "sector": None, "finding_type": "19z"},
    "감사원-2024-공개문전문5-2": {"work_type": "19", "sector": None, "finding_type": "19z"},
    "감사원-2024-공개문전문5-3": {"work_type": "02", "sector": None, "finding_type": "02c"},
    # 사전컨설팅(consult): 회신 주제 기준 판단 보정
    "감사원-2025-consult2025-1": {"work_type": "18", "sector": None, "finding_type": "18a"},  # 위탁수수료
    "감사원-2025-consult2025-4": {"work_type": "15", "sector": None, "finding_type": "15c"},  # 국가장학금 지원
    "감사원-2025-consult2025-6": {"work_type": "11", "sector": None, "finding_type": "11z"},  # 계약직 보수(직무급)
}

stats = {"alio": {"try": 0, "ok": 0, "fail": 0},
         "bai": {"try": 0, "ok": 0, "fail": 0},
         "consult": {"try": 0, "ok": 0, "fail": 0}}


def _alio_audit_type(rec: dict) -> str | None:
    files = " ".join(rec.get("files") or [])
    for at in tag.AUDIT_TYPES:
        if at in files or at in rec.get("rtitle", ""):
            return at
    return None


def do_alio() -> list[dict]:
    docs = json.loads(ALIO_JSON.read_text(encoding="utf-8"))
    records: list[dict] = []
    for rec in docs:
        if len(records) >= ALIO_TARGET:
            break
        if not rec.get("org_name") or not rec.get("year"):
            continue
        stats["alio"]["try"] += 1
        try:
            meta = {
                "doc_kind": "alio",
                "source": "ALIO",
                "org_type": "공공기관",
                "org_name": rec["org_name"],
                "audit_org": None,             # ALIO 목록엔 감사기관 명시 없음
                "audit_type": _alio_audit_type(rec),
                "year": rec["year"],
                "source_url": rec["source_url"],
                "document_url": None,
                "record_type": "finding",
                "dockey": rec["submission_no"],
            }
            items = tag.parse_document(rec["rtitle"], meta)
            if not items:
                stats["alio"]["fail"] += 1
                continue
            for idx, it in enumerate(items, 1):
                if len(records) >= ALIO_TARGET:
                    break
                records.append(tag.build_record(it, meta, idx))
            stats["alio"]["ok"] += 1
        except Exception as e:  # noqa: BLE001
            stats["alio"]["fail"] += 1
            print(f"  ALIO 실패 {rec.get('submission_no')}: {type(e).__name__} {e}")
    return records


def do_bai() -> list[dict]:
    records: list[dict] = []
    for fn in BAI_FILES:
        p = BAI_DIR / fn
        stats["bai"]["try"] += 1
        try:
            md = extract(str(p))
            at = tag._audit_type_from(md)
            items = tag.parse_document(md, {"doc_kind": "report"})
            if not items:
                stats["bai"]["fail"] += 1
                print(f"  감사원 파싱 0건: {fn}")
                continue
            for idx, it in enumerate(items, 1):
                org = it.get("org_name")
                meta = {
                    "source": "감사원",
                    "org_type": tag.org_type_of(org),
                    "org_name": org or "(미상)",
                    "audit_org": "감사원",
                    "audit_type": at,
                    "year": _year_from(md) or 2026,
                    "source_url": "https://www.bai.go.kr/",
                    "document_url": None,
                    "record_type": "finding",
                    "dockey": p.stem,
                }
                records.append(tag.build_record(it, meta, idx))
            stats["bai"]["ok"] += 1
        except Exception as e:  # noqa: BLE001
            stats["bai"]["fail"] += 1
            print(f"  감사원 실패 {fn}: {type(e).__name__} {e}")
    return records


def _year_from(text: str) -> int | None:
    m = re.search(r"(20\d\d)\.\s*\d{1,2}\.", text[:2000])
    return int(m.group(1)) if m else None


def do_consult() -> list[dict]:
    records: list[dict] = []
    stats["consult"]["try"] += 1
    try:
        text = extract(str(CONSULT_PDF))
        items = tag.parse_document(text, {"doc_kind": "consult"})
        if not items:
            stats["consult"]["fail"] += 1
            return records
        for idx, it in enumerate(items[:CONSULT_TAKE], 1):
            meta = {
                "source": "감사원",
                "org_type": "기타",
                "org_name": "(사례집·신청기관 비공개)",
                "audit_org": "감사원",
                "audit_type": None,
                "year": 2025,
                "source_url": "https://www.bai.go.kr/",
                "document_url": None,
                "record_type": "consult",
                "dockey": "consult2025",
            }
            records.append(tag.build_record(it, meta, idx))
        stats["consult"]["ok"] += 1
    except Exception as e:  # noqa: BLE001
        stats["consult"]["fail"] += 1
        print(f"  사전컨설팅 실패: {type(e).__name__} {e}")
    return records


def main() -> int:
    print("[1/3] ALIO 태깅 …")
    alio = do_alio()
    print(f"  → {len(alio)} 레코드")
    print("[2/3] 감사원 태깅 …")
    bai = do_bai()
    print(f"  → {len(bai)} 레코드")
    print("[3/3] 사전컨설팅 태깅 …")
    consult = do_consult()
    print(f"  → {len(consult)} 레코드")

    all_recs = alio + bai + consult
    # 판단 보정 적용(의미분류만 교정, 원문·처분·법령은 불변)
    for r in all_recs:
        ov = _OVERRIDE.get(r["id"])
        if ov:
            r.update(ov)
    # ALIO submissionNo 를 seen_ids 에 기록 → 다음 collect_alio --incremental 이 기존분 건너뜀
    alio_subs = sorted({r["id"].split("-")[2] for r in alio})
    res = tag.merge_incremental(all_recs, seen_source_ids=alio_subs)
    print(f"\n병합: 신규 {res['added']} · 전체 {res['total']} · 스킵 {res['skipped']}")
    print("소스별 시도/성공/실패:", json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
