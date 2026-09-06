# 감사 선례 도우미 (Audit Precedent Helper)

> 이 파일은 Claude Code가 이 저장소에서 작업할 때 참고하는 프로젝트 지침이다.
> 상세 기획은 `docs/PRD.md`를 읽는다.

## 무엇을 만드는가
감사원·국회 결산·중앙부처 자체감사·지방자치단체 종합감사에 흩어진 **지적사례**와
**적극행정 면책·사전컨설팅 사례**를 하나의 지식으로 모아, 담당자가
- (AXIS A) 업무를 수행하는 순간 유사 지적을 **결재 전에** 확인하고,
- (AXIS B) 반복 지적의 패턴에서 **제도개선 과제**를 발굴하도록 돕는 도구.

핵심 성격: "감사자료 검색기"가 아니라 **상황→선례 매핑** 도구.
"하지 마라"가 아니라 면책사례를 나란히 두어 **"과감히 하되 보호받는 길"**까지 제시한다.

## 절대 규칙 (품질·신뢰가 곧 채택 조건)
1. **위법·부당을 단정하지 않는다.** 유사 사례와 근거만 제시하고 판단은 담당자·결재권자.
2. 모든 결과 카드에 **출처 원문 링크**와 **처분종류**(없으면 "미부과·해당없음")를 반드시 표시.
3. **근거 없는 사례를 생성하지 않는다.** 무근거 서술 금지.
4. 근거법령의 현행 여부는 확인 전이면 **"확인 필요"**로 명시(임의 현행 처리 금지).
5. **담당자 평가·징계 목적으로 쓰지 않는다.** 로그·피드백은 품질 개선에만.

## 데이터 정책 (중요)
- **"키 없이"의 진짜 뜻 = 프로젝트에 생성형(LLM) 키를 심지 않는다.** 판정(태깅·분석)에 생성형 LLM은 쓸 수 있으나, **키는 (a) Claude Code("이 Claude", 로그인 세션/헤드리스 `claude -p`) 또는 (b) 운영자 본인 키(BYOK)** 로 공급한다. → 태깅 모듈은 **키를 환경변수/설정에서 읽는 pluggable 구조**(Claude Code 경로 + BYOK LLM 경로 모두 지원), 키를 코드·저장소에 하드코딩 금지.
- **공공데이터 오픈API 키(data.go.kr, 법제처 OC 등)는 정상 사용한다.** 이건 제한 대상이 아니다(무료 공개키). 역시 저장소에 커밋 금지(환경변수/시크릿).
- **수집은 robots.txt를 준수한다.** 허용 소스(예: ALIO)는 공개 페이지 직접 읽기. **robots가 막은 소스(감사원 bai·클린아이 = `Disallow: /`)는 스크래핑하지 말고 공식 오픈API/공공데이터셋(data.go.kr)으로** 받는다. JS 렌더링 + 허용 소스는 브라우저형 수집(Claude in Chrome).
- 법령 조문/현행성은 법제처 OC API로. → `docs/legal-api.md`
- 모든 레코드는 `schema/finding.schema.json`을 따른다. 이 스키마가 프론트·파이프라인·내부배포의 **접착면**이다.
- 샘플 데이터(`data/*.sample.json`)는 **합성 예시**다(실제 감사기록 아님). 개발·테스트용 픽스처.

## 스키마 요점
- `record_type`: finding(지적) | immunity(면책) | consult(사전컨설팅)
- 필터 축: `work_type`(업무유형) · `org_type`(기관유형) · `year`(연도) · `legal_basis[].law`(법령)
- `disposition`은 **선택값(null 허용)** — 국회 시정요구·통보·개선요구·면책은 처분이 없음
- `immunity`: record_type=immunity일 때 `{outcome:"인정|불인정", requirements:[...]}`
- `budget_link`: 예산·사업 연결(있을 때만) `{program, budget_ref, confidence}`
- `added_at`: 신규 피드·구독(F10) 기준 날짜

## 재사용·배포 (AI 정부 실험실) — `docs/reuse-and-landscape.md`
- 이 과제는 행안부·NIA **AI 정부 실험실**(공공 GitLab, 인터넷망 검증→보안게이트→업무망)에 등록해 확산하는 것을 전제로 한다. 우리 Track 1/2가 그 구조와 일치. **단, 지금은 인터넷망 운영이 우선이고 업무망(내부망) 이전은 아주 나중이다.**
- **새로 만들기 전에 재사용부터 검토:**
  - **F4 조문 뷰어** → 소방청 `korean-law-markdown`(법제처 XML→마크다운) 재사용.
  - **F9 예산·사업 연결** → `나라예산 한눈에`(예산 자동 수집·검색) 재사용.
  - 계약/여비 업무유형 → `조달법령 검색`, `contract-king/contract_easy`, `여비업무통합도우미` 참고.
- 재사용 시 각 과제 **라이선스 확인** 필수.
- 직접 중복(감사 지적·면책 통합 검색) 과제는 확인되지 않음 → 축(지적·면책·발굴)은 직접 구축.

## 매일 배치 업데이트 (인터넷망 · Claude Code 연결) — 핵심 기능
- 지금 단계는 **인터넷망에서 검색·활용**하고, 데이터는 **매일 배치로 자동 갱신**한다. 내부망 이전은 나중.
- 실행: `scripts/daily_update.sh` 를 크론에 등록 → **Claude Code 헤드리스(`claude -p`)** 가 `pipeline/daily_prompt.md` 대로 신규 사례를 **키 없이** 수집·태깅해 `data/findings.json` 에 append → 변경분 git 커밋/푸시.
- 증분·중복 방지: `data/state.json`(last_run·seen_ids)로 이미 있는 id 는 건너뜀. 실행 요약은 `data/runs/<날짜>.md`.
- 검수 큐: 신규는 `review:true` 로 표시해 사람이 확인 후 노출.
- 지속 저장소 = **인터넷망 GitHub 커밋**(정적 사이트면 커밋 시 자동 재배포). 내부망 GitLab 은 나중.
- 어댑터가 코드로 구현되면 결정론적 경로 `pipeline/daily_update.py` 로 대체 가능(현재는 Claude 경로 사용).

## MVP 범위 (M0)
- **포함:** F1 유사검색, F2 사전점검 체크리스트, F8 지적↔면책 대조, F10 신규 피드
- **제외(후속):** F3 문서 하이라이트, F4 법제처 조문 뷰어(자리만), F5 발굴 보드, F9 예산연결
- Track 1(정적 사이트 + 브라우저 검색)로 방식 검증 → 검증 후 Track 2(공통기반)로 이식

## 개발 순서
1. `schema/finding.schema.json` 확정, `data/findings.sample.json`로 픽스처 확보
2. `app/`의 정적 검색·필터·카드(지적/면책 배지, 처분 결측 처리)를 완성
3. `pipeline/`로 1개 소스(ALIO 또는 국회 결산) 실제 수집→태깅→findings.json 생성
4. `pipeline/embed.py`로 embeddings.json 생성, 브라우저 시맨틱 검색으로 F1 고도화
5. 정답셋으로 Top-k 측정 → 프롬프트·태깅 보정
6. F8(면책 대조)·F10(신규 피드) → 이후 F4/F5/F9

## 실행
```bash
# 정적 앱은 fetch 때문에 로컬 서버 필요 (저장소 루트에서 실행)
python3 -m http.server 8000   # http://localhost:8000/app/
# 파이프라인
pip install -r requirements.txt
python pipeline/collect.py && python pipeline/structure.py && python pipeline/embed.py
# 매일 배치(인터넷망): 크론에 등록
bash scripts/daily_update.sh
```

## 코딩 규칙
- 프론트는 의존성 최소(바닐라 JS 우선). 라이브러리는 필요할 때만.
- 데이터는 정적 JSON. 상태는 URL 쿼리/메모리(브라우저 저장소 남용 금지).
- 사용자 언어는 한국어. 공무원에게 익숙한 용어를 쓴다.
