"""입수함(data/inbox) 자동 처리기 — 어디서 받은 자료든 넣으면 처리.

흐름: inbox 스캔 → (문서=추출, 표데이터=매핑) → 태깅 → 검증 → findings.json 병합 → 처리완료 이관.
멱등: 내용 해시로 이미 처리한 파일은 건너뜀(배치 재실행 안전).

사용:
  PYTHONUTF8=1 python pipeline/ingest.py
  PYTHONUTF8=1 python pipeline/ingest.py --dry-run   # 처리 안 하고 목록만
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox"
RAW = ROOT / "data" / "raw_docs"
STATE = ROOT / "data" / "state.json"
RUNS = ROOT / "data" / "runs"

DOC_EXT = {".hwp", ".hwpx", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".hml", ".hwpml", ".docx"}
TABLE_EXT = {".csv", ".xlsx", ".xls", ".json"}
SKIP = {"README.md", ".gitkeep"}


def load_state() -> dict:
    if STATE.exists():
        s = json.loads(STATE.read_text(encoding="utf-8"))
    else:
        s = {}
    s.setdefault("last_run", None)
    s.setdefault("seen_ids", [])
    s.setdefault("seen_hashes", [])
    return s


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def extract_text(p: Path) -> tuple[str, str]:
    """문서→(fmt, text). kordoc 우선(pipeline.kordoc_extract), 없으면 자체 hwp_extract."""
    data = p.read_bytes()
    try:
        from pipeline.kordoc_extract import extract as kordoc_extract  # noqa
        return "kordoc", kordoc_extract(str(p))
    except Exception:
        from pipeline.hwp_extract import extract_document
        return extract_document(data)


def iter_inbox():
    if not INBOX.exists():
        return
    for p in sorted(INBOX.rglob("*")):
        if p.is_file() and p.name not in SKIP:
            yield p


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    state = load_state()
    seen_hashes = set(state["seen_hashes"])
    files = list(iter_inbox())
    print(f"입수함 파일: {len(files)}건")

    processed, skipped, staged, failed = 0, 0, 0, 0
    notes = []
    for p in files:
        source = p.relative_to(INBOX).parts[0]
        h = file_hash(p)
        if h in seen_hashes:
            skipped += 1
            continue
        if args.dry_run:
            print(f"  [dry] {source}/{p.name} ({p.suffix})")
            continue
        try:
            ext = p.suffix.lower()
            if ext in DOC_EXT:
                fmt, text = extract_text(p)
                if not text or len(text) < 20:
                    raise ValueError("본문 추출 실패(빈 텍스트)")
                # 추출 텍스트를 raw_docs/<source>/ 에 보관(태깅 입력)
                outdir = RAW / source
                outdir.mkdir(parents=True, exist_ok=True)
                (outdir / f"{p.stem}.{h}.txt").write_text(text, encoding="utf-8")
                # TODO: pipeline.tag 로 태깅→검증→merge (tag.py 구현 후 연결)
                staged += 1
                notes.append(f"- staged {source}/{p.name} [{fmt}] {len(text)}자")
            elif ext in TABLE_EXT:
                # TODO: 표데이터 컬럼 매퍼(data.go.kr CSV/XLSX/JSON → 스키마)
                staged += 1
                notes.append(f"- staged(table) {source}/{p.name} — 매퍼 연결 대기")
            else:
                notes.append(f"- skip(unknown ext) {source}/{p.name}")
                skipped += 1
                continue
            seen_hashes.add(h)
            # 처리완료 이관
            arch = RAW / source / "_processed"
            arch.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(arch / p.name))
            processed += 1
        except Exception as e:  # 실패는 실패로 기록(성공 계상 금지)
            failed += 1
            notes.append(f"- FAIL {source}/{p.name}: {type(e).__name__} {e}")

    if not args.dry_run:
        state["seen_hashes"] = sorted(seen_hashes)
        state["last_run"] = date.today().isoformat()
        save_state(state)
        RUNS.mkdir(parents=True, exist_ok=True)
        (RUNS / f"{date.today().isoformat()}.md").write_text(
            f"# {date.today().isoformat()} ingest\n\n처리 {processed} · 스테이징 {staged} · 건너뜀 {skipped} · 실패 {failed}\n\n"
            + "\n".join(notes) + "\n", encoding="utf-8")
    print(f"처리 {processed} · 스테이징 {staged} · 건너뜀 {skipped} · 실패 {failed}")
    print("※ 태깅(tag.py)·표매퍼는 다음 단계에서 연결 → 완전 자동화 완성")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
