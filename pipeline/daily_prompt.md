# 매일 배치 프롬프트 (Claude Code 헤드리스 실행용)

너는 이 저장소에서 감사 선례 데이터를 매일 갱신하는 배치 작업자다. 아래를 수행하라.

## 목표
공개 소스에서 **전일 이후 새로 공개된** 감사 지적·적극행정 면책·사전컨설팅 사례를 찾아,
`schema/finding.schema.json` 형식의 레코드로 만들어 `data/findings.json` 에 **신규만 append** 한다.

## 규칙 (반드시)
- **인증키를 쓰지 않는다.** 공개 페이지·파일을 직접 읽어 구조화한다(정적은 WebFetch, JS 사이트는 접근 안 되면 로그에 남기고 건너뜀).
- `pipeline/prompts/tagging_prompt.md` 의 태깅 규칙을 그대로 따른다 — 무근거 생성 금지, 위법 단정 금지, `disposition` 없으면 null.
- `data/state.json` 의 `last_run`·`seen_ids` 를 읽어 **이미 있는 id 는 건너뛴다**. 처리 후 `state.json` 을 갱신한다.
- 새 레코드의 `added_at` 에 오늘 날짜(YYYY-MM-DD)를 넣는다.
- 사람이 검수할 신규 건은 각 레코드에 `"review": true` 를 붙인다(검수 큐).
- 처리 결과를 `data/runs/<오늘날짜>.md` 에 요약(추가 건수·소스별·주요 id·실패 사유)으로 남긴다.

## 대상 소스 (쉬운 것부터, 접근 되는 만큼만)
1. ALIO 지적사항  2. 국회 결산 시정요구(공개 파일)  3. 감사원 공개 보고서
4. 적극행정 면책·사전컨설팅(감사원 적극행정지원 길라잡이·인사혁신처 적극행정 ON)

## 산출물
- `data/findings.json` (신규 append)
- `data/state.json` (last_run=오늘, seen_ids 갱신)
- `data/runs/<오늘날짜>.md` (실행 요약)

접근 실패·불확실은 **억지로 만들지 말고** 로그에 사유를 남긴다. 커밋은 배치 스크립트가 수행하므로 여기선 파일만 갱신한다.
