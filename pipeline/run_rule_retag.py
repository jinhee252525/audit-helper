# -*- coding: utf-8 -*-
import json, os, sys
from pathlib import Path
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(os.environ["USERPROFILE"]) / "Desktop" / "audit-helper"
OUT = ROOT / "data" / "retag_out"
WORK = ROOT / "data" / "retag_work"
SHARDS = ROOT / "data" / "retag_shards"
OUT.mkdir(parents=True, exist_ok=True)

NEW_RULES = [
    ("20", ["채권", "미수금", "미수액", "연체", "결손처분", "대손", "구상금", "과오납", "세외수입", "세입 징수", "수입금", "체납"]),
    ("21", ["물품관리", "물품 관리", "비품", "재물조사", "재고", "저장품", "불용품", "공유재산", "국유재산", "관용물품", "자산관리", "재산 관리", "물품 취득", "물품 처분"]),
    ("22", ["시설물", "시설 관리", "시설관리", "안전관리", "안전점검", "노후", "소방시설", "방재", "승강기", "놀이시설", "석면", "내진", "화재예방", "재난안전", "안전진단"]),
    ("23", ["정보시스템", "전산", "정보화", "소프트웨어", "데이터베이스", "개인정보", "정보보안", "홈페이지", "시스템 구축", "cctv", "CCTV", "정보통신", "전자문서", "디지털", "정보자산"]),
    ("24", ["기록물", "정보공개", "문서관리", "문서 관리", "공문서", "비밀문서", "대장 관리", "서식", "공시 누락", "기록관리"]),
    ("25", ["학사", "학생", "학교", "수업", "성적", "입학", "졸업", "교육과정", "교무", "급식", "방과후", "생활지도", "담임", "전학"]),
]
BASE_RULES = [
    ("02", ["수의계약", "입찰", "낙찰", "용역계약", "물품계약", "발주", "계약 체결", "계약업무", "계약 변경", "예정가격", "과업", "용역"]),
    ("04", ["시공", "설계", "감리", "준공", "건설공사", "공사감독", "하자", "착공", "건설사업관리"]),
    ("11", ["복무", "채용", "임용", "승진", "전보", "징계", "겸직", "근태", "초과근무", "시간외근무", "당직", "휴가", "호봉", "행동강령", "인사"]),
    ("17", ["여비", "출장비", "업무추진비", "성과상여금", "수당", "정산", "지출", "급여", "보수", "예산 집행", "회계"]),
    ("15", ["보조금", "보조사업", "지원금", "포상금", "출연금", "국고보조"]),
    ("06", ["과태료", "부과", "징수", "환수", "부담금", "과세", "가산세", "감면"]),
    ("14", ["점검", "단속", "지도·감독", "지도감독", "사후관리", "실태조사", "감찰"]),
    ("13", ["조사", "검사", "적발"]),
    ("10", ["인가", "허가", "면허", "특허"]),
    ("05", ["신고", "등록", "발급", "교부"]),
    ("09", ["대부", "보증", "융자", "여신", "구상", "대출"]),
    ("08", ["심사", "심의", "평가위원", "선정위원회"]),
    ("18", ["위임", "위탁", "대행"]),
    ("03", ["계획", "조정", "수립"]),
    ("01", ["검정", "평가"]),
]


def find_code(text, rules):
    t = text or ""
    tl = t.lower()
    for code, kws in rules:
        for k in kws:
            if k.lower() in tl:
                return code
    return None


def classify(item):
    text = f"{item.get('x') or ''} {item.get('t') or ''}"
    iid = item.get("id") or ""
    cur = str(item.get("cur") or "19")
    if "edu" in iid.lower() or "학교" in text or "교육청" in (item.get("t") or ""):
        if find_code(text, [NEW_RULES[5]]) == "25" or any(
            k in text for k in ["학사", "학생", "수업", "성적", "입학", "급식", "방과후"]
        ):
            return {
                "id": item["id"],
                "work_type": "25",
                "sector": None,
                "confidence": 0.7,
                "need_deep": False,
            }
    code = find_code(text, NEW_RULES) or find_code(text, BASE_RULES)
    if code:
        conf = 0.65 if code in {r[0] for r in NEW_RULES} else 0.6
        if code == cur:
            conf = min(0.85, conf + 0.15)
        return {
            "id": item["id"],
            "work_type": code,
            "sector": None,
            "confidence": conf,
            "need_deep": conf < 0.55,
        }
    if cur not in {"19", "16", "03", "01"} and cur:
        return {
            "id": item["id"],
            "work_type": cur,
            "sector": None,
            "confidence": 0.4,
            "need_deep": True,
        }
    return {
        "id": item["id"],
        "work_type": "19",
        "sector": None,
        "confidence": 0.3,
        "need_deep": True,
    }


def main():
    # 000: merge existing decisions + rules for rest
    shard = json.loads((SHARDS / "retag_000.json").read_text(encoding="utf-8"))
    dec = {}
    for p in sorted(WORK.glob("dec*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for k, v in d.items():
            dec[int(k)] = v
    out = []
    src_dec = src_rule = 0
    for i, item in enumerate(shard):
        if i in dec:
            wt, sec, conf, nd = dec[i][0], dec[i][1], dec[i][2], dec[i][3]
            out.append(
                {
                    "id": item["id"],
                    "work_type": str(wt) if wt is not None else "19",
                    "sector": sec,
                    "confidence": conf,
                    "need_deep": bool(nd),
                }
            )
            src_dec += 1
        else:
            out.append(classify(item))
            src_rule += 1
    (OUT / "retag_000.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("retag_000", len(out), "dec", src_dec, "rule", src_rule)
    print(" top", Counter(x["work_type"] for x in out).most_common(10))

    done = {"002", "007", "011", "000"}
    for i in range(12):
        name = f"{i:03d}"
        if name in done:
            continue
        items = json.loads((SHARDS / f"retag_{name}.json").read_text(encoding="utf-8"))
        outs = [classify(it) for it in items]
        (OUT / f"retag_{name}.json").write_text(
            json.dumps(outs, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        chg = sum(
            1
            for a, b in zip(items, outs)
            if str(a.get("cur")) != str(b.get("work_type"))
        )
        nd = 100 * sum(1 for x in outs if x["need_deep"]) / len(outs)
        print(
            f"retag_{name} n={len(outs)} changed={chg} need_deep%={nd:.1f} top={Counter(x['work_type'] for x in outs).most_common(5)}"
        )

    print("files", sorted(p.name for p in OUT.glob("retag_*.json")))


if __name__ == "__main__":
    main()
