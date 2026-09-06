---
name: audit-tagging
description: 감사 지적/면책/사전컨설팅 원문을 finding.schema.json 레코드로 태깅하는 재사용 절차. 코드북(권익위 관련기능19·발생분야28) 폐쇄형 강제 + 원문 앵커 + 규칙우선/AI보조로 고정확·무근거차단. record-tagger·daily-updater가 매 수집분·매일 배치에서 동일하게 사용.
---

# 감사 태깅 절차 (재사용·고정확)

목표: 어떤 소스(ALIO·클린아이·국회·감사원)의 원문이든 **동일 절차**로 스키마 레코드를 만든다. 정확도와 무근거 차단이 최우선.

## 입력
- 문서 텍스트/마크다운(kordoc 추출) + 메타(source, org_type, org_name, audit_org, year, source_url, document_url)
- 코드북: `data/codebook.json` (관련기능·발생분야·처분·감사종류)

## 단계
1. **개요 추출(규칙)**: 문서 상단에서 `audit_org`(감사기관), `audit_type`(감사종류→codebook 매칭), 피감기관 확인.
2. **지적 분해(규칙)**: 표(마크다운)·`○` 항목 단위로 지적 1건=레코드 1건. 제목만 있으면 1건.
3. **결정론 필드(규칙, 정규식)** — 여기서 정확도를 확보:
   - `source_excerpt` = 원문 항목 **그대로**(무근거 차단의 핵심).
   - `disposition` = 괄호 안 토큰 중 codebook `disposition`에 있는 것만. 없으면 `null`(추정 금지).
   - `legal_basis[]` = 「」 인용 법령(law_type: 조례→자치법규 / 규정·지침·훈령·예규·고시·규칙→행정규칙 / 그외 법령).
4. **의미 분류(AI 보조, 폐쇄형)**:
   - `work_type` = 관련기능 코드(01~19) 중 **행위** 기준 1개. `sector` = 발생분야(01~28) 중 **분야** 기준(없으면 null). `finding_type` = 세부기능(a/b/c/z).
   - **반드시 codebook 코드값만**. 애매하면 work_type=`19`(기타), sector=null — 억지 배정 금지.
   - 애매 건은 self-consistency(2~3회 질의 다수결).
5. **요약**: `summary`는 `source_excerpt` 범위 내 사실만 1~2문장(새 사실 창작 금지).
6. **레코드 조립**: 필수필드(§8) 모두. id=`{SOURCE}-{year}-{docId}-{itemIdx}`(안정적), `added_at`=수집일.
7. **자기검증→독립검증**: `python pipeline/validate.py`(G1·G2) 통과 확인 후, **자기 승인 금지** — `compliance-reviewer`·`pipeline-auditor`가 원문 대조 판정.

## 정확도 원칙 (사람 검수 없이)
- 규칙으로 뽑을 수 있는 건(처분·법령·발췌) 규칙으로 = 결정론적 정확.
- 폐쇄형 코드북 = 엉뚱한 값 원천 차단.
- 골든셋(정답 라벨) 자동채점으로 관련기능/발생분야 분류 정확도를 반복 측정→프롬프트·규칙 보정.
- 원문 앵커(source_excerpt)로 사용자·감독이 즉시 검증 가능.

## 금지
없는 처분·법령·분야를 채우지 않는다. 위법·부당 단정하지 않는다. 코드북 밖 값 금지.
