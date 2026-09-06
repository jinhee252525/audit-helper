---
name: source-adapter
description: 새 감사 소스(클린아이·국회결산·자체감사·감사원 등)를 인증키 없이 수집하는 어댑터를 추가하는 재사용 절차. ALIO 어댑터(collect_alio.py) 패턴을 표준으로, 증분·멱등·정중한 수집을 보장. source-collector·pipeline-dev가 소스 확장 시 사용.
---

# 소스 어댑터 추가 절차 (키 없음·증분·운영형)

목표: ALIO에서 검증된 패턴으로 새 소스를 붙인다. 모든 어댑터는 **키 없음 + 증분 + 멱등 + 정중(rate-limit)** 을 지킨다.

## 1) 엔드포인트 발견 (키 없이)
- 정적 페이지: `requests`/WebFetch로 바로.
- JS 렌더링(클린아이 등): 브라우저(내장/Claude in Chrome)로 열어 **네트워크 탭에서 내부 JSON 엔드포인트**를 찾는다(ALIO는 `findPointList.json` 발견). 봇 차단 시 로그 남기고 브라우저형으로.
- 발견한 엔드포인트/URL 패턴·페이지네이션 파라미터를 문서화.

## 2) 어댑터 구현 (collect_alio.py를 템플릿으로)
- `requests` + **고정 공개호스트 화이트리스트**(SSRF 방지, Semgrep 통과). 정수 파라미터만.
- **증분**: `data/state.json`의 `seen_ids`를 읽어, 목록이 최신순이면 **이미 본 id를 만나면 중단**(전량 재수집 금지).
- **정중**: 요청 간 sleep + 재시도/백오프(타임아웃·5xx). robots 존중.
- 원문·메타를 공통 형태로 저장: `{source, org_type, org_name, audit_org?, year, source_url, document_url, files[]}`.
- 문서 파일은 `kordoc`으로 추출(HWP/PDF/HWPX/이미지OCR) → 텍스트/마크다운.

## 3) 공통 파이프라인에 연결
수집 → kordoc 추출 → `audit-tagging` 스킬로 태깅 → `validate.py`(G1·G2) → `merge_incremental`(멱등) → state 갱신 → commit.

## 4) 검증
- `pipeline-auditor`: 수집 건수·URL 진위, 파싱 실추출 대조.
- `test-engineer`: 증분 2회 실행 시 중복 0(멱등) 테스트.
- `security-reviewer`: 호스트 고정·시크릿 없음·개인정보 미저장.

## 소스별 메모
- 클린아이(cleaneye.go.kr): 지방공공기관 통합공시 — ALIO 유사 JSON 가능성, 미조사.
- 국회 결산: 공개 파일(시정요구) — 파일 다운로드형.
- 자체감사: 기관별 산재 — 기관 목록 기반.
- 감사원(bai.go.kr): **봇 차단** — Claude in Chrome 필요.

## 금지
인증키 사용 금지(법제처 F4 제외). 접근 실패를 성공으로 계상 금지. 없는 데이터 생성 금지.
