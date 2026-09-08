# 진행 기록 & 할 일 (정밀) — 2026-09-07

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

## B0. 오늘 완료 (2026-09-08, 로컬 실측)

- **환경 동기화**: `git fetch/pull` 정상, HEAD=`d70d43f`(origin/main과 동일). GitHub 인증 복구(jinhee252525). Python 미설치 → **Node 정적 서버**로 스모크(신규 패키지·CDN 없음).
- **스모크 PASS**:
  - 히어로/검색(`app/index.html`·`app/app.js`): 실인덱스(`app/data/index`, 24샤드·199,572건) 연결, "수의계약 견적" → 실제 지적사례 카드(출처·처분·품질/신뢰 배지) 정상, 합성경고 꺼짐.
  - 대시보드(`app/dashboard.html`): 렌더 정상.
- **대시보드 Pages 대응(task B)**: dashboard.html이 `data/findings.json`(gitignore, Pages 미배포)만 쓰던 것을 **이중화**.
  - 1순위 전체 `findings.json`(로컬·상호작용 필터), 폴백 **집계본** `app/data/dashboard-agg.json`(커밋·배포 대상, 31KB).
  - 집계본 생성기: `pipeline/build_dashboard_agg.js`(의존성 없는 Node) — `node pipeline/build_dashboard_agg.js`.
  - Pages 시뮬레이션(app/만 루트)에서 findings 404 시 **집계 요약 모드**(배너·필터 비활성·KPI/차트·샘플카드 24) 동작 확인. 두 모드 콘솔 에러 0(폴백 404는 정상).
  - 요약뷰 record_type 안내 문구를 실측(consult 102·immunity 89)으로 동적화.
- **Pages 워크플로**: `.github/workflows/deploy-pages.yml` 로컬 생성(범위 `app/`). **푸시는 OAuth `workflow` 스코프 없음으로 거부** → GitHub 웹에서 수동 생성 필요(내용은 `docs/PAGES.md`와 동일). 이후 **Settings→Pages→Source=GitHub Actions**(공개 여부 확인).

---

## B. 직전에 완료·인계됨 (2026-09-07)

- **careful 재태깅 12샤드 완료·보수적 병합 반영** (저정밀 코드 01·03·08·09·10·13·14·16·19 대상)
  - 입력 `data/retag_shards/` · 출력 `data/retag_out/` · **apply 보수적 병합으로 pap·json·all에 반영 완료**
  - 보고서: `data/retag_out/_apply_report.json`
  - 골든 실측: **findings.all 전체 ~76.0%** · retag-overlap **~54.4%**(보수적 수용 후)
  - 통계 예: rule_accept 3,008 · rule_hold_cur 23,992 · claude_keep 7,453 · all 갱신 34,278건
  - `python pipeline/dedup_merge.py`는 **선택/스킵 가능**: all이 이미 pap+json 반영본과 동기화됨(재실행은 대용량·불필요 시 생략)

---

## C. 앞으로 할 일 (정확한 순서)

### C-1. 재태깅 마무리 [무료] — 완료(2026-09-07)
1. ~~retag 샤드 완료 → apply_retag 보수적 반영~~ 완료
2. ~~골든 재측정~~ 완료 → full **~76.0%**, retag-overlap **~54.4%**
3. `python pipeline/dedup_merge.py` — **optional/skip**(all 이미 갱신). 소스본만 따로 고친 뒤에만 재실행

### C-2. 신뢰도 라우팅으로 "노출분 95%" [무료] — 앱 반영(이번 작업)
4. `tag_confidence`·`review` 기준 **고신뢰=확정노출 / 저신뢰·검토=「검토중」배지**. 정렬 고신뢰 우선.
   - 힌트: `min_confidence_expose_hint=0.6`(manifest `default_filters`)
   - 순수 exact 95%는 원문정독=[LLM] 대량 필요 → 사용량 회복 후 선택(C-4)

### C-3. 검색앱(프론트) [무료 대부분] — 인덱스·프로토타입 완료 / 앱 배선(이번 작업)
5. **FlexSearch 인덱스 빌드 + 샤딩** 완료 — 24샤드 (`app/data/index/manifest.json` + `shards/`)
   - 재빌드: `python pipeline/build_index.py --input data/findings.all.json --out app/data/index`
6. **히어로 UI 프로토타입** 완료 — `prototypes/situation-memo`, `prototypes/hero.html`
7. **앱 배선(이번 작업)**: `app/` → shard 인덱스 lazy-load · 개별학교 기본 숨김 · 품질 배지(목록만/본문확보/근거대조) · 신뢰도 배지

### C-4. 고도화 [LLM 필요 — 사용량 회복 후] — 이후
8. **임베딩(F1 유사검색)** 구축 — [LLM](임베딩은 생성보다 저렴하나 필요)
9. 골든∩저신뢰 thin LLM 정독으로 exact **~78–80%** 목표(전량 `need_deep` 회피) — [LLM]
10. F8 지적↔면책 대조 · F10 신규피드 · 대시보드 인사이트(AXIS B) · GitHub Pages 배포 · 매일배치(헤드리스 로그인) — 혼합([무료]/[LLM])

---


## E. 출장·폰 완성 플랜 (2026-09-07) — 내일부터

목표: 출장 중 **MVP를 거의 완성**. 노트북의 19만 건 findings·인덱스 샤드는 Git에 없음 → 폰에서는 **코드·UI·배포·문서**로 완성도를 올리고, 대용량 정확도/인덱스는 복귀 후(또는 Pro 클라우드)에.

### E-1. 폰에서 바로 (우선순위 · 거의 전부 [무료])
1. **히어로 합치기**: `prototypes/situation-memo/` → 살아 있는 `app/` 1화면 (상황→유사선례→같음/다름→원문 온디맨드→증빙→결재용 검토메모). demo/sample로 동작 확인.
2. **sage 녹색 디자인**을 `app/`에 반영 (프로토·palette-lock 기준).
3. **F8 UI**: 지적 카드 옆 면책/컨설팅 나란히 (샘플 데이터로).
4. **F10 UI**: 신규 피드 / `added_at`·`review` 큐 셸.
5. **GitHub Pages**(또는 정적 미리보기): demo 기준으로 폰 브라우저에서 열어보기.
6. **도메인팩 골격**: 계약 → 보조금 (MASTER-PLAN).
7. **대시보드**: `dashboard-agg.json` 소비(소량 커밋 가능) / AXIS B 인사이트 자리.
8. 문서 동기화: 이 파일 + `HANDOFF-accuracy.md` + `MASTER-PLAN.md`를 작업 기준으로 유지.

### E-2. 폰에서 가능하나 조건 있음
- **Cloud Agents(Pro)**: 저장소 직접 수정·PR에 가장 편함. 현재 플랜에선 Cloud Agents 불가 → Pro 업그레이드 또는 채팅으로 파일 단위 반영(GitHub) 경로.
- **thin LLM / 임베딩(C-4.8–9)**: 골든·저신뢰 샘플은 레포에 있음(`data/golden/`). 전체 findings·인덱스 재빌드는 노트북 또는 데이터 동기화 후에.
- **정확도 ~78–80%**: 출장 중엔 샘플·프롬프트·검수큐 UX까지. 전량 careful은 복귀 후.

### E-3. 복귀 후(노트북) 한 번에
- `python pipeline/build_index.py --input data/findings.all.json --out app/data/index` 재빌드 확인
- 앱을 실인덱스에 붙여 스모크
- (선택) 골든∩저신뢰 thin LLM → 골든 재측정
- 매일배치·헤드리스는 네트워크·로그인 여유 있을 때

### E-4. 출장 중 "완성" 정의 (체크)
- [x] 히어로 1화면이 `app/`에서 demo로 끝까지 흐름 — **done** (sage UI 포함, branch `feat/phone-trip-mvp`)
- [x] 품질·신뢰 배지 + 개별학교 기본 숨김 유지 — **done** (`feat/phone-trip-mvp`)
- [x] F8·F10 UI 자리 동작(샘플) — **done** (`feat/phone-trip-mvp`)
- [ ] Pages(또는 동등)로 폰에서 URL 오픈 — 사용자 OK 대기
- [x] STATUS에 남은 C-4만 명확히 남김 — **done** (C-4는 출장 후 LLM 작업으로 유지)

> 2026-09-08: 폰 MVP(히어로·sage·F8/F10 바닐라) 반영 → branch `feat/phone-trip-mvp`.

## D. 핵심 파일 지도
- 데이터: `data/findings.all.json`(최종 통합) · `findings.pap.json`·`findings.json`(소스본) · `data/codebook.json`
- 인덱스: `app/data/index/manifest.json` · `app/data/index/shards/shard-XXXX.json`
- 파이프라인: `pipeline/apply_retag.py`·`apply_deep.py`·`reclass_deterministic.py`·`refine_classification.py`·`dedup_merge.py`·`build_index.py`·`map_pap.py`·`collect_pap_central.py`
- 검증: `pipeline/validate.py` · 골든 `data/golden/` · 재태깅 보고서 `data/retag_out/_apply_report.json`
- 원본(대조): `data/raw_docs/자체감사/_pap_*/manifest.json` · `data/inbox/감사원|사전컨설팅/*.pdf` · `data/raw_docs/alio_3yr.json`·`nabo_3yr.json`
- 계획: `docs/MASTER-PLAN.md`(최신) · 이 문서 `docs/STATUS-AND-TODO.md`
