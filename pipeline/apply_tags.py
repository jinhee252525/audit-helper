# -*- coding: utf-8 -*-
"""tag_out/*.json(의미분류 결과)를 findings.pap.json 에 반영.

- work_type/sector 갱신, confidence 저장.
- confidence<임계 또는 need_deep=true → review=true(검수큐) + review_queue.json 적재.
- 코드북 폐쇄집합 검증(벗어난 코드는 19/None 로 안전화).
"""
from __future__ import annotations
import json, glob, sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower()!="utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

ROOT = Path(__file__).resolve().parents[1]
REVIEW_TH = 0.5
CB = json.loads((ROOT/"data"/"codebook.json").read_text(encoding="utf-8"))
WT = set(CB["work_type_관련기능"].keys())
SEC = set(CB["sector_발생분야"].keys())


def main() -> int:
    pap = json.loads((ROOT/"data"/"findings.pap.json").read_text(encoding="utf-8"))
    tags = {}
    for f in glob.glob(str(ROOT/"data"/"tag_out"/"shard_*.json")):
        for t in json.loads(Path(f).read_text(encoding="utf-8")):
            tags[t["id"]] = t
    applied=review=0; missing=0
    rq=[]
    for x in pap:
        t = tags.get(x["id"])
        if not t:
            missing+=1; continue
        wt = t.get("work_type")
        if wt not in WT: wt="19"
        sec = t.get("sector")
        if sec not in SEC: sec=None
        x["work_type"]=wt
        x["sector"]=sec
        x["finding_type"]=wt+"z"
        conf=t.get("confidence")
        x["tag_confidence"]=conf
        if (conf is not None and conf<REVIEW_TH) or t.get("need_deep"):
            x["review"]=True; review+=1
            rq.append({"id":x["id"],"excerpt":(x.get("source_excerpt") or "")[:60],
                       "work_type":wt,"confidence":conf,"need_deep":t.get("need_deep",False)})
        else:
            x["review"]=False
        applied+=1
    (ROOT/"data"/"findings.pap.json").write_text(json.dumps(pap,ensure_ascii=False,indent=2),encoding="utf-8")
    (ROOT/"data"/"review_queue.json").write_text(json.dumps(rq,ensure_ascii=False,indent=2),encoding="utf-8")
    import collections
    print(f"반영 {applied:,} · 미태깅 {missing:,} · 검수큐 {review:,}")
    print("work_type 분포:",dict(collections.Counter(x['work_type'] for x in pap).most_common()))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
