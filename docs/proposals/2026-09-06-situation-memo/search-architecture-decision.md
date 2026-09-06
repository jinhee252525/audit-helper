# 검색구조 결정 제안: 방식 A

기존 `docs/search-architecture.md` 비교를 존중하되, **결정만** 여기 적는다 (원본 비교문 유지).

## 결정
**1차 = 방식 A (FlexSearch/MiniSearch + 연도·기관유형 샤딩)**

### 이유
- GitHub Pages 순수 정적
- 19만 건을 단일 JSON으로 못 올림 → 색인 + lazy shard
- 오프라인·업무망 이전에 유리
- 이후 임베딩(F1) 결합이 쉬움

### 흡수
- **C**: 교육 개별학교 등 대량·저연관은 **필터 기본 숨김** (데이터 삭제 아님)
- 대시보드: **사전집계 JSON** (A의 집계 약점 보완)

### 승격 조건 (나중에 B)
복합 필터·SQL 집계가 A로 버거울 때 SQLite-wasm(+httpvfs) 검토

## 구현 순서 (data 건드리기 전 설계만)
1. 경량 검색 레코드 스키마 정의 (id, title/summary 단문, org, year, work_type, record_type, text_quality, shard_key)
2. 빌드 스크립트 설계 (findings → index/ + shards/) — **실행은 data 안정화·사용자 OK 후**
3. 앱은 색인 로드 → id 매칭 → shard fetch