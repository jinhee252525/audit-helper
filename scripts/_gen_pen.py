# -*- coding: utf-8 -*-
import json, os, time, urllib.request

BASE = r"C:\Users\국민권익위원회\Desktop\audit-helper\data\raw_docs\자체감사\pen"
os.makedirs(BASE, exist_ok=True)
ORIGIN = "https://www.pen.go.kr"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; audit-helper-collector/1.0; +internal research use)"}

posts = [
 {"id":"1177907","title":"부산해군과학기술고등학교 종합감사 결과","date":"2026.08.13",
  "body":"❍ 감사범위: 2022. 5. 13.부터 감사일 현재까지 처리한 기관 운영 전반 ❍ 감사기간: 2026. 6. 8.(월)∼6. 10.(수) (3일간) ❍ 감사인원: 감사1담당 사무관 등 9명 ❍ 이행여부: 감사 처분 이행완료",
  "files":[{"name":"(공개용) 부산해군과학기술고등학교 종합감사 결과.hwpx","path":"/upload/main/na/bbs_2370/ntt_1177907/doc_a764v0354=79vde=46vd0=adv48=68c9v8841vf849_v9531.hwpx"}]},
 {"id":"1177429","title":"경남여자고등학교 종합감사 결과 공개","date":"2026.08.06",
  "body":"❍ 감사범위: 2022. 4. 8.부터 감사일 현재까지 처리한 학교 운영 전반 ❍ 감사기간: 2026. 6. 15. ~ 6. 17.(3일간) ❍ 감사인원: 감사2담당사무관 등 8명 ❍ 이행여부: 감사 처분 이행완료",
  "files":[{"name":"(공개용)경남여자고등학교 종합감사 결과.hwpx","path":"/upload/main/na/bbs_2370/ntt_1177429/doc_bb8av343a=20v57=4fvcc=9dv1a=490bv32cfv428e_v4644.hwpx"}]},
 {"id":"1176698","title":"부산장안고등학교 종합감사 결과","date":"2026.07.29",
  "body":"❍ 대상기관: 부산장안고등학교 ❍ 감사범위: 2022. 12. 9.부터 감사일 현재까지 처리한 학교 운영 전반 ❍ 감사기간: 2026. 5. 27. ~ 5. 29.(3일간) ❍ 감사인원: 감사1담당사무관 등 9명",
  "files":[{"name":"(공개용) 부산장안고등학교 종합감사 결과.hwpx","path":"/upload/main/na/bbs_2370/ntt_1176698/doc_fb4dv4f48=09v99=45vb4=9bvd1=b79dv839cv3fc4_v5822.hwpx"}]},
 {"id":"1176697","title":"부산산업학교 종합감사 결과","date":"2026.07.29",
  "body":"❍ 대상기관: 부산산업학교 ❍ 감사범위: 2022. 5. 5.부터 감사일 현재까지 처리한 학교 운영 전반 ❍ 감사기간: 2026. 5. 20. ~ 5. 22.(3일간) ❍ 감사인원: 감사1담당사무관 등 9명",
  "files":[{"name":"(공개용) 부산산업학교 종합감사 결과.hwpx","path":"/upload/main/na/bbs_2370/ntt_1176697/doc_3c3cva47b=80v64=4dva0=8ev52=fd41ve166vec09_v4382.hwpx"}]},
 {"id":"1176696","title":"부산항공고등학교 종합감사 결과","date":"2026.07.29",
  "body":"❍ 대상기관: 부산항공고등학교 ❍ 감사범위: 2022. 2. 10.부터 감사일 현재까지 처리한 학교 운영 전반 ❍ 감사기간: 2026. 5. 13. ~ 5. 15.(3일간) ❍ 감사인원: 감사1담당사무관 등 9명",
  "files":[{"name":"(공개용) 부산항공고등학교 종합감사 결과.hwpx","path":"/upload/main/na/bbs_2370/ntt_1176696/doc_4e78ved01=27vb8=41v99=80va8=ef70v0d9fv48b0_v1697.hwpx"}]},
 {"id":"1175981","title":"부산소프트웨어마이스터고등학교 종합감사 결과","date":"2026.07.20",
  "body":"❍ 대상기관: 부산소프트웨어마이스터고등학교 ❍ 감사범위: 2022. 5. 19.부터 감사일 현재까지 처리한 기관 운영 전반 ❍ 감사기간: 2026. 4. 13.(월)∼4. 15.(수) (3일간) ❍ 감사인원: 감사1담당 사무관 등 9명",
  "files":[{"name":"(공개용) 부산소프트웨어마이스터고등학교 종합감사 결과.hwpx","path":"/upload/main/na/bbs_2370/ntt_1175981/doc_a3b4v9ed4=4fv6e=43vb9=95v58=be14vde96v2dd4_v2992.hwpx"}]},
 {"id":"1175021","title":"동천고등학교 종합감사 결과 공개","date":"2026.07.07",
  "body":"❍ 감사범위: 2022. 6. 24.부터 감사일까지 처리한 학교 운영 전반 ❍ 감사기간: 2026. 4. 13.~4. 15.(3일간) ❍ 감사인원: 감사2담당사무관 등 8명 ❍ 이행여부: 감사 처분 이행중",
  "files":[{"name":"(공개용)동천고등학교 종합감사 결과.hwpx","path":"/upload/main/na/bbs_2370/ntt_1175021/doc_f7e7v522f=00ve7=4bvf8=9cvba=141cvd229v04f1_v9634.hwpx"}]},
 {"id":"1175018","title":"부산공업고등학교 종합감사 결과 공개","date":"2026.07.07",
  "body":"❍ 감사범위: 2022. 4. 1.부터 감사일까지 처리한 학교 운영 전반 ❍ 감사기간: 2026. 4. 8.~4. 10.(3일간) ❍ 감사인원: 감사2담당사무관 등 8명 ❍ 이행여부: 감사 처분 이행중",
  "files":[{"name":"(공개용)부산공업고등학교 종합감사 결과.hwpx","path":"/upload/main/na/bbs_2370/ntt_1175018/doc_7a26v40b3=7cva4=46v04=91v95=a723v6d40vf71f_v5529.hwpx"}]},
 {"id":"1175015","title":"부산광역시립중앙도서관 종합감사 결과 공개","date":"2026.07.07",
  "body":"❍ 감사범위: 2022. 7. 22.부터 감사일까지 처리한 기관 운영 전반 ❍ 감사기간: 2026. 3. 30.~4. 1.(3일간) ❍ 감사인원: 감사2담당사무관 등 8명 ❍ 이행여부: 감사 처분 이행완료",
  "files":[{"name":"(공개용)부산광역시립중앙도서관 종합감사 결과.hwpx","path":"/upload/main/na/bbs_2370/ntt_1175015/doc_8ecdvdd06=13v66=47vc7=94v32=1c70ve858v1074_v7805.hwpx"}]},
 {"id":"1175010","title":"부산광역시립해운대도서관 종합감사 결과 공개","date":"2026.07.07",
  "body":"❍ 감사범위: 2022. 2. 26.부터 감사일까지 처리한 기관 운영 전반 ❍ 감사기간: 2026. 3. 18.~3. 20.(3일간) ❍ 감사인원: 감사2담당사무관 등 8명 ❍ 이행여부: 감사 처분 이행완료",
  "files":[{"name":"(공개용)부산광역시립해운대도서관 종합감사 결과.hwpx","path":"/upload/main/na/bbs_2370/ntt_1175010/doc_9dfev6110=19v6b=47ve7=bev6e=b162vccedva6a0_v1859.hwpx"}]},
]

manifest = []
for p in posts:
    detail_url = f"https://www.pen.go.kr/main/na/ntt/selectNttInfo.do?mi=30502&bbsId=2370&nttSn={p['id']}"
    for j, fobj in enumerate(p['files'], start=1):
        furl = ORIGIN + fobj['path']
        ext = os.path.splitext(fobj['path'])[1] or ".hwpx"
        local_name = f"pen_{p['id']}_{j}{ext}"
        local_path = os.path.join(BASE, local_name)
        status, fail_reason = "ok", None
        try:
            req = urllib.request.Request(furl, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            with open(local_path, "wb") as f:
                f.write(data)
            if len(data) < 500:
                status, fail_reason = "failed", f"다운로드 파일 크기 비정상({len(data)} bytes)"
        except Exception as e:
            status, fail_reason = "failed", f"다운로드 실패: {e}"
            local_path = None
        manifest.append({
            "org_name": "부산광역시교육청",
            "org_code": "pen",
            "org_type": "교육",
            "source": "자체감사",
            "source_title": f"{p['title']} - {fobj['name']}",
            "source_url": detail_url,
            "document_url": furl,
            "posted_date": p['date'].replace('.', '-'),
            "local_path": local_path,
            "audit_type_hint": "종합감사",
            "status": status,
            "fail_reason": fail_reason,
            "note": p['body']
        })
        time.sleep(0.6)

with open(os.path.join(BASE, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

ok = sum(1 for m in manifest if m['status']=='ok')
print(f"pen done: total={len(manifest)} ok={ok}")
