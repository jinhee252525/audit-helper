# -*- coding: utf-8 -*-
"""pap.go.kr 자체감사 결과공개 — 중앙(clsf10) 전량 메타 수집.

키 불필요 공개 API(/api/fdadPlanRslt). 원문 파일은 다운로드하지 않고
document_url(다운로드 링크)만 보관한다. 감사계획(plan) 하위 지적(sub) 1건 = 레코드 1건.

출력: data/raw_docs/자체감사/_pap_central/manifest.json
사용:  python pipeline/collect_pap_central.py [--clsf 10] [--from 20240101 --to 20261231]
"""
from __future__ import annotations
import argparse, json, sys, time, urllib.request
from pathlib import Path
from urllib.parse import quote

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://pap.go.kr"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://pap.go.kr/selfAudit/resultPublic/",
}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def collect(clsf: str, dt_from: str, dt_to: str, size: int = 200) -> list[dict]:
    page = 0
    plans: list[dict] = []
    total = None
    while True:
        url = (f"{BASE}/api/fdadPlanRslt?searchYmdBgng={dt_from}&searchYmdEnd={dt_to}"
               f"&size={size}&index=0&page={page}&palawInstClsfCd={clsf}")
        j = _get(url)
        emb = j.get("_embedded", {}).get("fdadPlanRsltListDtoes", [])
        pinfo = j.get("page", {})
        total = pinfo.get("totalElements", total)
        if not emb:
            break
        plans.extend(emb)
        tp = pinfo.get("totalPages", 0)
        print(f"  page {page+1}/{tp} · 누적 계획 {len(plans)}/{total}")
        page += 1
        if page >= tp:
            break
        time.sleep(0.4)
    return plans


def to_records(plans: list[dict]) -> list[dict]:
    recs: list[dict] = []
    for p in plans:
        audit_org = p.get("instCdNm")           # 감사 수행기관
        inst_cd = p.get("instCd")
        src_title = p.get("adMttrNm")            # 감사사항명
        audit_type = p.get("adFldNm")           # 감사종류
        year = p.get("adYr")
        posted = (p.get("frstRegDt") or "")[:10] or None
        emphs = p.get("adEmphsMttr")
        plan_uuid = p.get("fdadPlanUuid")
        for s in (p.get("subList") or []):
            file_uuid = s.get("rlsDocAtchFileUuid")
            recs.append({
                "source": "자체감사",
                "org_name": s.get("instNm") or audit_org,   # 피감기관
                "audit_org": audit_org,                       # 감사수행
                "org_type_hint": "중앙",
                "source_title": src_title,
                "indic_mttr": s.get("indicMttrTtl"),          # 지적사항(원문 텍스트)
                "disposition_raw": s.get("dsprqKindList"),
                "audit_type_hint": audit_type,
                "emphasis": emphs,
                "year": year,
                "posted_date": posted,
                "source_url": f"{BASE}/api/fdadPlanRslt/{inst_cd}" if inst_cd else f"{BASE}/selfAudit/resultPublic/",
                "document_url": (f"{BASE}/api/files/download (POST fileId={file_uuid}&fileSn=1)"
                                 if file_uuid else None),
                "file_uuid": file_uuid,
                "plan_uuid": plan_uuid,
                "indic_uuid": s.get("indicMttrUuid"),
            })
    return recs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clsf", default="10", help="기관분류(10 중앙·20 교육·30 공공기관)")
    ap.add_argument("--from", dest="dt_from", default="20240101")
    ap.add_argument("--to", dest="dt_to", default="20261231")
    ap.add_argument("--out", default="data/raw_docs/자체감사/_pap_central/manifest.json")
    a = ap.parse_args()
    print(f"pap 자체감사 clsf={a.clsf} 수집({a.dt_from}~{a.dt_to})...")
    plans = collect(a.clsf, a.dt_from, a.dt_to)
    recs = to_records(plans)
    outp = ROOT / a.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    withdoc = sum(1 for r in recs if r.get("file_uuid"))
    print(f"계획 {len(plans)} · 지적(레코드) {len(recs)} · 첨부보유 {withdoc} → {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
