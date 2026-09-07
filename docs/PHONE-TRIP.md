# 출장·폰 작업 가이드 (2026-09-07)

저장소: https://github.com/jinhee252525/audit-helper (`main`)

## 기준 문서
- `docs/STATUS-AND-TODO.md` §E (출장 플랜)
- `docs/MASTER-PLAN.md` · `docs/HANDOFF-accuracy.md`
- 프로토: `prototypes/situation-memo/`

## 폰에서 해도 되는 것
히어로를 `app/`에 합치기 · sage 디자인 · F8/F10 UI · Pages · 도메인팩 · 문서.
데이터는 `app/data/demo.json` / `data/golden/`.

## 폰에서 안 되는 것(지금은)
19만 건 실검색(인덱스·findings gitignore). Cloud Agents는 Pro 필요.

## 복귀 후 한 줄
`python pipeline/build_index.py --input data/findings.all.json --out app/data/index`
