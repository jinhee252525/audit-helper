"""매일 배치 오케스트레이터 (결정론적 경로).

Claude 헤드리스(daily_prompt.md) 대신, 소스 어댑터가 코드로 구현된 뒤 쓰는 경로.
collect -> structure(tag) -> 증분 병합 -> (embed) -> state/run log 갱신.

지금은 collect/structure 가 스텁이라 실제 수집은 daily_prompt.md(Claude) 경로를 쓴다.
"""
from pathlib import Path
from datetime import date
import json

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FINDINGS = DATA / "findings.json"
STATE = DATA / "state.json"
RUNS = DATA / "runs"


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"last_run": None, "seen_ids": []}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_incremental(new_records: list[dict]) -> tuple[int, int]:
    existing = json.loads(FINDINGS.read_text(encoding="utf-8")) if FINDINGS.exists() else []
    seen = {r["id"] for r in existing}
    added = [r for r in new_records if r["id"] not in seen]
    FINDINGS.write_text(json.dumps(existing + added, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(added), len(existing) + len(added)


def write_run_log(added: int, total: int, notes: str = "") -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    (RUNS / f"{today}.md").write_text(
        f"# {today} 업데이트\n\n- 추가: {added}건 / 전체: {total}건\n{notes}\n", encoding="utf-8"
    )


def run(collected: list[dict] | None = None) -> None:
    """collected: 이미 태깅된 레코드 리스트(어댑터 산출). None이면 안내만."""
    if not collected:
        print("collect/structure 어댑터 미구현 — Claude 경로(scripts/daily_update.sh)를 사용하세요.")
        return
    state = load_state()
    added, total = merge_incremental(collected)
    state["last_run"] = date.today().isoformat()
    state["seen_ids"] = sorted({*state.get("seen_ids", []), *[r["id"] for r in collected]})
    save_state(state)
    write_run_log(added, total)
    print(f"추가 {added}건 / 전체 {total}건")


if __name__ == "__main__":
    run()
