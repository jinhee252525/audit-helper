# -*- coding: utf-8 -*-
"""ALIO 레코드 출처 보강 — raw(_raw)에서 발간일·보고서제목·감사종류·감사기간·원문링크 채움.

findings.json 의 ALIO 레코드는 posted_date·source_title·document_url 등이 비어 있었다.
raw(alio_3yr.json)의 filedata1(원문제목·저장파일)·pdate(발간일)·enfcBgng/End(감사기간)로 채운다.
매칭키: 레코드 id 의 submissionNo 부분(ALIO-YYYY-<submissionNo>-idx) ↔ raw submission_no.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

ROOT = Path(__file__).resolve().parents[1]
_AUDIT_TYPES = ["종합감사", "특정감사", "재무감사", "성과감사", "복무감사",
                "기관운영감사", "회계검사", "일상감사", "정기감사"]
ALIO_HOST = "https://www.alio.go.kr"


def _ymd(s: str | None) -> str | None:
    if not s:
        return None
    m = re.match(r"(20\d\d)[.\-](\d{1,2})[.\-](\d{1,2})", s.strip())
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None


def _parse_filedata(fd: str | None):
    """'seq**stored.ext**원문제목.ext**/path/**submissionNo' → (원문제목, stored, path)."""
    if not fd:
        return None, None, None
    parts = fd.split("**")
    if len(parts) < 4:
        return None, None, None
    stored, title = parts[1], parts[2]
    path = parts[3]
    title = re.sub(r"\.(hwp|hwpx|pdf|zip|docx?|xlsx?)$", "", title, flags=re.I)
    return title.strip(), stored, path


def _pick_report_file(raw: dict):
    """감사결과 원문(조치계획 아닌 것) 우선 선택."""
    for key in ("filedata1", "filedata2", "filedata3"):
        title, stored, path = _parse_filedata(raw.get(key))
        if title and not any(x in title for x in ("조치계획", "조치결과", "수정")):
            return title, stored, path, key
    return _parse_filedata(raw.get("filedata1")) + ("filedata1",)


def build_index() -> dict:
    idx = {}
    for name in ("alio_3yr.json", "alio_5yr.json"):
        p = ROOT / "data" / "raw_docs" / name
        if not p.exists():
            continue
        for rec in json.loads(p.read_text(encoding="utf-8")):
            sn = rec.get("submission_no") or rec.get("_raw", {}).get("submissionNo")
            if sn:
                idx[str(sn)] = rec.get("_raw", rec)
    return idx


def main() -> int:
    fp = ROOT / "data" / "findings.json"
    recs = json.loads(fp.read_text(encoding="utf-8"))
    idx = build_index()
    n = filled_date = filled_title = filled_doc = 0
    for r in recs:
        if r.get("source") != "ALIO":
            continue
        n += 1
        m = re.search(r"ALIO-\d{4}-(\d+)-", r.get("id", ""))
        sn = m.group(1) if m else None
        raw = idx.get(sn) if sn else None
        if not raw:
            continue
        # 발간일
        pd = _ymd(raw.get("pdate")) or _ymd(raw.get("idate")) or _ymd(raw.get("rdate"))
        if pd and not r.get("posted_date"):
            r["posted_date"] = pd; filled_date += 1
        # 보고서 제목 + 감사종류
        title, stored, path, key = _pick_report_file(raw)
        if title:
            if not r.get("source_title"):
                r["source_title"] = title; filled_title += 1
            if not r.get("audit_type"):
                for at in _AUDIT_TYPES:
                    if at in title:
                        r["audit_type"] = at; break
        # 감사기간
        bg, en = _ymd(raw.get("enfcBgngYmd")), _ymd(raw.get("enfcEndYmd"))
        if bg:
            r["audit_period"] = f"{bg}~{en}" if en else bg
        # 감사기관(B1220 = 감사원/주무부처)
        if not r.get("audit_org"):
            r["audit_org"] = "감사원·주무부처"
        # 원문 파일 직접 다운로드 URL 은 확실한 엔드포인트를 확인하지 못함 →
        # 깨진 링크를 넣지 않고, 원문 파일명만 보관(출처는 source_title+source_url 공시페이지).
        if stored:
            r["document_filename"] = title  # 원문 파일 제목(참고)
            r["document_url"] = None
        # 출처 URL 을 submissionNo 포함으로 구체화(공시 페이지)
        if sn:
            r["source_url"] = f"{ALIO_HOST}/occasional/auditPointList.do?submissionNo={sn}"
    fp.write_text(json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ALIO {n}건 · 발간일채움 {filled_date} · 제목채움 {filled_title} · 원문링크 {filled_doc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
