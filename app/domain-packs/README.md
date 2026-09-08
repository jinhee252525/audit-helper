# 도메인 팩 (domain packs)

엔진(히어로·검색·메모)은 하나. 분야별로 입력 힌트 · 업무유형 제안 · 체크리스트 · 메모 placeholder만 갈음한다.
시드 사례 필터·임베딩은 후속(MASTER-PLAN · design-domain-packs.md).

## 파일
- contract.json — 계약·용역 (1단계)
- subsidy.json — 보조금·정산 (2단계)

## JSON 스키마 (공통)
- id — 팩 ID (contract | subsidy)
- label / labelLong — UI 짧은/긴 표기
- situationDomain — situationDomain 필 텍스트
- defaultWorkType — situationWorkType 기본값
- workTypes — 제안 업무유형 칩
- situationPlaceholder — 상황 textarea placeholder
- checklist — 결재 전 점검 프롬프트 (id, prompt, hint)
- evidenceHints — 증빙 후보 템플릿 문구
- memoFieldHints — 메모 필드 placeholder (overview, refs, diff, grounds, open, decision)

## 앱 배선
히어로 화면에서 팩 선택(계약|보조금) 후 domain-packs JSON을 불러와 필·placeholder를 채운다.
로드 실패 시 hero-sample 기본값 유지.

## 규칙
- 바닐라만. 새 외부 패키지·CDN 금지.
- 대시보드 dual-mode와 무관(히어로만).
- 본문 미확보(목록만) 건으로 체크리스트·검토메모 근거 생성 금지(절대규칙).
