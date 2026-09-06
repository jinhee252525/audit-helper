"""자체감사(중앙부처) 게시판 수집 어댑터 - 인증키 없이 공개 게시판만 사용.

대상: 전자정부 표준 게시판(board.es?mid=...&bid=...) 패턴을 쓰는 부처.
설정: data/selfaudit_sources.json 의 sources[] 중 cms_type == "board.es" 인 항목만
      이 스크립트가 자동 처리한다. 그 외(custom_*, not_found 등)는 board_note에
      기록된 별도 파서가 필요하며 이 스크립트의 범위 밖이다.

이 스크립트는 '원문 목록/본문 확보'까지만 한다. 스키마 태깅(finding.schema.json 매핑)은
record-tagger 단계(audit-tagging 스킬)에서 별도로 수행한다.

절대 금지: data/findings.json, pipeline/tag.py, data/state.json 은 이 스크립트가 건드리지
않는다. 증분 상태는 이 스크립트 전용 파일 data/selfaudit_state.json 에 별도 보관한다.

사용:
  python pipeline/collect_selfaudit.py --org mohw --limit 20
  python pipeline/collect_selfaudit.py --all --limit 20   # sources.json의 board.es 항목 전체
  python pipeline/collect_selfaudit.py --org acrc --dry-run  # 목록만 확인, 저장 안 함
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests  # 설정 파일에 명시된 base_url(고정 정부 도메인)만 호출.

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "data" / "selfaudit_sources.json"
STATE_FILE = ROOT / "data" / "selfaudit_state.json"  # 이 스크립트 전용 (data/state.json과 별개)
RAW_ROOT = ROOT / "data" / "raw_docs" / "자체감사"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; audit-helper-selfaudit-collector/1.0)"}

# board.es 목록 페이지의 행(row) 패턴: act=view&list_no=NNNN 링크와 그 주변 텍스트(제목/날짜) 추출.
# 사이트마다 마크업이 조금씩 다르므로 관대한 패턴을 쓰고, 후처리로 정제한다.
LIST_LINK_RE = re.compile(
    r"act=view[^\"'>]*?list_no=(\d+)[^\"'>]*[\"'][^>]*>\s*([^<]{2,150})", re.IGNORECASE
)
# 신형 게시판 스킨(예: mods.go.kr): <a onclick="goView('123456'); ...><span>...(주석/뱃지)...제목텍스트</span></a>
# 링크와 제목 텍스트 사이에 HTML 주석/장식 span이 많이 끼어 있어 블록 단위로 찾는다.
GOVIEW_BLOCK_RE = re.compile(
    r"goView\('(\d+)'\)[\s\S]{0,50}?<span>([\s\S]{0,2000}?)</span></a>", re.IGNORECASE
)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
TAG_RE = re.compile(r"<[^>]+>")
DATE_RE = re.compile(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _load_sources() -> list[dict]:
    data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    return data.get("sources", [])


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _decode(content: bytes) -> str:
    """정부 게시판은 UTF-8/EUC-KR이 혼재하고 Content-Type이 부정확한 경우가 많아,
    UTF-8 디코드를 우선 시도하고 실패하면 EUC-KR로 대체한다(requests.apparent_encoding은
    이 사이트들에서 종종 오탐한다)."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("euc-kr", errors="replace")


def fetch_list_page(base_url: str, mid: str, bid: str, page: int) -> str:
    url = f"{base_url}/board.es"
    params = {"mid": mid, "bid": bid, "nPage": page}
    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return _decode(r.content)


def _clean_title_block(block: str) -> str:
    """주석 제거 후 남는 텍스트 줄 중 마지막(=실제 제목인 경우가 많음) 비어있지 않은 줄을 제목으로 채택."""
    no_comment = HTML_COMMENT_RE.sub("", block)
    no_tag = TAG_RE.sub("\n", no_comment)
    lines = [ln.strip() for ln in no_tag.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def parse_list(html: str) -> list[dict]:
    items = []
    for m in LIST_LINK_RE.finditer(html):
        list_no, title = m.group(1), m.group(2).strip()
        if not title or title.isdigit():
            continue
        items.append({"list_no": int(list_no), "title": title})
    for m in GOVIEW_BLOCK_RE.finditer(html):
        list_no, block = m.group(1), m.group(2)
        title = _clean_title_block(block)
        if title and not title.isdigit():
            items.append({"list_no": int(list_no), "title": title})
    # 같은 list_no가 여러 번 매치될 수 있어 중복 제거(첫 등장 유지)
    seen_no = set()
    dedup = []
    for it in items:
        if it["list_no"] in seen_no:
            continue
        seen_no.add(it["list_no"])
        dedup.append(it)
    return dedup


def fetch_detail(base_url: str, mid: str, bid: str, list_no: int) -> tuple[str, str | None]:
    """상세 페이지 HTML과, 찾을 수 있으면 게시일 문자열을 반환."""
    url = f"{base_url}/board.es"
    params = {"mid": mid, "bid": bid, "act": "view", "list_no": list_no}
    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    html = _decode(r.content)
    dm = DATE_RE.search(html)
    posted_date = None
    if dm:
        y, mo, d = dm.groups()
        posted_date = f"{y}-{int(mo):02d}-{int(d):02d}"
    return html, posted_date


def collect_source(src: dict, limit: int, dry_run: bool, title_filter: bool = True) -> list[dict]:
    if src.get("cms_type") != "board.es":
        print(f"  [스킵] {src['org_code']}: cms_type={src.get('cms_type')} (board.es 아님, 이 스크립트 범위 밖)")
        return []

    org_code = src["org_code"]
    base_url = src["base_url"]
    mid = src["mid"]
    bid = src["bid"]
    include_any = src.get("title_include_any") or []
    exclude_any = src.get("title_exclude_any") or []

    state = _load_state()
    seen = set(state.get(org_code, {}).get("seen_ids", []))

    out_dir = RAW_ROOT / org_code
    out_dir.mkdir(parents=True, exist_ok=True)

    collected: list[dict] = []
    page = 1
    while len(collected) < limit and page <= 10:  # 안전상 최대 10페이지
        html = fetch_list_page(base_url, mid, bid, page)
        items = parse_list(html)
        if not items:
            break
        for it in items:
            if len(collected) >= limit:
                break
            list_no = it["list_no"]
            key = f"{org_code}_{list_no}"
            if key in seen:
                continue
            title = it["title"]
            if include_any and not any(k in title for k in include_any):
                continue
            if exclude_any and any(k in title for k in exclude_any):
                continue

            record = {
                "source": "자체감사",
                "org_type": "중앙행정기관",
                "org_name": src.get("org_name"),
                "org_code": org_code,
                "source_title": title,
                "source_url": f"{base_url}/board.es?mid={mid}&bid={bid}&act=view&list_no={list_no}",
                "document_url_pattern": f"{base_url}/boardDownload.es?bid={bid}&list_no={list_no}&seq={{seq}}",
                "list_no": list_no,
                "collected_at": time.strftime("%Y-%m-%d"),
                "note": "list.py 자동 수집. 게시일/본문/첨부는 상세 조회 후 채움(--fetch-detail).",
            }
            collected.append(record)
            seen.add(key)

            if not dry_run:
                (out_dir / f"{org_code}_{list_no}.json").write_text(
                    json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        page += 1
        time.sleep(0.5)  # 정중한 수집 간격

    if not dry_run and collected:
        state.setdefault(org_code, {})["seen_ids"] = sorted(seen)
        state[org_code]["last_run"] = time.strftime("%Y-%m-%d")
        _save_state(state)

    print(f"  [{org_code}] 신규 {len(collected)}건 {'(dry-run, 미저장)' if dry_run else f'저장 -> {out_dir}'}")
    return collected


def main():
    ap = argparse.ArgumentParser(description="자체감사 게시판(board.es 계열) 수집기")
    ap.add_argument("--org", help="data/selfaudit_sources.json 의 org_code 하나만 수집")
    ap.add_argument("--all", action="store_true", help="board.es 계열 소스 전체 수집")
    ap.add_argument("--limit", type=int, default=20, help="소스당 최대 신규 수집 건수")
    ap.add_argument("--dry-run", action="store_true", help="목록만 확인, 파일 저장 안 함")
    args = ap.parse_args()

    sources = _load_sources()
    if args.org:
        sources = [s for s in sources if s["org_code"] == args.org]
        if not sources:
            print(f"org_code={args.org} 를 data/selfaudit_sources.json 에서 찾을 수 없음")
            sys.exit(1)
    elif not args.all:
        print("사용법: --org <code> 또는 --all 지정 필요")
        sys.exit(1)

    total = 0
    for src in sources:
        result = collect_source(src, limit=args.limit, dry_run=args.dry_run)
        total += len(result)
    print(f"총 신규 {total}건")


if __name__ == "__main__":
    main()
