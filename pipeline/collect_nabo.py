"""국회 결산 시정요구 및 조치결과 수집 어댑터 (source-collector용) — 인증키 없이 공개 AJAX 사용.

배경: NABOSTATS 오픈API(openApiGuideCdPage.do 등)는 통계코드(총괄 집계) 위주이며,
개별 시정요구 건의 '지적 내용' 원문은 담고 있지 않다. 브라우저 네트워크 정찰 결과,
결산시정요구 페이지(naboEvaluationHis5Page.do) 자체가 아래의 **공개 AJAX 엔드포인트**
(로그인·인증키 불필요, 페이지가 쓰는 것과 동일한 호출)로 개별 건을 제공한다:

  목록: POST https://www.nabostats.go.kr/portal/nabo/searchNaboEvaluationHisBbsList.do
        form: page, rows, bbsCd=NABOC, bCheckType(I/D/R/C/B 체크박스, 빈값=전체),
              bListSelect=<회계연도>, bSearchColumn=, bSearchWord=
        응답: {"total":N,"pages":N,"data":[{seq,listSubCd(연도),list1SubNm(유형: 제도개선/주의/시정/징계/변상),
              cmteNm(소관위원회), tgtOrgNm(조치대상기관), bbsTit(제목), refTit(사업명),
              bbsCont(지적사항 원문), ans2StateNm(조치상황)}, ...]}

  단건 상세(선택): POST https://www.nabostats.go.kr/portal/nabo/searchNaboAnalysisOne.do
        form: bbsCd=NABOC&seq=<seq>
        응답에 refCont(시정요구사항), ansCont(1차 조치결과), ans2Cont(후속조치결과) 등 추가.
        건별 호출이라 전량 수집 시 매우 느림 — 기본은 목록(bbsCont)까지만 저장.

CLAUDE.md 데이터 정책: 수집에 API 키를 쓰지 않는다 — 이 엔드포인트는 인증키가 필요 없는
공개 페이지 백엔드이므로 원칙에 부합한다(.env의 NABOSTATS_KEY는 사용하지 않음).

이 스크립트는 '원문 확보'까지만 한다(스키마 태깅은 record-tagger/structure.py 몫).

사용:
  python pipeline/collect_nabo.py --years 2024 2023 2022
  python pipeline/collect_nabo.py --years 2024 --detail   # 상세(조치결과) 포함, 느림
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_docs" / "nabo"
ALLOWED_HOST = "https://www.nabostats.go.kr"
LIST_URL = ALLOWED_HOST + "/portal/nabo/searchNaboEvaluationHisBbsList.do"
DETAIL_URL = ALLOWED_HOST + "/portal/nabo/searchNaboAnalysisOne.do"
PAGE_URL = ALLOWED_HOST + "/portal/nabo/naboEvaluationHis5Page.do"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": PAGE_URL,
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


def fetch_list_page(year: int, page: int, rows: int = 100) -> dict:
    assert LIST_URL.startswith(ALLOWED_HOST), "허용된 공개 호스트만 호출"
    body = {
        "page": page, "rows": rows, "bbsCd": "NABOC",
        "bCheckType": "", "bCheckTypeI": "I", "bCheckTypeD": "D",
        "bCheckTypeR": "R", "bCheckTypeC": "C", "bCheckTypeB": "B",
        "bListSelect": year, "bSearchColumn": "", "bSearchWord": "",
    }
    r = requests.post(LIST_URL, data=body, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_detail(seq: int) -> dict:
    assert DETAIL_URL.startswith(ALLOWED_HOST)
    r = requests.post(DETAIL_URL, data={"bbsCd": "NABOC", "seq": seq}, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("data", {})


def to_meta(it: dict, year: int, detail: dict | None = None) -> dict:
    meta = {
        "source": "NABO",
        "org_type": "중앙행정기관",  # tgtOrgNm 이 실제 소관기관; 국회결산 시정요구 성격상 기본값
        "org_name": it.get("tgtOrgNm"),
        "year": year,
        "source_url": PAGE_URL,
        "seq": it.get("seq"),
        "committee": it.get("cmteNm"),
        "finding_type": it.get("list1SubNm"),  # 시정/주의/제도개선/징계/변상
        "title": it.get("bbsTit"),
        "program_ref": it.get("refTit"),
        "finding_text": it.get("bbsCont"),  # 지적사항 원문
        "action_status": it.get("ans2StateNm"),
        "_raw_list": it,
    }
    if detail:
        meta["remedy_request_text"] = detail.get("refCont")  # 시정요구사항
        meta["action_result_text"] = detail.get("ansCont")  # 1차 조치결과
        meta["followup_result_text"] = detail.get("ans2Cont")  # 후속 조치결과
        meta["reg_dttm"] = detail.get("regDttm")
        meta["_raw_detail"] = detail
    return meta


def collect_year(year: int, rows: int = 100, with_detail: bool = False,
                  detail_sleep: float = 0.25, limit: int | None = None) -> list[dict]:
    collected: list[dict] = []
    page = 1
    total = None
    while True:
        d = fetch_list_page(year, page, rows)
        total = d.get("total", total)
        rows_data = d.get("data", [])
        if not rows_data:
            break
        for it in rows_data:
            detail = None
            if with_detail:
                try:
                    detail = fetch_detail(it["seq"])
                    time.sleep(detail_sleep)
                except Exception as e:  # noqa: BLE001
                    print(f"    상세 실패 seq={it.get('seq')}: {e}")
            collected.append(to_meta(it, year, detail))
            if limit and len(collected) >= limit:
                break
        print(f"  {year} page {page}: 누적 {len(collected)} / total {total}")
        if limit and len(collected) >= limit:
            break
        if page * rows >= (total or 0):
            break
        page += 1
        time.sleep(0.3)
    return collected


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=[2024, 2023, 2022],
                     help="수집할 회계연도 목록(사이트 상 최신은 2024)")
    ap.add_argument("--rows", type=int, default=100)
    ap.add_argument("--detail", action="store_true", help="건별 상세(조치결과 등) 추가 수집(느림)")
    ap.add_argument("--limit-per-year", type=int, default=None, help="테스트용 연도별 상한")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    all_records: list[dict] = []
    summary = {}
    for year in args.years:
        print(f"[NABO] {year}회계연도 수집 시작 (키 없음, detail={args.detail})")
        try:
            recs = collect_year(year, args.rows, args.detail, limit=args.limit_per_year)
        except Exception as e:  # noqa: BLE001
            print(f"  실패: {year}: {e}")
            summary[year] = {"status": "failed", "error": str(e)}
            continue
        out = RAW / f"nabo_{year}.json"
        out.write_text(json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  저장: {out.relative_to(ROOT)} ({len(recs)}건)")
        all_records.extend(recs)
        summary[year] = {"status": "ok", "count": len(recs)}

    combined = RAW.parent / "nabo_3yr.json"
    combined.write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[NABO] 통합 저장: {combined.relative_to(ROOT)} (총 {len(all_records)}건)")
    print("[NABO] 연도별 요약:", json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
