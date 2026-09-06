# -*- coding: utf-8 -*-
"""board.es 계열 자체감사 상세페이지에서 게시일 추출 + 첨부문서 다운로드.

collect_selfaudit.py 가 만든 목록 레코드(<org_code>_<list_no>.json)를 입력으로,
각 상세페이지를 조회해 posted_date 를 채우고, 첨부(HWP/HWPX/PDF)를 실제 저장한다.
게시일이 최근 3년(2024~2026) 범위 밖이면 건너뛴다.
robots 준수(허용 기관만 대상), 정중한 간격. 재실행 안전(이미 받은 파일 skip).

사용:
  python pipeline/fetch_boardes_docs.py --org acrc
  python pipeline/fetch_boardes_docs.py --all
"""
from __future__ import annotations
import argparse, glob, json, os, re, sys, time
from pathlib import Path
import requests

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw_docs" / "자체감사"
HEADERS = {"User-Agent": "Mozilla/5.0 (audit-helper; +selfaudit)", }
# 게시일 라벨에 고정 (페이지 내 무관한 날짜 오탐 방지). 라벨과 날짜 사이 태그/공백 허용.
DATE_RE = re.compile(r"(?:게시일|작성일|등록일)[^0-9]{0,40}(20\d{2})[.\-](\d{1,2})[.\-](\d{1,2})")


def robots_allows(base_url: str, mid: str, bid: str) -> tuple[bool, str]:
    """robots.txt 를 확인해 해당 board.es 경로 수집 허용 여부 판정.
    /board 계열 Disallow 가 있고, 대상 mid 가 Allow 예외에 없으면 차단."""
    try:
        rb = requests.get(base_url.rstrip("/") + "/robots.txt", headers=HEADERS, timeout=15).text
    except Exception:
        return True, "robots.txt 조회불가(허용 간주)"
    dis = [l.split(":", 1)[1].strip() for l in rb.splitlines() if l.strip().lower().startswith("disallow") and ":" in l]
    alw = [l.split(":", 1)[1].strip() for l in rb.splitlines() if l.strip().lower().startswith("allow") and ":" in l]
    board_blocked = any(d and ("/board" == d or d.startswith("/board.es") and "mid=" not in d or d == "/board.es") for d in dis)
    # 특정 board 만 Disallow 한 경우: 우리 mid 가 그 Disallow 에 포함되면 차단
    specific_block = any(mid in d for d in dis if "mid=" in d)
    if specific_block:
        return False, f"robots Disallow(특정 board mid={mid})"
    if board_blocked:
        allowed = any((mid in a) for a in alw if a.startswith("/board") and "rss" not in a)
        if allowed:
            return True, "robots: /board 차단이나 대상 board Allow 예외"
        return False, "robots Disallow: /board.es (대상 board Allow 예외 없음)"
    return True, "robots 허용"
MIN_YEAR, MAX_YEAR = 2024, 2026
DOC_EXT = (".hwp", ".hwpx", ".pdf")

# 첨부 다운로드 링크: boardDownload.es?bid=..&list_no=..&seq=N  (&amp; 포함)
DL_RE = re.compile(r"boardDownload\.es\?([^\"'()\s>]+)")


def _decode(content: bytes) -> str:
    for enc in ("utf-8", "euc-kr", "cp949"):
        try: return content.decode(enc)
        except UnicodeDecodeError: continue
    return content.decode("utf-8", "replace")


def _sources() -> dict:
    d = json.loads((ROOT / "data" / "selfaudit_sources.json").read_text(encoding="utf-8"))
    return {s["org_code"]: s for s in d["sources"] if s.get("cms_type") == "board.es"}


def _safe(s: str, n: int = 40) -> str:
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"[\\/:*?\"<>|]", "", s)
    return s[:n]


def _filename_from_headers(resp: requests.Response, fallback: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    if m:
        name = m.group(1).strip()
        from urllib.parse import unquote
        if "%" in name:
            name = unquote(name)
        else:
            # requests 는 헤더를 latin-1 로 디코드 → 한글 파일명은 euc-kr/utf-8 로 복원
            for enc in ("euc-kr", "utf-8"):
                try:
                    cand = name.encode("latin-1").decode(enc)
                    if cand and "�" not in cand:
                        name = cand; break
                except (UnicodeEncodeError, UnicodeDecodeError):
                    continue
        return name
    return fallback


def process_org(org_code: str, base_url: str) -> dict:
    folder = RAW_ROOT / org_code
    recs = sorted(glob.glob(str(folder / f"{org_code}_*.json")))
    manifest = []
    n_docs = 0
    n_skip_year = 0
    for rp in recs:
        rec = json.loads(Path(rp).read_text(encoding="utf-8"))
        url = rec.get("source_url")
        list_no = rec.get("list_no")
        if not url:
            continue
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            html = _decode(r.content)
        except Exception as e:
            manifest.append({**_base_rec(rec), "posted_date": None, "local_path": None,
                             "note": f"상세조회 실패: {e}"})
            continue
        dm = DATE_RE.search(html)
        posted = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else None
        if posted:
            yr = int(posted[:4])
            if yr < MIN_YEAR or yr > MAX_YEAR:
                n_skip_year += 1
                continue
        else:
            # 게시일 확인 불가 → 범위 판정 불가, 안전하게 건너뜀
            n_skip_year += 1
            continue
        # 첨부 링크 수집(중복 제거)
        links = []
        for q in DL_RE.findall(html):
            q = q.replace("&amp;", "&")
            if f"list_no={list_no}" in q or "list_no=" not in q:
                links.append(q)
        links = list(dict.fromkeys(links))
        saved = []
        for q in links:
            dl = f"{base_url}/boardDownload.es?{q}"
            try:
                dr = requests.get(dl, headers={**HEADERS, "Referer": url}, timeout=60)
                if dr.status_code != 200 or len(dr.content) < 500:
                    continue
                fname = _filename_from_headers(dr, f"{org_code}_{list_no}_{len(saved)+1}.bin")
                if not fname.lower().endswith(DOC_EXT):
                    # 문서형 첨부만 저장
                    if not any(e in fname.lower() for e in DOC_EXT):
                        continue
                ext = os.path.splitext(fname)[1].lower()
                out = folder / f"{org_code}_{list_no}_{_safe(os.path.splitext(fname)[0])}{ext}"
                if out.exists() and out.stat().st_size == len(dr.content):
                    saved.append(str(out.relative_to(ROOT))); continue
                out.write_bytes(dr.content)
                saved.append(str(out.relative_to(ROOT)))
                n_docs += 1
            except Exception:
                continue
            time.sleep(0.4)
        manifest.append({**_base_rec(rec), "posted_date": posted,
                         "document_urls": [f"{base_url}/boardDownload.es?{q}" for q in links],
                         "local_paths": saved,
                         "local_path": saved[0] if saved else None})
        time.sleep(0.5)
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"org": org_code, "records": len(manifest), "docs_downloaded": n_docs, "skipped_year": n_skip_year}


def _base_rec(rec: dict) -> dict:
    return {
        "org_name": rec.get("org_name"), "org_code": rec.get("org_code"),
        "org_type": "중앙", "source": "자체감사",
        "source_title": rec.get("source_title"), "source_url": rec.get("source_url"),
        "list_no": rec.get("list_no"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--org")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    srcs = _sources()
    targets = list(srcs) if a.all else ([a.org] if a.org else [])
    if not targets:
        print("--org 또는 --all 필요"); return 1
    for oc in targets:
        if oc not in srcs:
            print(f"[스킵] {oc}: board.es 소스 아님"); continue
        s = srcs[oc]
        ok, why = robots_allows(s["base_url"], s.get("mid", ""), s.get("bid", ""))
        if not ok:
            print(f"[차단] {oc}: {why} → 수집 안 함"); continue
        res = process_org(oc, s["base_url"])
        print(f"[{oc}] 레코드 {res['records']} · 문서 {res['docs_downloaded']} · 연도범위밖 {res['skipped_year']} ({why})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
