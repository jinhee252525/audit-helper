# 분류·태깅 완성도 100% + 정확도 향상 에이전트 구성안

> 대상: 통합 199,629건(자체감사 190,518·국회결산 6,200·ALIO 2,724·감사원 187)
> 현재 문제: work_type=19(기타) 42%(80,492건), 파싱 노이즈 348건, org_type 기타 35,537, 모범사례 280
> 목표: ① 완성도 100%(모든 필수필드 채움·노이즈 0·무근거 0) ② 분류 정확도 Top-1 ≥ 90% ③ 환각 0(원본 대조 검증·감독)

---

## 1. 완성도 100%의 정의(측정 가능)
- **필드 완비**: 모든 레코드가 source_url·source_excerpt·added_at·work_type·org_name·source_title 보유(국회결산 발간일은 원천 부재→회계연도 갈음, 명시).
- **노이즈 0**: 표지/목차 조각·빈 표 등 무근거 excerpt 레코드 제거.
- **무근거 0(환각 0)**: 모든 source_excerpt 가 원본(raw)에 실제 존재(부분문자열 일치).
- **분류 유효**: work_type·sector·disposition 이 코드북 폐쇄집합 안.
- **정확도**: 정답셋(골든) 기준 work_type Top-1 ≥ 90%, sector ≥ 80%.

## 2. 원본(대조본) 별도 보관 — 검증 가능성의 전제
| 소스 | 원본 위치(대조본) | 재조회 |
|---|---|---|
| 자체감사(pap) | `data/raw_docs/자체감사/_pap_*/manifest.json` | pap API 재조회 가능 |
| ALIO | `data/raw_docs/alio_*.json`(_raw 포함) | ALIO API 재조회 |
| 국회결산 | `data/raw_docs/nabo_*.json` | NABO API 재조회 |
| 감사원 | `data/inbox/감사원/*.pdf`(+PyMuPDF 재추출) | 원문 PDF 보존 |
- 태깅 산출물(findings)과 **물리적으로 분리** → 언제든 대조 가능. 검증 에이전트는 이 대조본만 신뢰.

## 3. 정확도 향상 5방안
1. **규칙 대폭 보강(무료·빠름)**: 코드북 19기능×키워드 확장 + 문제서술어("관리 미흡" 등)만 있는 경우 2차 힌트. → 기타 1차 축소.
2. **LLM 폐쇄집합 태깅(하이브리드)**: 규칙이 기타/저신뢰인 건만 LLM 배치 태깅. **키 없이 `claude -p` 헤드리스**(프로젝트 정책). 1콜당 지적 40~50건 묶음 → 콜 수 최소화. 출력은 **코드북 코드만**(자유생성 금지) + confidence.
3. **이중 태깅 합치(dual-tag agreement)**: 규칙 vs LLM 일치 → 채택·고신뢰. 불일치 → 검수 큐(review:true).
4. **골든셋 측정**: 사람이 확인한 정답 200건으로 Top-1 정확도 측정(보정 전/후). 목표 미달 시 프롬프트·규칙 반복 보정.
5. **저신뢰 검수 큐**: confidence<임계 또는 불일치는 `review:true` 로 표시해 노출 전 사람 확인(담당자 평가 목적 아님).

## 4. 파이프라인 6단계 · 에이전트 구성
```
[0 정제] cleaner(결정론적) : 노이즈 excerpt 제거 + 제외로그
        └ 감독: compliance-reviewer(무근거 0 확인)
[1 규칙보강] record-tagger(규칙) : _WORK_RULES/_SECTOR_RULES 확장 후 전량 재태깅
[2 LLM태깅] tagger-worker × N(병렬) : 기타·저신뢰 건 claude -p 배치, 코드북 폐쇄집합
[3 병합]   orchestrator : 규칙∧LLM 합치, confidence·review 부여
[4 org보강] record-tagger : org_type 판별 개선(피감기관 사전 + 접미사 규칙)
[5 검증]   verifier(독립) : findings ↔ 원본 대조 — (a)무근거 0 (b)코드 유효 (c)필드완비 (d)골든 Top-1
[6 감독]   pipeline-auditor(독립2) : 검증결과 재표본·재대조 → 환각 0 최종판정
```
- **검증(5)과 감독(6)은 서로 다른 에이전트·다른 표본**으로 독립 수행(자기검증 금지, CLAUDE.md 원칙).
- 각 단계 산출은 `data/runs/`에 로그.

## 5. 산출물
- `data/findings.all.json` : 최종 통합(중복제거·노이즈0·완비)
- `data/excluded_records.json` : 제외(노이즈·비지적) 로그
- `data/review_queue.json` : 저신뢰 검수 대상
- `data/golden_set.json` : 정답셋 + 정확도 리포트
- `data/runs/<날짜>-verify.md` / `-audit.md` : 검증·감독 리포트(환각 0 판정)

## 6. 실행 순서(밤샘 자동)
0 노이즈 제거 → 1 규칙보강 재태깅 → 2 LLM 배치(기타/저신뢰) → 3 병합 → 4 org보강 → 5 독립검증 → 6 감독(환각0). 미달 항목은 2~4 반복.
