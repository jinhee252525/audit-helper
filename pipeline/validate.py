"""품질 게이트 G1(스키마) + G2(절대규칙) — 결정론 검사.

레코드가 파이프라인에 진입하기 전 반드시 통과해야 하는 관문.
- G1 스키마: schema/finding.schema.json 적합 + id 중복 없음.
- G2 절대규칙(CLAUDE.md): 출처링크·처분표기·무근거·현행성·위법단정 관련 최소 검사.

사용:
    python pipeline/validate.py                     # data/findings.json 검사(없으면 sample)
    python pipeline/validate.py data/findings.sample.json
    python pipeline/validate.py --strict            # 경고도 실패로 취급

종료코드: 0=통과, 1=오류(하드), 2=파일/스키마 로드 실패.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

# Windows 콘솔에서도 한글 출력이 깨지지 않도록 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)
SCHEMA_PATH = ROOT / "schema" / "finding.schema.json"

# 위법·부당을 '단정'하는 종결형(명사 카테고리는 허용, 단정 서술만 잡음)
ASSERTIVE_PATTERNS = [
    r"위법하다", r"위법이다", r"불법이다", r"부당하다", r"위반이다",
    r"위법하였다", r"부당하였다", r"위반하였다",
]
NONCURRENT_BASIS = {"현행", "개정", "폐지"}  # F4(법제처) 확인 전에는 확인필요 여야 함


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def g1_schema(records: list[dict]) -> tuple[list[str], list[str]]:
    """스키마 적합 + id 중복. return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        from jsonschema import Draft7Validator
    except ImportError:
        errors.append("jsonschema 미설치 — `pip install jsonschema` 후 재실행")
        return errors, warnings

    schema = load_json(SCHEMA_PATH)
    validator = Draft7Validator(schema)
    seen_ids: dict[str, int] = {}

    for i, rec in enumerate(records):
        for err in validator.iter_errors(rec):
            loc = "/".join(str(p) for p in err.path) or "(root)"
            errors.append(f"[{i}] 스키마 위반 @{loc}: {err.message}")
        rid = rec.get("id")
        if rid is not None:
            if rid in seen_ids:
                errors.append(f"[{i}] id 중복: '{rid}' (앞서 [{seen_ids[rid]}]에서 사용)")
            else:
                seen_ids[rid] = i
    return errors, warnings


def g2_rules(records: list[dict]) -> tuple[list[str], list[str]]:
    """절대규칙 검사. return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    assertive_re = re.compile("|".join(ASSERTIVE_PATTERNS))

    for i, rec in enumerate(records):
        rid = rec.get("id", f"index{i}")
        rtype = rec.get("record_type")

        # 규칙2: 출처 링크 필수 + 비어있지 않음
        url = rec.get("source_url", "")
        if not url or not str(url).strip():
            errors.append(f"[{rid}] 출처 링크(source_url) 누락 — 절대규칙2 위반")

        # 규칙3: 근거법령 배열 형태 확인(무근거 서술 방지 보조). 비면 경고.
        lb = rec.get("legal_basis")
        if lb is not None and not isinstance(lb, list):
            errors.append(f"[{rid}] legal_basis 형식 오류(배열 아님)")
        if not lb:
            warnings.append(f"[{rid}] 근거법령 미기재 — 무근거 여부 검수 필요(절대규칙3)")

        # 규칙4: 현행성 임의 처리 금지 — F4 확인 전 basis_status는 확인필요 여야
        bs = rec.get("basis_status", "확인필요")
        if bs in NONCURRENT_BASIS:
            warnings.append(
                f"[{rid}] basis_status='{bs}' — F4(법제처) 확인 증거 없이 현행성 단정 금지(절대규칙4). "
                f"확인 전이면 '확인필요' 유지"
            )

        # 규칙1: 위법·부당 단정 종결형 탐지(요지·지적유형)
        text = " ".join([str(rec.get("summary", "")), str(rec.get("finding_type", ""))])
        for m in assertive_re.finditer(text):
            warnings.append(f"[{rid}] 단정 표현 의심 '{m.group()}' — 사실 서술로 순화 권장(절대규칙1)")

        # record_type 일관성
        if rtype == "immunity":
            imm = rec.get("immunity")
            if not isinstance(imm, dict) or imm.get("outcome") not in ("인정", "불인정"):
                errors.append(f"[{rid}] immunity 레코드인데 immunity.outcome(인정|불인정) 없음")
        elif rtype == "consult":
            if rec.get("immunity") not in (None, {}):
                warnings.append(f"[{rid}] consult 레코드에 immunity 값이 있음 — 확인 필요")

        # disposition: enum은 G1이 검사. 여기선 finding 외 타입의 disposition 잔존만 경고.
        if rtype in ("immunity", "consult") and rec.get("disposition") not in (None, ""):
            warnings.append(f"[{rid}] {rtype} 레코드에 disposition 값이 있음 — 보통 null(해당없음)")

    return errors, warnings


def summarize(records: list[dict]) -> str:
    n = len(records)
    synth = sum(1 for r in records if r.get("_synthetic"))
    review = sum(1 for r in records if r.get("review"))
    by_type: dict[str, int] = {}
    for r in records:
        by_type[r.get("record_type", "?")] = by_type.get(r.get("record_type", "?"), 0) + 1
    types = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items()))
    return f"총 {n}건 ({types}) · 합성 {synth} · 검수대기 {review}"


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    args = [a for a in argv if not a.startswith("--")]
    if args:
        target = Path(args[0]).resolve()
    else:
        default = ROOT / "data" / "findings.json"
        target = default if default.exists() else ROOT / "data" / "findings.sample.json"

    if not target.exists():
        print(f"[G] 대상 파일 없음: {target}")
        return 2
    if not SCHEMA_PATH.exists():
        print(f"[G] 스키마 없음: {SCHEMA_PATH}")
        return 2

    try:
        records = load_json(target)
    except json.JSONDecodeError as e:
        print(f"[G] JSON 파싱 실패: {e}")
        return 2
    if not isinstance(records, list):
        print("[G] 최상위가 배열이 아님")
        return 2

    print(f"검사 대상: {rel(target)}")
    print(f"요약: {summarize(records)}\n")

    e1, w1 = g1_schema(records)
    e2, w2 = g2_rules(records)
    errors = e1 + e2
    warnings = w1 + w2

    if warnings:
        print(f"⚠ 경고 {len(warnings)}건:")
        for w in warnings:
            print(f"  - {w}")
        print()
    if errors:
        print(f"✖ 오류 {len(errors)}건 (게이트 반려):")
        for e in errors:
            print(f"  - {e}")
        print("\n결과: 반려 (G1/G2 미통과)")
        return 1

    if strict and warnings:
        print("결과: --strict 모드 — 경고를 실패로 취급. 반려")
        return 1

    print("결과: 통과 ✔ (G1 스키마 + G2 절대규칙)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
