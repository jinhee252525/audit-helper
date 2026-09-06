"""감사원 inbox 전량 태깅 — data/inbox/감사원/ 의 공개문 전문 PDF 전부를
kordoc_extract → parse_cover_meta(출처) → _parse_report(지적분해) → 태깅해
data/findings.json 에 멱등 병합한다.

대상:
  - 최상위 '공개문 전문*.pdf' · '공개문_전문*.pdf' 전부
  - SOC 하위폴더 2건, ICC 하위폴더의 '(국문요약)*.pdf' 2건
  - 2025회계연도 국가결산검사보고서(제1·2권) — 대형(표지·발간일·audit_type 등록 +
    검사결과 지적 best-effort, 실패는 로그)
제외: .zip(이미 해제), ICC '(영문 전문)*.pdf'(국내감사 대상 아님)

출처: source_title·posted_date·audit_type 를 표지에서 추출해 레코드에 채운다.
source_url 은 개별 글 URL이 없어 'https://www.bai.go.kr/' 유지.

원칙: source_excerpt 원문 verbatim, 코드북 코드값만, disposition·법령 원문 근거,
위법단정·무근거요약 금지, pii.mask 적용. 실패 파일은 성공 계상 금지·로그.

사용: PYTHONUTF8=1 python pipeline/run_bai_full.py
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pipeline import tag
from pipeline.kordoc_extract import extract

ROOT = Path(__file__).resolve().parent.parent
BAI_DIR = ROOT / "data" / "inbox" / "감사원"
FINDINGS = ROOT / "data" / "findings.json"
RUNS_DIR = ROOT / "data" / "runs"

REPORT_CAP = 60          # 파일당 지적 상한(폭주 방지)
BIG_BYTES = 8 * 1024 * 1024   # 대형 문서 임계(국가결산 등)
BIG_CAP = 50             # 대형 문서 지적 상한

log_lines: list[str] = []
stats = {"try": 0, "ok": 0, "fail": 0, "records": 0}
failures: list[str] = []


def _log(msg: str) -> None:
    print(msg)
    log_lines.append(msg)


def _year_from(text: str) -> int | None:
    m = re.search(r"(20\d\d)\.\s*\d{1,2}\.", text[:2000])
    return int(m.group(1)) if m else None


def _targets() -> list[Path]:
    """대상 PDF 목록(정렬·중복제거). .zip·영문 전문 제외."""
    seen: dict[str, Path] = {}
    # 1) 최상위 공개문 전문
    for pat in ("공개문 전문*.pdf", "공개문_전문*.pdf"):
        for p in BAI_DIR.glob(pat):
            if p.is_file():
                seen[str(p)] = p
    # 2) SOC 하위폴더
    for p in BAI_DIR.glob("공개문 전문(SOC*/*.pdf"):
        seen[str(p)] = p
    # 3) ICC 하위폴더 — 국문요약만
    for p in BAI_DIR.glob("1.(영문 전문)*/*.pdf"):
        if "(국문요약)" in p.name:
            seen[str(p)] = p
    # 4) 국가결산 하위폴더 — 대형 등록
    for p in BAI_DIR.glob("2025회계연도 국가결산*/*.pdf"):
        seen[str(p)] = p
    return sorted(seen.values(), key=lambda x: str(x))


def _registration_excerpt(md: str) -> str | None:
    """대형 문서에서 지적분해 실패 시, '검사결과' 인근 원문 문장 verbatim 발췌(등록용)."""
    idx = md.find("검사결과")
    region = md[idx: idx + 600] if idx != -1 else md[:600]
    seg = tag._trim_sentence(region)
    seg = seg.strip()
    return seg if len(seg) >= 30 else None


def _process(p: Path) -> list[dict]:
    """파일 1건 → 레코드 리스트. 실패 시 예외."""
    md = extract(str(p))
    cover = tag.parse_cover_meta(md)
    year = _year_from(md) or (int(cover["posted_date"][:4]) if cover.get("posted_date") else 2026)
    base_meta = {
        "source": "감사원",
        "audit_org": "감사원",
        "audit_type": cover.get("audit_type"),
        "source_title": cover.get("source_title"),
        "posted_date": cover.get("posted_date"),
        "year": year,
        "source_url": "https://www.bai.go.kr/",
        "document_url": None,
        "record_type": "finding",
        # dockey: 파일 경로 해시를 붙여 유일화. '공개문 전문 (1)'/'공개문_전문 (1)' 처럼
        # 밑줄·공백만 다른 파일이 _dockey 정규화에서 충돌하는 것을 방지한다.
        "dockey": f"{p.stem}-{hashlib.sha256(str(p).encode('utf-8')).hexdigest()[:8]}",
    }
    is_big = p.stat().st_size >= BIG_BYTES
    cap = BIG_CAP if is_big else REPORT_CAP

    items = tag.parse_document(md, {"doc_kind": "report"})
    records: list[dict] = []
    if items:
        for idx, it in enumerate(items[:cap], 1):
            org = it.get("org_name")
            meta = dict(base_meta, org_name=org or "(미상)", org_type=tag.org_type_of(org))
            records.append(tag.build_record(it, meta, idx))
        return records

    # 지적분해 0건 — 대형/특수는 표지·발간일 등록(대표 원문 발췌 1건)
    excerpt = _registration_excerpt(md)
    if not excerpt:
        raise RuntimeError("지적 0건 + 등록용 발췌 실패")
    meta = dict(base_meta, org_name="(보고서 등록)", org_type="중앙")
    item = {"source_excerpt": excerpt, "disposition": None, "legal_basis": tag.extract_laws(excerpt)}
    records.append(tag.build_record(item, meta, 1))
    return records


def main() -> int:
    targets = _targets()
    _log(f"# 감사원 전량 태깅 — {date.today().isoformat()}")
    _log(f"대상 파일: {len(targets)}건\n")

    all_recs: list[dict] = []
    for p in targets:
        stats["try"] += 1
        try:
            recs = _process(p)
            if not recs:
                stats["fail"] += 1
                failures.append(f"{p.name}: 레코드 0건")
                _log(f"  ✖ {p.name}: 레코드 0건")
                continue
            all_recs.extend(recs)
            stats["ok"] += 1
            stats["records"] += len(recs)
            ct = recs[0]
            _log(f"  ✔ {p.name}: {len(recs)}건 | {ct.get('source_title')} | {ct.get('posted_date')} | {ct.get('audit_type')}")
        except Exception as e:  # noqa: BLE001
            stats["fail"] += 1
            failures.append(f"{p.name}: {type(e).__name__} {e}")
            _log(f"  ✖ {p.name}: {type(e).__name__} {e}")

    # 초기 데모(run_demo_tagging)가 넣은 감사원 지적(record_type=finding)은 이 전량 처리로
    # 출처(source_title 등)까지 채운 버전으로 대체된다. 중복을 막기 위해 병합 전에 제거한다.
    # (ALIO 지적·감사원 사전컨설팅 consult 는 그대로 유지)
    existing = json.loads(FINDINGS.read_text(encoding="utf-8")) if FINDINGS.exists() else []
    before = len(existing)
    kept = [r for r in existing if not (r.get("source") == "감사원" and r.get("record_type") == "finding")]
    dropped = before - len(kept)
    if dropped:
        FINDINGS.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")

    res = tag.merge_incremental(all_recs)
    _log("")
    _log(f"병합: 신규 {res['added']} · 전체 {res['total']} · 스킵 {res['skipped']} · 기존 감사원 지적 대체 {dropped}건")
    _log(f"파일 시도/성공/실패: {stats['try']}/{stats['ok']}/{stats['fail']} · 생성 레코드 {stats['records']}")
    if failures:
        _log("\n## 실패 파일")
        for f in failures:
            _log(f"  - {f}")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / f"{date.today().isoformat()}-감사원.md").write_text(
        "\n".join(log_lines) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
