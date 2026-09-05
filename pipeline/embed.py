"""임베딩 (embed) — 각 레코드의 검색용 텍스트를 임베딩해 data/embeddings.json 생성.

임베딩 입력은 '요지 + 지적유형 + 근거법령'을 권장(원문 통짜 금지).
PoC(Track 1)는 브라우저 시맨틱 검색을 위해 사전 계산 벡터를 정적 파일로 배포.
내부배포(Track 2)는 범정부 공통기반/전용 임베딩으로 대체한다.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "findings.json"
OUT = ROOT / "data" / "embeddings.json"


def embed_text(record: dict) -> str:
    laws = " ".join(l.get("law", "") for l in record.get("legal_basis", []))
    return " ".join([record.get("summary", ""), record.get("finding_type", ""), laws]).strip()


def embed(vectors_fn) -> None:
    """vectors_fn(list[str]) -> list[list[float]] 를 주입해 임베딩. (TODO: 모델 연결)"""
    recs = json.loads(SRC.read_text(encoding="utf-8"))
    vecs = vectors_fn([embed_text(r) for r in recs])
    out = [{"id": r["id"], "embedding": v} for r, v in zip(recs, vecs)]
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"임베딩 {len(out)}건 저장")


if __name__ == "__main__":
    print("embed.py — 임베딩 모델을 연결한 뒤 embed(vectors_fn) 을 호출하세요.")
