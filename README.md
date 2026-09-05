# 감사 선례 도우미 (Audit Precedent Helper)

감사원·국회 결산·중앙부처 자체감사·지자체 종합감사의 **지적사례**와 **적극행정 면책·사전컨설팅 사례**를
모아, 담당자가 업무 순간과 제도개선 발굴 순간에 선례를 **결재 전에** 확인하게 하는 도구.

> 자세한 지침은 `CLAUDE.md`, 기획은 `docs/PRD.md`.

## 빠른 시작 (정적 PoC)
```bash
# 저장소 루트에서 실행
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000/app/  접속
```
샘플 데이터(`data/findings.sample.json`, **합성 예시**)로 검색·필터·카드가 바로 뜬다.

## 구조
```
audit-helper/
├─ CLAUDE.md                # Claude Code 작업 지침
├─ README.md
├─ requirements.txt
├─ schema/
│  └─ finding.schema.json   # 지적·면책 통합 표준 레코드
├─ data/
│  ├─ findings.sample.json  # 합성 예시 (실제 기록 아님)
│  ├─ checklists.sample.json
│  └─ (findings.json / embeddings.json ← 파이프라인 산출)
├─ app/                     # 정적 프론트(Track 1)
│  ├─ index.html · app.js · styles.css
├─ scripts/
│  └─ daily_update.sh       # 매일 배치(인터넷망): Claude Code 헤드리스로 수집→append→커밋
├─ pipeline/                # 오프라인 (수집→태깅→임베딩)
│  ├─ collect.py · structure.py · embed.py · daily_update.py
│  └─ prompts/tagging_prompt.md · daily_prompt.md
└─ docs/
   ├─ PRD.md · legal-api.md · reuse-and-landscape.md
```

## 매일 배치 업데이트 (인터넷망)
```bash
# Claude Code 설치·로그인 + git 원격(origin) 설정 후, 크론에 등록
crontab -e
# 매일 07:10 실행:
10 7 * * *  /경로/audit-helper/scripts/daily_update.sh >> /경로/audit-helper/data/cron.log 2>&1
```
`scripts/daily_update.sh` → `claude -p`(헤드리스)가 `pipeline/daily_prompt.md` 대로 신규 사례를
키 없이 수집·태깅해 `data/findings.json`에 append → 변경분 git 커밋. 상태는 `data/state.json`, 로그는 `data/runs/`.
> 내부망(업무망) 이전은 아주 나중. 지금은 인터넷망 운영 + 매일 배치가 기본.

## 개발 로드맵(MVP)
1. 스키마 확정 → 샘플로 화면 완성
2. `pipeline/`으로 1개 소스(ALIO/국회 결산) 실제 수집→태깅→`data/findings.json`
3. `embed.py`로 임베딩 → 브라우저 시맨틱 검색(F1 고도화)
4. F8(면책 대조)·F10(신규 피드) → 이후 F4(법제처 조문)·F5(발굴 보드)·F9(예산연결)

## 원칙(요약)
- 위법 판정 금지 · 출처/처분/근거상태 항상 표시 · 무근거 생성 금지 · 평가목적 사용 금지
- 수집은 키 없이 Claude가 직접 · 법제처 키는 조문 조회에만
