#!/usr/bin/env bash
# 매일 배치 업데이트 (인터넷망) — Claude Code(헤드리스)로 신규 감사/면책 사례를
# 키 없이 직접 수집·구조화해 data/findings.json 에 append 하고, 변경분을 git 커밋한다.
#
# 크론 예시 (매일 07:10):
#   10 7 * * *  /경로/audit-helper/scripts/daily_update.sh >> /경로/audit-helper/data/cron.log 2>&1
#
# 사전 준비: Claude Code 설치·로그인, git 원격(origin) 설정(인터넷망 GitHub 등).

set -euo pipefail
cd "$(dirname "$0")/.."
DATE=$(date +%F)
echo "[$(date '+%F %T')] daily_update 시작"

# 1) Claude Code 헤드리스로 신규 수집·태깅 (키 없이 Claude가 공개 페이지를 직접 읽음)
if command -v claude >/dev/null 2>&1; then
  claude -p "$(cat pipeline/daily_prompt.md)" \
    --allowedTools "Read,Write,Edit,Bash,WebFetch,WebSearch" \
    || { echo "claude 실행 실패"; exit 1; }
else
  echo "claude CLI 미설치 — 설치 후 재실행하세요"; exit 1
fi

# 2) (선택) 임베딩 갱신: 모델 연결 후 주석 해제
# python3 pipeline/embed.py || true

# 3) 유효성 검사
python3 - <<'PY'
import json
recs = json.load(open("data/findings.json", encoding="utf-8"))
assert isinstance(recs, list) and all("id" in r for r in recs), "findings.json 형식 오류"
print(f"findings.json OK: {len(recs)}건")
PY

# 4) 변경분만 커밋·푸시 (인터넷망)
if ! git diff --quiet -- data/ 2>/dev/null; then
  git add data/
  git commit -m "chore(data): daily update ${DATE}"
  git push 2>/dev/null || echo "push 생략(원격 미설정) — 로컬 커밋 완료"
else
  echo "변경 없음"
fi
echo "[$(date '+%F %T')] 완료"
