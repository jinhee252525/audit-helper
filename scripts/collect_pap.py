#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pap.go.kr(감사원 공공감사포털) 자체감사결과 API를 이용해
중앙부처 자체감사 결과 원문(첨부파일)을 수집한다.
- 인증키 불필요(공개 API), robots.txt 없음(404, 별도 제한 없음)
- 사용법: python scripts/collect_pap.py <org_code> <org_name_for_search> [org_name_display]
"""
import sys, os, json, time, re
import urllib.request

BASE = "https://pap.go.kr"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://pap.go.kr/selfAudit/resultPublic/",
}

def http_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def http_post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    h = dict(HEADERS)
    h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def safe_name(s, maxlen=60):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:maxlen]

def main():
    if len(sys.argv) < 3:
        print("usage: collect_pap.py <org_code> <inst_nm_query> [inst_nm_display]")
        sys.exit(1)
    org_code = sys.argv[1]
    inst_nm = sys.argv[2]
    display = sys.argv[3] if len(sys.argv) > 3 else inst_nm

    out_dir = os.path.join("data", "raw_docs", "자체감사", org_code)
    os.makedirs(out_dir, exist_ok=True)

    from urllib.parse import quote
    list_url = (f"{BASE}/api/fdadPlanRslt?searchYmdBgng=20240101&searchYmdEnd=20260905"
                f"&searchYmdBgngA=2024-01-01&searchYmdEndA=2026-09-05"
                f"&instNm={quote(inst_nm)}&palawInstClsfCd=10&size=200&index=0&page=0")
    raw = http_get(list_url)
    raw_path = os.path.join(out_dir, f"{org_code}_pap_2024_2026_raw.json")
    with open(raw_path, "wb") as f:
        f.write(raw)
    data = json.loads(raw)
    items = data.get("_embedded", {}).get("fdadPlanRsltListDtoes", [])
    print(f"[{org_code}] plan count: {len(items)}")

    manifest = []
    seen_files = set()
    for plan in items:
        plan_uuid = plan.get("fdadPlanUuid")
        ad_mttr = plan.get("adMttrNm", "")
        ad_yr = plan.get("adYr")
        ad_fld = plan.get("adFldNm")
        posted = plan.get("frstRegDt", "")[:10] if plan.get("frstRegDt") else None
        sub_list = plan.get("subList") or []
        for sub in sub_list:
            uuid = sub.get("rlsDocAtchFileUuid")
            indic_ttl = sub.get("indicMttrTtl", "")
            inst_target = sub.get("instNm", "")
            dsprq = sub.get("dsprqKindList", "")
            if not uuid or uuid in seen_files:
                continue
            seen_files.add(uuid)
            try:
                fl_raw = http_get(f"{BASE}/api/files/filelist/{uuid}")
                fl = json.loads(fl_raw)
                files = fl.get("_embedded", {}).get("commonFileDetailDtoes", [])
            except Exception as e:
                manifest.append({
                    "org_name": display, "org_code": org_code, "org_type": "중앙",
                    "source": "자체감사", "source_title": ad_mttr,
                    "source_url": f"{BASE}/api/fdadPlanRslt/{plan.get('instCd','')}",
                    "document_url": None, "posted_date": posted, "local_path": None,
                    "audit_type_hint": ad_fld, "note": f"filelist 조회 실패: {e}",
                    "indic_mttr": indic_ttl, "target_inst": inst_target, "disposition": dsprq,
                    "plan_uuid": plan_uuid, "year": ad_yr,
                })
                continue
            time.sleep(0.4)
            for fd in files:
                fname = fd.get("fileName") or f"{uuid}_{fd.get('fileSn')}"
                fsn = fd.get("fileSn", 1)
                ext = os.path.splitext(fname)[1] or ".bin"
                local_name = f"{org_code}_{uuid[:8]}_{fsn}_{safe_name(os.path.splitext(fname)[0])}{ext}"
                local_path = os.path.join(out_dir, local_name)
                doc_url = f"{BASE}/api/files/download (POST fileId={uuid}&fileSn={fsn})"
                try:
                    blob = http_post_json(f"{BASE}/api/files/download", {"fileId": uuid, "fileSn": fsn})
                    with open(local_path, "wb") as fbin:
                        fbin.write(blob)
                    rel_local = os.path.relpath(local_path, ".")
                    status_note = None
                except Exception as e:
                    rel_local = None
                    status_note = f"다운로드 실패: {e}"
                manifest.append({
                    "org_name": display, "org_code": org_code, "org_type": "중앙",
                    "source": "자체감사", "source_title": ad_mttr,
                    "source_url": f"{BASE}/api/fdadPlanRslt/{plan.get('instCd','')}",
                    "document_url": doc_url, "posted_date": posted,
                    "local_path": rel_local, "audit_type_hint": ad_fld,
                    "note": status_note, "indic_mttr": indic_ttl,
                    "target_inst": inst_target, "disposition": dsprq,
                    "plan_uuid": plan_uuid, "year": ad_yr, "original_filename": fname,
                })
                time.sleep(0.4)

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    ok = sum(1 for m in manifest if m.get("local_path"))
    print(f"[{org_code}] manifest items: {len(manifest)}, downloaded: {ok}")

if __name__ == "__main__":
    main()
