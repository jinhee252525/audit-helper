# -*- coding: utf-8 -*-
"""소스 간 중복 제거 + 통합 병합.

중복 발생 지점(사용자 확인):
  - 감사원 ↔ ALIO  (감사원이 공공기관 지적한 게 ALIO에도 공시)
  - ALIO ↔ 자체감사(pap)  (감독기관이 공공기관 감사한 게 ALIO에도 공시)
제외: 국회결산(거의 없음), 감사원 ↔ 자체감사(성격 다름)

매칭: 피감기관(정규화)+연도로 블록 → 블록 내 지적내용 유사도(char 2-gram Jaccard)≥THRESH.
보존 우선순위: 감사원 > 자체감사(pap, 지적별 구조화 원천) > ALIO(재공시) > 국회결산.
자동삭제하지 않고 removed 로그를 남긴다(검수 가능).

입력: data/findings.json + data/findings.pap.json
출력: data/findings.all.json (통합·중복제거) + data/dedup_removed.json (제거내역)
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

ROOT = Path(__file__).resolve().parents[1]
THRESH = 0.62
PRIORITY = {"감사원": 0, "자체감사": 1, "ALIO": 2, "국회결산": 3, "인사혁신처": 4, "기타": 9}
# dedup 대상 소스쌍(정렬된 튜플)
ELIGIBLE_PAIRS = {("ALIO", "감사원"), ("ALIO", "자체감사")}

_ORG_STOP = re.compile(r"(주식회사|㈜|\(주\)|재단법인|사단법인|\s)")


def norm_org(s: str | None) -> str:
    s = s or ""
    s = re.sub(r"[()（）]", "", s)
    s = _ORG_STOP.sub("", s)
    return s.lower()


def fix_bai_org(rec: dict) -> None:
    """감사원 org_name 결측(보고서 등록·미상) → source_title 앞부분에서 피감기관 추정."""
    if rec.get("source") != "감사원":
        return
    on = rec.get("org_name") or ""
    if on and on not in ("(보고서 등록)", "(미상)", "(사례집·신청기관 비공개)"):
        return
    t = rec.get("source_title") or ""
    # "○○ 정기감사", "○○의 ... 관련", "기관정기감사 ○○·○○ 정기감사"
    m = re.match(r"(?:기관정기감사\s*)?([가-힣A-Za-z0-9·\s]{2,20}?)(?:의|\s)?\s*(?:정기감사|종합감사|특정감사|감사|관련)", t)
    if m:
        cand = m.group(1).strip(" ·")
        if cand:
            rec["org_name"] = cand.split("·")[0].strip()  # 다기관이면 첫 기관


def _norm_text(s: str | None) -> str:
    s = s or ""
    s = re.sub(r"\([^)]*\)", "", s)          # (주의, 통보) 등 처분 괄호 제거
    s = re.sub(r"[○\-·•\s\r\n]", "", s)
    s = re.sub(r"[^\w가-힣]", "", s)
    return s.lower()


def bigrams(s: str) -> set:
    s = _norm_text(s)
    if len(s) < 2:
        return {s} if s else set()
    return {s[i:i+2] for i in range(len(s) - 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load() -> list[dict]:
    recs = json.loads((ROOT / "data" / "findings.json").read_text(encoding="utf-8"))
    pap = json.loads((ROOT / "data" / "findings.pap.json").read_text(encoding="utf-8"))
    return recs + pap


def main() -> int:
    recs = load()
    for r in recs:
        fix_bai_org(r)
        r["_ng"] = bigrams(r.get("source_excerpt"))
    # 블록: (norm_org, year)
    blocks: dict = {}
    for i, r in enumerate(recs):
        k = (norm_org(r.get("org_name")), r.get("year"))
        blocks.setdefault(k, []).append(i)

    removed = {}      # idx -> {kept_id, sim}
    for k, idxs in blocks.items():
        if len(idxs) < 2 or not k[0]:
            continue
        # 소스가 2종 이상 섞인 블록만 교차비교
        srcs = {recs[i].get("source") for i in idxs}
        if len(srcs) < 2:
            continue
        for a_pos in range(len(idxs)):
            i = idxs[a_pos]
            if i in removed:
                continue
            for b_pos in range(a_pos + 1, len(idxs)):
                j = idxs[b_pos]
                if j in removed:
                    continue
                sa, sb = recs[i].get("source"), recs[j].get("source")
                if sa == sb:
                    continue
                if tuple(sorted((sa, sb))) not in ELIGIBLE_PAIRS:
                    continue
                sim = jaccard(recs[i]["_ng"], recs[j]["_ng"])
                if sim < THRESH:
                    continue
                # 우선순위 낮은 쪽 제거
                pi, pj = PRIORITY.get(sa, 9), PRIORITY.get(sb, 9)
                drop = j if pj >= pi else i
                keep = i if drop == j else j
                removed[drop] = {"kept_id": recs[keep].get("id"),
                                 "kept_source": recs[keep].get("source"),
                                 "dropped_source": recs[drop].get("source"),
                                 "sim": round(sim, 3),
                                 "org": recs[drop].get("org_name"),
                                 "excerpt": (recs[drop].get("source_excerpt") or "")[:60]}
                if drop == i:
                    break
    kept = [r for i, r in enumerate(recs) if i not in removed]
    for r in kept:
        r.pop("_ng", None)
    rem_log = [{"dropped_id": recs[i].get("id"), **info} for i, info in removed.items()]
    (ROOT / "data" / "findings.all.json").write_text(
        json.dumps(kept, ensure_ascii=False), encoding="utf-8")
    (ROOT / "data" / "dedup_removed.json").write_text(
        json.dumps(rem_log, ensure_ascii=False, indent=2), encoding="utf-8")
    import collections
    by_pair = collections.Counter((r["dropped_source"] + "→" + r["kept_source"]) for r in rem_log)
    print(f"입력 {len(recs):,} · 제거 {len(removed):,} · 최종 {len(kept):,}")
    print("제거 소스쌍:", dict(by_pair))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
