# 법제처 국가법령정보 공동활용 Open API (F4 — 조문 뷰어)

> **키를 쓰는 유일한 곳.** 감사자료 수집에는 키를 쓰지 않는다(CLAUDE.md 데이터 정책).

## 인증
- 사이트: <https://open.law.go.kr/LSO/openApi/guideResult.do>
- 신청 후 받은 **OC 값**(보통 신청 이메일 아이디)을 모든 요청에 `OC=<값>` 으로 붙인다.
- 키는 서버측(Track 2) 또는 빌드/배포 파이프라인에 두고, 정적 프론트에 노출하지 않는다.

## 주요 대상(target)
| 용도 | target | 가이드 |
|---|---|---|
| 법령 본문/조항호목 | `law` | 현행법령(공포일) 본문 조항호목 조회 |
| 행정규칙(훈령·예규) | `admrul` | 행정규칙 본문 조회 |
| 자치법규(조례·규칙) | `ordin` | 자치법규 본문 조회 |
| 판례 | `prec` | 판례 본문 조회 |

각 가이드에서 정확한 파라미터(ID/MST, JO=조번호, type=XML/JSON 등)를 확인한다.
- 목록: `https://www.law.go.kr/DRF/lawSearch.do?OC=...&target=law&type=JSON&query=...`
- 본문: `https://www.law.go.kr/DRF/lawService.do?OC=...&target=law&type=JSON&MST=...` (조문 지정 시 JO 등)

## 구현 메모
- 레코드의 `legal_basis[]`(law, article, law_type)로 target을 고르고 조문 본문을 받아 그대로 표시.
- **조문 본문은 API 응답을 그대로** 보여준다(임의 요약·변형 금지).
- 현행성: 응답의 시행일/개정 정보로 `basis_status`(현행/개정/폐지)를 채운다. 불명확하면 "확인필요" 유지.
- 캐시 권장(같은 조문 반복 조회 방지).

## 참고 링크
- 국가법령정보 공동활용: <https://open.law.go.kr/LSO/main.do>
- 공공데이터포털(법제처 공유서비스): <https://www.data.go.kr/data/15000115/openapi.do>
