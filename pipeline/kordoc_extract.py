"""문서 텍스트 추출 (kordoc 우선, 실패 시 자체 파서 폴백).

kordoc(Node 패키지)은 HWP/PDF/HWPX/XLS 표 복원까지 지원한다. Python 파이프라인에서
`npx -y kordoc <path> -o <tmp.md>` subprocess 로 브리지한다.

정책:
- 파일 40MB 초과 → 스킵(경고, 폴백 시도).
- subprocess 타임아웃 120초.
- 임시 md 파일은 항상 정리.
- kordoc 실패(비정상 종료·타임아웃·빈 결과)면 hwp_extract.extract_document 로 폴백.
- 폴백까지 실패하면 예외를 올린다(성공으로 계상 금지).

사용:
    from pipeline.kordoc_extract import extract
    md = extract("문서.pdf")
"""
from __future__ import annotations
import shutil
import subprocess
import tempfile
from pathlib import Path

MAX_BYTES = 40 * 1024 * 1024   # 40MB
TIMEOUT_SEC = 120


def _npx() -> str:
    """플랫폼별 npx 실행경로(Windows 는 npx.cmd)."""
    return shutil.which("npx") or shutil.which("npx.cmd") or "npx"


def _kordoc(path: Path) -> str:
    """npx kordoc 로 마크다운 추출. 실패 시 예외."""
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tf:
        out_md = Path(tf.name)
    try:
        proc = subprocess.run(
            [_npx(), "-y", "kordoc", str(path), "-o", str(out_md)],
            capture_output=True, text=True, timeout=TIMEOUT_SEC,
            shell=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"kordoc 종료코드 {proc.returncode}: {proc.stderr[-300:]}")
        text = out_md.read_text(encoding="utf-8", errors="ignore") if out_md.exists() else ""
        if not text or len(text.strip()) < 20:
            raise RuntimeError("kordoc 빈 결과")
        return text
    finally:
        try:
            out_md.unlink(missing_ok=True)
        except OSError:
            pass


def _fallback(path: Path) -> str:
    """자체 파서(hwp_extract)로 폴백."""
    from pipeline.hwp_extract import extract_document
    fmt, text = extract_document(path.read_bytes())
    if not text or len(text.strip()) < 20:
        raise RuntimeError(f"폴백 추출 실패(fmt={fmt}, 빈 텍스트)")
    return text


def extract(path: str | Path) -> str:
    """경로를 받아 마크다운/텍스트 반환. kordoc→hwp_extract 폴백."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    size = p.stat().st_size
    if size > MAX_BYTES:
        # 대용량은 kordoc 스킵(경고) 후 폴백만 시도
        print(f"  [경고] {p.name} {size/1e6:.1f}MB > 40MB — kordoc 스킵, 폴백 시도")
        return _fallback(p)
    try:
        return _kordoc(p)
    except Exception as e:  # noqa: BLE001 — kordoc 실패는 폴백으로 흡수
        print(f"  [경고] kordoc 실패({type(e).__name__}: {e}) — 폴백 시도")
        return _fallback(p)


if __name__ == "__main__":
    import sys
    md = extract(sys.argv[1])
    print(f"[{len(md)}자]\n{md[:2000]}")
