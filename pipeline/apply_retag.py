# -*- coding: utf-8 -*-
"""retag_out/*.json(careful 건별 재태깅) → findings 반영. 교정이므로 현재값 덮어씀.
저신뢰/need_deep → review=true(신뢰도 라우팅). 코드북 폐쇄집합 검증."""
from __future__ import annotations
import json, glob, sys
from pathlib import Path
if sys.stdout.encoding and sys.stdout.encoding.lower()!="utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
ROOT=Path(__file__).resolve().parents[1]
CB=json.loads((ROOT/"data"/"codebook.json").read_text(encoding="utf-8"))
WT=set(CB["work_type_관련기능"].keys()); SEC=set(CB["sector_발생분야"].keys())

def main()->int:
    rt={}
    for f in glob.glob(str(ROOT/"data"/"retag_out"/"retag_*.json")):
        for t in json.loads(Path(f).read_text(encoding="utf-8")):
            rt[t["id"]]=t
    print("retag 결과:",len(rt))
    for path in ["data/findings.pap.json","data/findings.json"]:
        d=json.loads((ROOT/path).read_text(encoding="utf-8")); ch=0
        for x in d:
            t=rt.get(x["id"])
            if not t: continue
            wt=t.get("work_type");  wt=wt if wt in WT else "19"
            sec=t.get("sector");    sec=sec if sec in SEC else None
            x["work_type"]=wt; x["finding_type"]=wt+"z"; x["sector"]=sec
            x["tag_method"]="retag-careful"; x["tag_confidence"]=t.get("confidence")
            x["review"]=bool(t.get("need_deep")) or (t.get("confidence") or 0)<0.6
            ch+=1
        (ROOT/path).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"  {path}: {ch}건 반영")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
