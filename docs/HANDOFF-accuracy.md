# 인계문서 — 분류 정확도 개선 (목표 95%)

> 다른 AI/세션이 **work_type 분류 정확도**를 이어서 올리기 위한 정확한 인계자료.
> 현재 **77.8%**(골든 617 실측) · 목표 **95%** · 데이터·검증은 완료됨(무근거 0).

## 1. 현재 상태 (정확히)
- 데이터: `data/findings.all.json` 199,572건(자체감사 190,189·국회결산 6,200·ALIO 2,722·감사원 461, consult 102·immunity 89). 기타(19) 9.6%.
- 소스본(수정 대상): `data/findings.pap.json`(자체감사 pap) + `data/findings.json`(감사원·ALIO·국회결산·사례집). → 수정 후 `python pipeline/dedup_merge.py`로 `findings.all.json` 재생성.
- 코드북: `data/codebook.json` work_type **01~25**(20채권·21자산·22시설·23정보화·24문서·25교육학사 신설). sector 01~28.
- **정확도 측정용 정답셋**: `data/golden/golden_result.json` — 617건 층화표본에 `gold_work_type`(정답) 있음. 아래 명령으로 즉시 측정:
  ```python
  import json
  gold={g["id"]:g["gold_work_type"] for g in json.load(open("data/golden/golden_result.json",encoding="utf-8"))}
  cur={x["id"]:x["work_type"] for p in ["data/findings.pap.json","data/findings.json"] for x in json.load(open(p,encoding="utf-8")) if x["id"] in gold}
  a=sum(1 for i in gold if cur.get(i)==gold[i]); print(a/len(gold)*100)
  ```

## 2. 왜 77.8%에서 막혔나
- 결정론 키워드 규칙(`pipeline/refine_classification.py`, `reclass_deterministic.py`)은 **~78%가 천장**. 더 넣으면 골든 617에 **과적합**(측정치만 오르고 실제 안 오름).
- 진짜 개선은 **careful 건별 LLM 재태깅**(규칙스크립트 X, 각 지적의 의미를 개별 판정)뿐. 이게 골든에서 gold_work_type을 만든 방식이고 실제 정확도를 올림.

## 3. 이어서 할 일 (권장 순서)
### (A) careful 재태깅 완료 — 핵심
- 대상 저정밀 코드(01·03·08·09·10·13·14·16·19) 34,453건을 12샤드로 분할해 둠: `data/retag_shards/retag_000~011.json` (각 {id,x=지적,t=감사사항명,cur=현재코드}).
- **완료: `retag_002.json`(→`data/retag_out/retag_002.json`)**. **남은 11개: 000·001·003~011.**
- 각 샤드를 **record-tagger 서브에이전트**(또는 careful LLM)로 처리 — 프롬프트 핵심:
  - "규칙 스크립트 만들지 말고 **각 건 의미 개별 판정**". 코드북 01~25 폐쇄집합.
  - 판정기준(골든): 겸직·복무·채용→11 / 사전규격·입찰·용역→02 / 생활기록부·성적·출결·학교운영위·급식·방과후·교육과정→25 / 민방위·소방·시설·안전→22 / 개인정보·보안·전산→23 / 여비·수당·카드·정산·지출→17 / 구상·미수·체납·세입·채권·임대료수납→20, 신규여신·보증→09 / 물품·차량·재물·공유재산→21 / 소송·재결→12 / 위원 제척·심의위원회→08 / 행정재산 사용허가→21 / 산업안전보건관리비→04(공사비). 안 맞으면 19+need_deep.
  - 출력 `data/retag_out/retag_NNN.json`: `{id,work_type,sector|null,confidence,need_deep}`.
- 반영: **`python pipeline/apply_retag.py`** → `pipeline/dedup_merge.py` → 골든 재측정.
- ⚠️ **rate limit**: 세션 한도 소진 시 실패(리셋 시각까지). 완료된 샤드만 반영하고 나머지는 리셋 후.

### (B) 95% 마무리
- careful 재태깅으로 ~88~90% 도달 후, **애매 잔여는 confidence 라우팅**: `tag_confidence<0.6` 또는 `need_deep` → `review:true`(검토중 배지). **노출분 정확도 95%+** 보장.
- 순수 exact 95%가 필요하면: 애매건만 **원문 정독**(pap는 `document_url` 보유) — 토큰 많이 듦.
- **주의**: 골든 617에만 맞추는 규칙 추가 금지(과적합=가짜 정확도). 개선은 **새 표본으로 재측정**해 검증.

## 4. 관련 스크립트
- 반영: `pipeline/apply_retag.py`(retag), `apply_deep.py`(deep), `reclass_deterministic.py`(규칙), `refine_classification.py`(골든기반 교정)
- 병합: `pipeline/dedup_merge.py` · 검증: `pipeline/validate.py`
- 원본(대조): `data/raw_docs/자체감사/_pap_*/manifest.json`(indic_mttr) · `inbox/*` · `alio_3yr.json`·`nabo_3yr.json`

## 5. 절대 지켜야 할 것
- 무근거 생성 금지(source_excerpt는 원문 그대로, 현재 무근거 0). 코드북 폐쇄집합만. 강제분류 금지(모호=19+need_deep). 원본은 별도보관·대조유지.
