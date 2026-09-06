# 진행 기록 & 할 일 (정밀) — 2026-09-06

> 어디까지 했는지 + 앞으로 할 것을 정확히 기록. 사용량(LLM 쿼터) 10% 미만이라, 각 할 일에 **[무료]=결정론/내 스크립트, [LLM]=사용량 소모**를 표기.

---

## A. 지금까지 완료 (확정)

### 데이터
- **통합 `data/findings.all.json` = 199,572건**
  - 소스: 자체감사 190,189 · 국회결산 6,200 · ALIO 2,722 · 감사원 461
  - record_type: finding 199,381 · **consult 102 · immunity 89**(사례집 분해 완료)
- 수집: 감사원(2026+, 재분해 144지적) · 국회결산 3년 · ALIO 3년 · 자체감사 pap 전량(중앙·지방·공공기관) · 사례집 3개(사전컨설팅 2025/2023·적극행정면책)
- 제외/격리: 국정감사·재무제표감사·클린아이·robots차단분 / 홈페이지수집분 `_homepage_archive/`
- 로그: `data/collection_failures.json`(실패), `excluded_records.json`(노이즈·비지적·모범사례), `dedup_removed.json`(중복 462)

### 분류(태깅)
- 코드북 `data/codebook.json`: work_type **01~25**(권익위19 + 신설 20채권·21자산·22시설·23정보화·24문서 + **25 교육·학사**) · sector 28 · disposition · audit_type
- 48샤드 LLM 의미분류 → deep-pass(기타 재분류 15샤드) → **기타(19) 42%→10.0%**
- 행위(지적) 단위 분해 완료(감사원 과소분해 재분해 포함)
- 중복제거(ALIO↔자체감사 462) · PII 오탐(날짜→계좌번호) 수정
- 필수필드: **source_url·source_excerpt·added_at 100%, 무근거 0**. 사례집 출처·발간일·수집일·outcome 100%

### 검증·감독 (환각 0)
- 1차 검증(pipeline-auditor)·2차 감독(compliance-reviewer)·deep+사례집 재검증 → **무근거(환각) 0건**, `validate.py` G1+G2 통과
- **분류 정확도 골든 측정(617건 층화)**: 초기 **69.9%** → 결정론 규칙교정 후 **74.9%**(실측)
  - 원인: 16통관·19기타·03계획이 "포괄바구니" 오용, 구코드→신설코드 미이관. 신설 25·23·22는 92~96% 정확.
  - 골든 정답: `data/golden/golden_result.json`(id별 gold_work_type)

### 설계 결정 (다른 세션 반영, `docs/MASTER-PLAN.md`)
- 검색구조 **방식 A(FlexSearch 인덱스+샤딩) 확정** · MVP=상황→검토메모 히어로 1화면 · 원문 온디맨드 · 계약→보조금 도메인팩 · 녹색(sage) 디자인

---

## B. 지금 진행 중 (두고 결과만 받기)
- **careful 재태깅 12샤드 중 1완료·11 진행중** (저정밀 코드 01·03·08·09·10·13·14·16·19 = 34,453건 대상, 건별 정독)
  - 입력 `data/retag_shards/` · 출력 `data/retag_out/` · **아직 findings 미반영**
  - ⚠️ 사용량<10%라 일부 rate limit로 실패 가능 — 완료된 것만 반영 예정

---

## C. 앞으로 할 일 (정확한 순서)

### C-1. 재태깅 마무리 [무료] — 사용량 회복 불필요
1. retag 11샤드 완료(또는 rate limit 중단) 대기 → **`python pipeline/apply_retag.py`** 로 완료분만 반영
2. **골든 재측정**(`data/golden/golden_result.json` 대조, 무료) → 정확도 실측치 확인
3. `python pipeline/dedup_merge.py` 재실행 → `findings.all.json` 갱신

### C-2. 신뢰도 라우팅으로 "노출분 95%" [무료]
4. `tag_confidence`·`need_deep` 기준으로 **고신뢰=확정노출 / 저신뢰=검토중 배지+검수큐** 분리. → 노출분 정확도 95%+ 보장(순수 exact 95%는 원문정독=LLM 대량 필요, 사용량 회복 후 선택)

### C-3. 검색앱(프론트) [무료 대부분]
5. **FlexSearch 인덱스 빌드 + 샤딩**(연도·기관유형·work_type별 JSON) — `pipeline/build_index.py` 신규
6. **히어로 UI 프로토타입**(`prototypes/`): 상황입력→유사선례→같음/다름→원문 온디맨드→증빙목록→**결재용 검토메모**(+면책/컨설팅) 1화면. 녹색 디자인
7. 교육 개별학교 필터 기본 숨김 · 품질 배지(목록만/본문확보/근거대조)

### C-4. 고도화 [LLM 필요 — 사용량 회복 후]
8. **임베딩(F1 유사검색)** 구축 — 사용량 소모(임베딩은 LLM보다 저렴하나 필요)
9. 남은 retag(사용량 부족으로 못한 샤드) + 원문정독으로 exact 정확도 향상(선택)
10. F8 지적↔면책 대조 · F10 신규피드 · 대시보드 인사이트(AXIS B) · GitHub Pages 배포 · 매일배치(헤드리스 로그인)

---

## D. 핵심 파일 지도
- 데이터: `data/findings.all.json`(최종 통합) · `findings.pap.json`·`findings.json`(소스본) · `data/codebook.json`
- 파이프라인: `pipeline/apply_retag.py`·`apply_deep.py`·`reclass_deterministic.py`·`refine_classification.py`·`dedup_merge.py`·`map_pap.py`·`collect_pap_central.py`
- 검증: `pipeline/validate.py` · 골든 `data/golden/`
- 원본(대조): `data/raw_docs/자체감사/_pap_*/manifest.json` · `data/inbox/감사원|사전컨설팅/*.pdf` · `data/raw_docs/alio_3yr.json`·`nabo_3yr.json`
- 계획: `docs/MASTER-PLAN.md`(최신) · 이 문서 `docs/STATUS-AND-TODO.md`
