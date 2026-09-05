"""구조화 (structure) — 원문을 '지적 1건 = 레코드 1건'으로 분해하고 LLM으로 태깅한다.

이 단계가 품질을 결정한다. 결과는 schema/finding.schema.json 을 반드시 따른다.
태깅 지침은 pipeline/prompts/tagging_prompt.md 참조.

규칙:
- 근거 없는 사례는 만들지 않는다(무근거 서술 금지).
- 처분수위(disposition)가 없으면 null 로 둔다(추정 금지).
- record_type 으로 지적/면책/사전컨설팅을 구분한다.
- id 로 중복 제거(증분 축적 시 이미 있는 id 는 건너뜀).
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "findings.json"
PROMPT = (Path(__file__).resolve().parent / "prompts" / "tagging_prompt.md").read_text(encoding="utf-8")


def tag_document(text: str, source_meta: dict) -> list[dict]:
    """원문 1건 -> 지적/면책 레코드 리스트. (TODO: LLM 호출로 구현)

    권장: PROMPT + text 를 LLM에 주고 스키마 JSON 배열을 받는다.
    반환 전 schema/finding.schema.json 로 검증한다.
    """
    raise NotImplementedError("LLM 태깅 미구현 — prompts/tagging_prompt.md 사용")


def merge_incremental(new_records: list[dict]) -> None:
    """id 기준 증분 병합(신규만 추가). 지속 저장소가 있으면 그쪽에 커밋."""
    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    seen = {r["id"] for r in existing}
    added = [r for r in new_records if r["id"] not in seen]
    OUT.write_text(json.dumps(existing + added, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"추가 {len(added)}건 / 전체 {len(existing) + len(added)}건")


if __name__ == "__main__":
    print("structure.py — collect.py 산출물을 태깅해 data/findings.json 을 만듭니다.")
