# -*- coding: utf-8 -*-
import json, os, time, re, urllib.request

BASE = r"C:\Users\국민권익위원회\Desktop\audit-helper\data\raw_docs\자체감사\sen"
os.makedirs(BASE, exist_ok=True)

posts = [
 {"doc":"20260824171320137","title":"정신여자고등학교 외 10개 기관 종합감사 결과 공개","date":"2026-08-24","period":"2026. 3. 17. ~ 2026. 6. 26.","hint":"종합감사",
  "files":[("(붙임1) 2026년 학교법인 정신학원 및 정신여자고등학교 종합감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2282954&q_fileId=77b90b56-57ef-43fd-a41f-b518d8da311d"),
   ("(붙임2) 2026년 오류고등학교 종합감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2282954&q_fileId=fc61b1ea-7a74-4cd6-bcad-f15b01db2a61"),
   ("(붙임3) 2026년 유한공업고등학교 종합감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2282954&q_fileId=f8d569df-8f1d-4603-ae77-ff0e3cc588d1")]},
 {"doc":"20260806144318259","title":"용산철도고등학교 외 5개 기관 감사결과 공개","date":"2026-08-06","period":"2023. 8. 10. ~ 2025. 5. 23.","hint":"특정감사",
  "files":[("1. 2023년 용산철도고등학교 시설공사 특정감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2278796&q_fileId=1d671adb-235d-4496-8cbc-69be939bea81"),
   ("2. 2023년 대일고등학교 시설공사 특정감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2278796&q_fileId=42b76242-2b9a-4e1e-9c76-1f5eb3817d07")]},
 {"doc":"20260803171512139","title":"서울특별시강남서초교육지원청 외 9개 기관 감사결과 공개","date":"2026-08-03","period":"2026. 2. 19.~5. 22.","hint":"종합감사",
  "files":[("1. 2026년 서울특별시강남서초교육지원청 종합감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2278184&q_fileId=84a4c650-422a-4805-9e0b-27ff6ae7b2ae")]},
 {"doc":"20260803171105415","title":"충암고등학교 특정감사 결과 공개","date":"2026-08-03","period":"2021. 10. 18.~10. 20.","hint":"특정감사",
  "files":[("11. 2021년 충암고등학교 학교운동부 특정감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2278183&q_fileId=a44a01b3-7a03-40b2-a2f0-e7dd66ef80a1")]},
 {"doc":"20260731095431047","title":"한국구화학교 외 1개 기관 특정감사 결과 공개","date":"2026-07-31","period":"2026. 4. 29. ~ 5. 20.","hint":"특정감사",
  "files":[("2026년 중산고등학교 특정감사 결과 공개문 - 복사본.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2277761&q_fileId=31f251b9-07e3-4f21-a5b1-acc0408aa0b1"),
   ("2026년 한국구화학교 특정감사 결과 공개문 - 복사본.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2277761&q_fileId=cf8b76b3-8998-4872-b16b-468ce7c69212")]},
 {"doc":"20260731095221720","title":"영동고등학교 외 9개 기관 특정감사 결과 공개","date":"2026-07-31","period":"2019. 4. 22. ~ 2025. 5. 22.","hint":"특정감사",
  "files":[("2019년 교원자녀 동일학교 재학 관련 특정감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2277757&q_fileId=d6351747-63d4-4f06-b4e9-74e2e7345fbe")]},
 {"doc":"20260730083546456","title":"청원고등학교 외 11개 기관 특정감사 결과 공개","date":"2026-07-30","period":"2019. 4. 23. ~ 2025. 7. 4.","hint":"특정감사",
  "files":[("(붙임1) 2019년 방과후학교운영 특정감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2277513&q_fileId=17ccc403-dba4-4493-ba51-4a7c03d656b1")]},
 {"doc":"20260630100658468","title":"강서고등학교 외 15개 기관 감사결과 공개","date":"2026-06-30","period":"2026. 1. 13. ~ 6. 26.","hint":"종합감사",
  "files":[("2026년 강서고등학교 종합감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2271142&q_fileId=4bd3774f-1fa9-4275-abe6-48c1d8ebdce2")]},
 {"doc":"20260202084116362","title":"숭실고등학교 외 12개 기관 감사결과 공개","date":"2026-02-02","period":"2025. 7. 8. ~ 2025. 12. 5.","hint":"종합감사",
  "files":[("2025년 학교법인 숭실학원 및 숭실고등학교 종합감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2233544&q_fileId=d332a46e-7f92-44e9-8781-4f3ab5a74e47")]},
 {"doc":"20260102142858183","title":"선화예술고등학교 외 8개기관 감사결과 공개","date":"2026-01-02","period":"2025. 9. 2. ~ 12. 11.","hint":"종합감사",
  "files":[("2025년 선화예술고등학교 종합감사 결과 공개문.pdf","https://www.sen.go.kr/component/file/ND_fileDownload.do?q_fileSn=2225158&q_fileId=a74a1d1b-d40a-493c-8287-6684c55a26a6")]},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; audit-helper-collector/1.0; +internal research use)"}

def safe_ext(url, fallback=".pdf"):
    m = re.search(r'\.([a-zA-Z0-9]{2,5})(?:\?|$)', url)
    return "." + m.group(1) if m else fallback

manifest = []
for i, p in enumerate(posts, start=1):
    detail_url = f"https://www.sen.go.kr/user/bbs/BD_selectBbs.do?q_bbsSn=1060&q_bbsDocNo={p['doc']}"
    for j, (fname, furl) in enumerate(p['files'], start=1):
        ext = os.path.splitext(fname)[1] or ".pdf"
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', p['title'])[:40]
        local_name = f"sen_{p['doc']}_{j}{ext}"
        local_path = os.path.join(BASE, local_name)
        status, fail_reason = "ok", None
        try:
            req = urllib.request.Request(furl, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            with open(local_path, "wb") as f:
                f.write(data)
            if len(data) < 500:
                status, fail_reason = "failed", f"다운로드 파일 크기 비정상({len(data)} bytes) - 세션/차단 페이지 의심"
        except Exception as e:
            status, fail_reason = "failed", f"다운로드 실패: {e}"
            local_path = None
        manifest.append({
            "org_name": "서울특별시교육청",
            "org_code": "sen",
            "org_type": "교육",
            "source": "자체감사",
            "source_title": f"{p['title']} - {fname}",
            "source_url": detail_url,
            "document_url": furl,
            "posted_date": p['date'],
            "local_path": local_path,
            "audit_type_hint": p['hint'],
            "status": status,
            "fail_reason": fail_reason,
            "note": f"감사기간: {p['period']}"
        })
        time.sleep(0.6)

with open(os.path.join(BASE, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

ok = sum(1 for m in manifest if m['status']=='ok')
print(f"sen done: total={len(manifest)} ok={ok}")
