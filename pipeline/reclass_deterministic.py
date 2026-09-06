# -*- coding: utf-8 -*-
"""결정론적 보완 분류 (rate limit 시 서브에이전트 대체).

- 미태깅(tag_confidence 없음: 실패 샤드) → 기본 19코드 + 신설 20~24 규칙으로 판정.
- 기타(work_type=="19") → 신설 20~24 키워드에 맞으면 재분류.
- LLM이 이미 붙인 비-19 분류는 존중(건드리지 않음).
- 결정론 판정은 tag_method="rule", 저신뢰는 review=true(검수큐).
근거 없는 강제 금지: 매칭 안 되면 19 유지.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
if sys.stdout.encoding and sys.stdout.encoding.lower()!="utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
ROOT = Path(__file__).resolve().parents[1]

# 신설 20~24 (구체 키워드 — 오탐 최소화)
NEW_RULES = [
    ("20", ["채권", "미수금", "미수액", "연체", "결손처분", "대손", "구상금", "과오납", "세외수입", "세입 징수", "수입금 관리", "체납"]),
    ("21", ["물품관리", "물품 관리", "비품", "재물조사", "재고", "저장품", "불용품", "공유재산", "국유재산", "관용물품", "자산관리", "재산 관리", "물품 취득", "물품 처분"]),
    ("22", ["시설물", "시설 관리", "시설관리", "안전관리", "안전점검", "노후", "소방시설", "방재", "승강기", "놀이시설", "석면", "내진", "화재예방", "재난안전", "안전진단"]),
    ("23", ["정보시스템", "전산", "정보화", "소프트웨어", "데이터베이스", "개인정보", "정보보안", "홈페이지", "시스템 구축", "cctv", "정보통신", "전자문서시스템", "디지털", "정보자산"]),
    ("24", ["기록물", "정보공개", "문서관리", "문서 관리", "공문서", "비밀문서", "대장 관리", "서식 관리", "공시 누락", "기록관리"]),
]
# 미태깅 보완용 기본 19코드 앵커(에이전트와 동일 취지)
BASE_RULES = [
    ("02", ["수의계약", "입찰", "낙찰", "용역계약", "물품계약", "발주", "계약 체결", "계약업무", "계약 변경", "예정가격"]),
    ("04", ["시공", "설계", "감리", "준공", "건설공사", "공사감독", "하자", "착공", "건설사업관리"]),
    ("11", ["복무", "채용", "임용", "승진", "전보", "징계", "겸직", "근태", "초과근무수당", "시간외근무", "당직", "휴가", "호봉", "품위유지", "행동강령"]),
    ("17", ["여비", "출장비", "업무추진비", "성과상여금", "수당 지급", "정산", "지출", "급여", "보수", "카드", "예산 집행", "회계", "정산 소홀"]),
    ("15", ["보조금", "보조사업", "지원금", "포상금", "출연금", "국고보조"]),
    ("06", ["과태료", "부과", "징수", "환수", "부담금", "과세", "가산세", "감면"]),
    ("14", ["점검", "단속", "지도·감독", "사후관리", "실태조사", "감찰"]),
    ("10", ["인가", "허가", "면허", "특허"]),
    ("05", ["신고 수리", "등록", "발급", "교부"]),
    ("09", ["대부", "보증", "융자", "여신", "구상"]),
    ("08", ["심사", "심의", "평가위원", "선정위원회"]),
]

def _find(text, rules):
    t = (text or "").lower()
    for code, kws in rules:
        for k in kws:
            if k.lower() in t:
                return code
    return None

def main() -> int:
    pap = json.loads((ROOT/"data"/"findings.pap.json").read_text(encoding="utf-8"))
    n_new=n_base=0
    for x in pap:
        ex = (x.get("source_excerpt") or "") + " " + (x.get("source_title") or "")
        untagged = x.get("tag_confidence") is None
        if untagged:
            # 미태깅: 기본 앵커 → 없으면 신설 → 없으면 19
            code = _find(ex, BASE_RULES) or _find(ex, NEW_RULES)
            if code:
                x["work_type"]=code; x["finding_type"]=code+"z"; n_base+=1
                x["tag_method"]="rule"; x["tag_confidence"]=0.5; x["review"]=True
            else:
                x["work_type"]="19"; x["finding_type"]="19z"
                x["tag_method"]="rule"; x["tag_confidence"]=0.2; x["review"]=True
        elif x.get("work_type")=="19":
            # 기타 → 신설 20~24 재분류 시도
            code = _find(ex, NEW_RULES)
            if code:
                x["work_type"]=code; x["finding_type"]=code+"z"; n_new+=1
                x["tag_method"]="rule-reclass"
                # 신설 재분류는 중신뢰
                if x.get("tag_confidence",0) < 0.5: x["tag_confidence"]=0.5
    (ROOT/"data"/"findings.pap.json").write_text(json.dumps(pap,ensure_ascii=False,indent=2),encoding="utf-8")
    import collections
    print(f"미태깅 규칙판정 {n_base:,} · 기타→신설 재분류 {n_new:,}")
    c=collections.Counter(x['work_type'] for x in pap)
    print("work_type 분포:",dict(c.most_common()))
    print("19 잔여:",c.get('19'),f"({c.get('19')/len(pap)*100:.1f}%)")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
