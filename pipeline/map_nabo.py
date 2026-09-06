"""국회결산(NABO) 매퍼 — 이미 정형화된 raw 레코드 → finding.schema.json 레코드.

nabo_3yr.json 의 각 항목은 이미 조치대상기관·회계연도·지적원문(finding_text)·유형이
분리돼 있으므로 별도 문서파싱 없이 '매핑'만 한다.

매핑 규칙:
- source='국회결산', record_type='finding', audit_type=None(국회 결산심사 — 감사종류 아님).
- org_name=조치대상기관(raw org_name), org_type=org_name으로 추정(tag.org_type_of).
- source_excerpt=finding_text 원문 그대로(verbatim, pii.mask만 적용). 없으면 title.
- disposition: raw finding_type → codebook disposition.
  시정→시정, 주의→주의, 제도개선→개선요구, 징계→징계. 복합은 첫 codebook 값. 밖이면 None.
- work_type/sector/finding_type: finding_text로 tag.assign_codes(규칙) 적용(코드북 코드값만).
- legal_basis: finding_text의 「」 인용 법령(tag.extract_laws).
- id: 국회결산-{year}-{seq}. committee 보존.

원칙: source_excerpt verbatim, 코드북 코드값만, 무근거 부여 금지, 위법 단정 금지.
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
from pipeline.pii import mask

ROOT = Path(__file__).resolve().parent.parent
NABO_JSON = ROOT / "data" / "raw_docs" / "nabo_3yr.json"

# raw finding_type 토큰 → codebook disposition. 코드북 밖(예: 제도개선)은 매핑값으로 치환.
_DISP_MAP = {
    "시정": "시정",
    "주의": "주의",
    "제도개선": "개선요구",
    "징계": "징계",
}


def _disposition(finding_type: str | None) -> str | None:
    """복합 유형은 등장 순서상 첫 codebook 값. 매핑 밖이면 None."""
    if not finding_type:
        return None
    hits = [(finding_type.find(k), v) for k, v in _DISP_MAP.items() if k in finding_type]
    if not hits:
        return None
    hits.sort()
    return hits[0][1]


def _org_name(raw_name: str | None) -> str | None:
    """복수기관(줄바꿈 구분)은 ', '로 합침. 공백 정리."""
    if not raw_name:
        return None
    parts = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"[\r\n]+", raw_name)]
    parts = [p for p in dict.fromkeys(parts) if p]
    return ", ".join(parts) or None


def build_nabo_record(raw: dict) -> dict | None:
    """raw NABO 레코드 → 스키마 레코드. 필수값 없으면 None."""
    year = raw.get("year")
    seq = raw.get("seq")
    if year is None or seq is None:
        return None
    org_name = _org_name(raw.get("org_name"))
    if not org_name:
        return None
    finding_text = (raw.get("finding_text") or "").strip()
    title = (raw.get("title") or "").strip()
    excerpt_src = finding_text or title
    if not excerpt_src:
        return None
    codes = tag.assign_codes(excerpt_src)
    rec = {
        "id": f"국회결산-{year}-{seq}",
        "record_type": "finding",
        "source": "국회결산",
        "org_type": tag.org_type_of(org_name.split(",")[0].strip()),
        "org_name": org_name,
        "audit_org": "국회(국회예산정책처 결산심사)",
        "work_type": codes["work_type"],
        "sector": codes.get("sector"),
        "audit_type": None,
        "finding_type": codes.get("finding_type", codes["work_type"] + "z"),
        "document_url": None,
        "source_title": title or None,
        "posted_date": None,
        "summary": None,
        "source_excerpt": mask(excerpt_src),
        "legal_basis": tag.extract_laws(finding_text),
        "disposition": _disposition(raw.get("finding_type")),
        "year": year,
        "source_url": raw.get("source_url"),
        "added_at": tag.ADDED_AT,
        "committee": raw.get("committee"),
    }
    return rec


def map_records(raws: list[dict]) -> list[dict]:
    out: list[dict] = []
    for raw in raws:
        rec = build_nabo_record(raw)
        if rec is not None:
            out.append(rec)
    return out


def main() -> int:
    raws = json.loads(NABO_JSON.read_text(encoding="utf-8"))
    records = map_records(raws)
    print(f"NABO raw {len(raws)} → 매핑 레코드 {len(records)}")
    res = tag.merge_incremental(records)
    print(f"병합: 신규 {res['added']} · 전체 {res['total']} · 스킵 {res['skipped']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
