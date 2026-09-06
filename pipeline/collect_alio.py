"""ALIO 지적사항 수집 어댑터 (source-collector용) — 인증키 없이 공개 JSON 사용.

발견한 공개 엔드포인트(키 없음):
  https://www.alio.go.kr/occasional/findPointList.json
    ?type=title&word=&sortType=&reportFormNo=B1220&countPerPage=N&pageNo=P
반환: data.result[] (레코드), data.totalCnt(전체건수), data.page

원문(rtitle)에는 지적내용 + 처분(괄호표기)이 함께 담겨 있어 태깅 입력으로 적합.
이 스크립트는 '원문 확보'까지만 한다(스키마 태깅은 record-tagger/structure.py).

사용:
  python pipeline/collect_alio.py --limit 200        # 최근 200건 raw 저장
  python pipeline/collect_alio.py --limit 3284       # 전체
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests  # 고정 공개 엔드포인트 호출(키 없음). file:// 등 위험 스킴 미지원으로 안전.

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_docs" / "alio"
ALLOWED_HOST = "https://www.alio.go.kr"
BASE = ALLOWED_HOST + "/occasional/findPointList.json"
LIST_PAGE = ALLOWED_HOST + "/occasional/auditPointList.do"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": LIST_PAGE}


def fetch_page(page_no: int, per_page: int) -> dict:
    # 파라미터는 정수만 사용하고, 호출 URL은 고정 공개 엔드포인트(ALLOWED_HOST)로 한정.
    assert BASE.startswith(ALLOWED_HOST), "허용된 공개 호스트만 호출"
    params = {
        "type": "title", "word": "", "sortType": "",
        "reportFormNo": "B1220",
        "countPerPage": int(per_page), "pageNo": int(page_no),
    }
    r = requests.get(BASE, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()["data"]


# 법령 추출용 정규식: 「...법/령/규칙/규정/조례/지침/기준」 및 따옴표 없는 ○○법 시행령 등
LAW_RE = re.compile(
    r"[「『]([^」』]{2,40}?(?:법|법률|법 시행령|법 시행규칙|령|규칙|규정|조례|지침|기준|훈령|예규|고시))[」』]"
)


def extract_laws(text: str) -> list[dict]:
    """rtitle 등 원문에서 인용된 법령명을 추출(1차 legal_basis 후보). HWP 파싱 시 정밀화."""
    laws: list[dict] = []
    seen = set()
    for m in LAW_RE.finditer(text or ""):
        name = m.group(1).strip()
        if name and name not in seen:
            seen.add(name)
            lt = "자치법규" if "조례" in name else ("행정규칙" if any(k in name for k in ["규정", "지침", "훈령", "예규", "고시", "규칙"]) else "법령")
            laws.append({"law": name, "article": None, "law_type": lt})
    return laws


def to_meta(it: dict, page: int) -> dict:
    sub = it.get("submissionNo") or f"p{page}-{it.get('rnum')}"
    year = (it.get("enfcBgngYmd") or it.get("idate") or "")[:4]
    rtitle = it.get("rtitle", "")
    return {
        "source": "ALIO",
        "org_type": "공공기관",
        "org_name": it.get("pname") or it.get("apbaNa"),
        "year": int(year) if year.isdigit() else None,
        "source_url": LIST_PAGE,
        "submission_no": sub,
        "audit_period": f"{it.get('enfcBgngYmd','')}~{it.get('enfcEndYmd','')}",
        "rtitle": rtitle,
        "legal_basis_raw": extract_laws(rtitle),
        "files": [it.get(k) for k in ("filedata1", "filedata2", "filedata3") if it.get(k)],
        "_raw": it,
    }


def _load_seen_ids() -> set[str]:
    """state.json 의 seen_ids(=이미 수집한 submissionNo) 로드. 없으면 빈 집합."""
    state = ROOT / "data" / "state.json"
    if not state.exists():
        return set()
    try:
        s = json.loads(state.read_text(encoding="utf-8"))
        return set(s.get("seen_ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def collect(limit: int, per_page: int = 100, min_year: int | None = None,
            combined_out: Path | None = None, incremental: bool = False) -> list[dict]:
    RAW.mkdir(parents=True, exist_ok=True)
    collected: list[dict] = []
    seen_ids = _load_seen_ids() if incremental else set()
    if incremental:
        print(f"  증분 모드: 기존 seen_ids {len(seen_ids)}건 — 최신순 목록에서 기존 id 만나면 중단")
    page = 1
    total = None
    stop = False
    while len(collected) < limit and not stop:
        d = fetch_page(page, per_page)
        total = d.get("totalCnt", total)
        rows = d.get("result", [])
        if not rows:
            break
        for it in rows:
            if len(collected) >= limit:
                break
            meta = to_meta(it, page)
            # 증분: 최신순 목록에서 이미 본 submissionNo 를 만나면 그 지점부터 전부 기존분 → 중단
            if incremental and str(meta["submission_no"]) in seen_ids:
                print(f"  증분 중단: 기존 id {meta['submission_no']} 도달 (누적 {len(collected)})")
                stop = True
                break
            if min_year and (meta["year"] or 0) < min_year:
                continue  # 5년 필터
            collected.append(meta)
        print(f"  page {page}: 누적 {len(collected)} (스캔 {page*per_page}/{total})")
        page += 1
        time.sleep(0.3)
    if combined_out:
        combined_out.write_text(json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  통합 저장: {combined_out.relative_to(ROOT)}")
    return collected


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--all", action="store_true", help="전량 수집(전체 건수만큼)")
    ap.add_argument("--min-year", type=int, default=None, help="이 연도 이상만(예: 2021)")
    ap.add_argument("--per-page", type=int, default=100)
    ap.add_argument("--incremental", action="store_true",
                    help="증분 수집: state.json seen_ids 로 기존분 만나면 중단(매일 배치용)")
    ap.add_argument("--out", type=str, default="data/raw_docs/alio_5yr.json")
    args = ap.parse_args()
    limit = 10_000 if args.all else args.limit
    out = (ROOT / args.out) if args.out else None
    print(f"ALIO 지적사항 수집 시작 (키 없음) — limit={limit} min_year={args.min_year} incremental={args.incremental}")
    recs = collect(limit, args.per_page, args.min_year, out, incremental=args.incremental)
    print(f"완료: {len(recs)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
