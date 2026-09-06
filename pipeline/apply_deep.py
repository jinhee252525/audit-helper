# -*- coding: utf-8 -*-
"""deep_out/*.json(기타 심층 재분류) → findings.pap.json + findings.json 반영.

- 대상은 기존 work_type=="19" 였던 레코드(deep_shards 에서 추출). id로 매칭.
- deep 결과가 19가 아니면 갱신(work_type/sector/finding_type), tag_method="deep", tag_confidence 갱신.
- 여전히 19면 그대로(정직). 코드북 폐쇄집합(01~25, sector 01~28) 검증.
"""
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
    deep={}
    for f in glob.glob(str(ROOT/"data"/"deep_out"/"deep_*.json")):
        for t in json.loads(Path(f).read_text(encoding="utf-8")):
            deep[t["id"]]=t
    print("deep 결과 로드:",len(deep))
    total_upd=0
    for path in ["data/findings.pap.json","data/findings.json"]:
        d=json.loads((ROOT/path).read_text(encoding="utf-8")); upd=0
        for x in d:
            t=deep.get(x["id"])
            if not t: continue
            wt=t.get("work_type");
            if wt not in WT: wt="19"
            sec=t.get("sector");
            if sec not in SEC: sec=None
            if wt!="19" and x.get("work_type")=="19":
                x["work_type"]=wt; x["sector"]=sec; x["finding_type"]=wt+"z"
                x["tag_method"]="deep"; x["tag_confidence"]=t.get("confidence")
                x["review"]=bool(t.get("need_deep"))
                upd+=1
        (ROOT/path).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"  {path}: {upd}건 재분류 반영"); total_upd+=upd
    import collections
    allf=json.loads((ROOT/"data"/"findings.pap.json").read_text(encoding="utf-8"))
    c=collections.Counter(x['work_type'] for x in allf)
    print("pap 19 잔여:",c.get('19'),f"({c.get('19')/len(allf)*100:.1f}%)")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
