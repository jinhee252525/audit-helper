# -*- coding: utf-8 -*-
import json, os

BASE = r"C:\Users\국민권익위원회\Desktop\audit-helper\data\raw_docs\자체감사\ice"
os.makedirs(BASE, exist_ok=True)

ROBOTS_NOTE = ("첨부파일 실제 경로는 ice.go.kr /upload/ 하위이며, 인천광역시교육청 robots.txt가 "
  "\"Disallow: /upload/\"로 전체 크롤러에 대해 차단하고 있어 본 세션은 원문 PDF 파일을 다운로드하지 않았습니다. "
  "게시글 목록·상세 페이지(/ice/na/ntt/)는 robots.txt에서 차단되지 않아(‘/na/’ 차단규칙은 루트 기준 경로라 ‘/ice/na/’에는 미적용) 열람과 본문 텍스트 수집만 수행했습니다.")

posts = [
 {"id":"3365967","title":"2025년 자율감사 결과(명신여고, 인천바이오과학고, 인평자동차고)","date":"2026.03.30",
  "body":"2025년 자율감사 결과(명신여자고등학교, 인천바이오과학고등학교, 인평자동차고등학교)\n- 명신여고: 2025. 11. 27. ~ 2025. 11. 28. (2일)\n- 인천바이오과학고: 2025. 12. 3. ~12. 4.(2일)\n- 인평자동차고: 2025. 12. 18. ~ 12. 19.(2일)",
  "files":[("2025 자율감사 최종결과보고서(공개용-명신여고,인천바이오과학고,인평자동차고).pdf","https://www.ice.go.kr/upload/ice/na/bbs_1735/2026/03/4830b16e39fd86ae95cc3109b0842c0c.pdf")], "hint":"자율감사"},
 {"id":"3365936","title":"2025년 종합감사 결과(인천하늘고등학교)","date":"2026.03.30",
  "body":"2025년 종합감사 결과(인천하늘고등학교) - 기간: 2025. 12. 9. ~ 2025. 12. 12. (4일)",
  "files":[("인천하늘고등학교(공개용).pdf","https://www.ice.go.kr/upload/ice/na/bbs_1735/2026/03/96fb48ae59dadb48720223a3ac93b8c0.pdf")], "hint":"종합감사"},
 {"id":"3356675","title":"2025년 종합감사 결과(선인고등학교)","date":"2026.01.23",
  "body":"2025년 종합감사 결과(선인고등학교) - 기간: 2025. 5. 26. ~ 2025. 5. 29.(4일)",
  "files":[("선인고등학교.pdf","https://www.ice.go.kr/upload/ice/na/bbs_1735/2026/01/1c350271abd63e7d4b2cf498d3e7688e.pdf")], "hint":"종합감사"},
 {"id":"3353220","title":"2025년 종합감사 결과(인천생활과학고등학교)","date":"2025.12.31",
  "body":"2025년 종합감사 결과(인천생활과학고등학교) - 기간: 2025.11.6.~2025.11.11.(4일)",
  "files":[("종합감사 결과 보고서(생활과학고)공개용.pdf","https://www.ice.go.kr/upload/ice/na/bbs_1735/2025/12/377579cc4247f3aa125610e716943f63.pdf")], "hint":"종합감사"},
 {"id":"3353199","title":"2025년 종합감사 결과(인천소방고등학교)","date":"2025.12.31",
  "body":"2025년 종합감사 결과(인천소방고등학교) - 기간: 2025.10.27.~2025.10.30.(4일)",
  "files":[("종합감사 결과 보고서(소방고)공개용.pdf","https://www.ice.go.kr/upload/ice/na/bbs_1735/2025/12/dede4dc0b3f21489b44f5cc04891372d.pdf")], "hint":"종합감사"},
 {"id":"3352322","title":"2025년 자율감사 우수사례(인천반도체고)","date":"2025.12.23",
  "body":"2025년 자율감사 우수사례(인천반도체고) *첨부파일 참고",
  "files":[("자율감사 우수사례(인천반도체고).pdf","https://www.ice.go.kr/upload/ice/na/bbs_1735/2025/12/2e1e4288fb1aca4d85b697a5fd68f716.pdf")], "hint":"자율감사(우수사례)"},
 {"id":"3352317","title":"2025년 자율감사 우수사례(인천예술고)","date":"2025.12.23",
  "body":"2025년 자율감사 우수사례(인천예술고) *첨부파일 참고",
  "files":[("자율감사 우수사례(인천예술고).pdf","https://www.ice.go.kr/upload/ice/na/bbs_1735/2025/12/be67f0e2e85faa658fa153d7e0477941.pdf")], "hint":"자율감사(우수사례)"},
 {"id":"3352316","title":"2025년 자율감사 우수사례(인천고잔고)","date":"2025.12.23",
  "body":"2025년 자율감사 우수사례(인천고잔고) *첨부파일 참고",
  "files":[("자율감사 우수사례(인천고잔고).pdf","https://www.ice.go.kr/upload/ice/na/bbs_1735/2025/12/db543ffc4e49186de9618d5aefda27bf.pdf")], "hint":"자율감사(우수사례)"},
 {"id":"3352179","title":"2025년 자율감사 우수사례(인천바이오과학고)","date":"2025.12.23",
  "body":"2025년 자율감사 우수사례(인천바이오과학고) *첨부파일 참고",
  "files":[("☆인천바이오과학고등학교 자율감사 우수사례.pdf","https://www.ice.go.kr/upload/ice/na/bbs_1735/2025/12/1ce35e783b388ef7afa8569c8c2dd665.pdf")], "hint":"자율감사(우수사례)"},
 {"id":"3350319","title":"2025년 자율감사 결과(인천영종고등학교)","date":"2025.12.12",
  "body":"2025년 자율감사 결과(인천영종고등학교) - 기간: 2025.9.30.~2025.10.1.(2일)",
  "files":[("자율감사 결과 보고서(영종고)공개용.pdf","https://www.ice.go.kr/upload/ice/na/bbs_1735/2025/12/744cac782c3759040af446f5e92e121b.pdf")], "hint":"자율감사"},
]

manifest = []
for p in posts:
    url = f"https://www.ice.go.kr/ice/na/ntt/selectNttInfo.do?mi=10951&bbsId=1735&nttSn={p['id']}"
    fname = f"ice_{p['id']}.txt"
    fpath = os.path.join(BASE, fname)
    file_lines = "\n".join(f"{n} ({u})" for n, u in p['files'])
    content = (
        f"[제목] {p['title']}\n"
        f"[게시판] 인천광역시교육청 행정 > 청렴/감사 > 감사결과공개\n"
        f"[등록일] {p['date']}\n"
        f"[출처 URL] {url}\n\n"
        f"[본문]\n{p['body']}\n\n"
        f"[첨부파일 목록 - 다운로드 불가]\n{file_lines}\n\n"
        f"[비고] {ROBOTS_NOTE}\n"
    )
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    manifest.append({
        "org_name": "인천광역시교육청",
        "org_code": "ice",
        "org_type": "교육",
        "source": "자체감사",
        "source_title": p['title'],
        "source_url": url,
        "document_url": p['files'][0][1] if p['files'] else None,
        "posted_date": p['date'].replace('.', '-'),
        "local_path": fpath,
        "audit_type_hint": p['hint'],
        "status": "ok",
        "fail_reason": None,
        "note": ROBOTS_NOTE
    })

with open(os.path.join(BASE, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

print("ice done:", len(manifest))
