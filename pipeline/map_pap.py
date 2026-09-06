# -*- coding: utf-8 -*-
"""pap 자체감사 manifest(_pap_central/_pap_public/_pap_local_edu) → finding 스키마 레코드.

- 처분(dsprqKindList) 복합값(예: '주의ㆍ통보-일반')을 코드북 enum으로 정규화.
- 피감기관명(org_name)으로 org_type(중앙/광역/기초/교육/공공기관) 판별.
- work_type/sector 는 tag.assign_codes(지적사항+감사사항명) 규칙분류 재사용.
- 중복키(dedup_key) 부여: 정규화(피감+지적내용+연도).
출력: data/findings.pap.json (검토 후 findings.json 병합)
"""
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.tag import assign_codes, extract_laws, DISPOSITIONS  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

ROOT = Path(__file__).resolve().parents[1]
ADDED_AT = "2026-09-06"

PAP_DIRS = ["_pap_central", "_pap_public", "_pap_local_edu"]

# 처분 정규화: 원문 토큰 → 코드북 enum
_DISP_MAP = [
    ("중징계", "징계"), ("경징계", "징계"), ("징계", "징계"),
    ("문책", "문책"), ("변상", "변상"),
    ("통보", "통보"), ("주의", "주의"), ("경고", "경고"),
    ("시정", "시정"), ("개선요구", "개선요구"), ("개선", "개선"),
    ("권고", "권고"), ("회수", "회수"), ("환수", "환수"),
    ("고발", "고발"), ("수사", "수사요청"), ("해임", "해임"),
    ("정직", "정직"), ("감봉", "감봉"), ("견책", "견책"),
]
# 심각도 순위(작을수록 심각) — 대표 처분 선택용
_SEVERITY = ["고발", "수사요청", "해임", "정직", "감봉", "견책", "징계", "문책",
             "변상", "환수", "회수", "경고", "시정", "개선요구", "개선", "권고",
             "통보", "주의요구", "주의"]


def normalize_disposition(raw: str | None):
    """복합 처분문자열 → (대표 disposition, 전체 list). 없으면 (None, [])."""
    if not raw:
        return None, []
    found = []
    for tok, mapped in _DISP_MAP:
        if tok in raw and mapped not in found:
            found.append(mapped)
    if not found:
        return None, []
    primary = min(found, key=lambda d: _SEVERITY.index(d) if d in _SEVERITY else 99)
    return primary, found


_EDU_SUF = ("초등학교", "중학교", "고등학교", "유치원", "학교", "교육지원청", "교육청")
_PUB_SUF = ("공사", "공단", "공제회", "재단", "진흥원", "연구원", "연구소", "센터",
            "관리원", "보증", "은행", "병원", "대학교", "대학", "협회", "조합", "공제")
_METRO = ("특별시", "광역시", "특별자치시", "특별자치도", "도청")
_BASIC = ("시청", "군청", "구청")


def guess_org_type(org_name: str | None, audit_org: str | None, clsf_dir: str) -> str:
    n = (org_name or "") + " " + (audit_org or "")
    if any(s in n for s in _EDU_SUF):
        return "교육"
    if clsf_dir == "_pap_public":
        return "공공기관"
    if clsf_dir == "_pap_central":
        # 정부합동감사 피감이 지자체면 그 유형, 아니면 중앙
        if any(s in (org_name or "") for s in _METRO): return "광역"
        if any(s in (org_name or "") for s in _BASIC): return "기초"
        if any(org_name and org_name.endswith(s) for s in ("도","시","군","구")): return "기초"
        return "중앙"
    # _pap_local_edu (지방)
    if any(s in (org_name or "") for s in _PUB_SUF): return "공공기관"
    if any(s in (org_name or "") for s in _METRO): return "광역"
    if org_name and (org_name.endswith("도") or "도교육청" in (audit_org or "")): return "광역"
    if any(s in (org_name or "") for s in _BASIC) or (org_name and org_name.endswith(("시","군","구"))):
        return "기초"
    if "교육청" in (audit_org or ""): return "교육"
    return "기타"


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", "", (s or "")).lower()


def dedup_key(org_name, excerpt, year) -> str:
    base = _norm(org_name) + "|" + _norm(excerpt)[:60] + "|" + str(year or "")
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def map_dir(clsf_dir: str) -> list[dict]:
    mf = ROOT / "data" / "raw_docs" / "자체감사" / clsf_dir / "manifest.json"
    if not mf.exists():
        return []
    items = json.loads(mf.read_text(encoding="utf-8"))
    out = []
    for i, x in enumerate(items):
        excerpt = (x.get("indic_mttr") or "").strip()
        if not excerpt:
            continue
        codes = assign_codes(excerpt + " " + (x.get("source_title") or ""))
        primary, disp_all = normalize_disposition(x.get("disposition_raw"))
        org_name = x.get("org_name")
        audit_org = x.get("audit_org")
        year = x.get("year")
        try: year = int(year)
        except (TypeError, ValueError): year = None
        rec = {
            "id": f"자체감사-pap-{clsf_dir[5:]}-{x.get('plan_uuid','')[:8]}-{i}",
            "record_type": "finding",
            "source": "자체감사",
            "org_type": guess_org_type(org_name, audit_org, clsf_dir),
            "org_name": org_name or (audit_org or "미상"),
            "audit_org": audit_org,
            "work_type": codes["work_type"],
            "sector": codes.get("sector"),
            "audit_type": x.get("audit_type_hint"),
            "finding_type": codes.get("finding_type", codes["work_type"] + "z"),
            "document_url": x.get("document_url"),
            "source_title": x.get("source_title"),
            "posted_date": x.get("posted_date"),
            "summary": None,
            "source_excerpt": excerpt,
            "legal_basis": extract_laws(excerpt),
            "disposition": primary,
            "disposition_all": disp_all or None,
            "disposition_raw": x.get("disposition_raw"),
            "year": year if year else 2024,
            "source_url": x.get("source_url"),
            "added_at": ADDED_AT,
            "_pap_class": clsf_dir[5:],
            "dedup_key": dedup_key(org_name, excerpt, year),
        }
        out.append(rec)
    return out


def main() -> int:
    all_recs = []
    for d in PAP_DIRS:
        recs = map_dir(d)
        print(f"{d}: {len(recs)} 레코드")
        all_recs.extend(recs)
    # pap 내부 중복 제거(dedup_key)
    seen = {}
    for r in all_recs:
        seen.setdefault(r["dedup_key"], r)
    deduped = list(seen.values())
    outp = ROOT / "data" / "findings.pap.json"
    outp.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"총 {len(all_recs)} → pap내부 중복제거 후 {len(deduped)} → {outp.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
