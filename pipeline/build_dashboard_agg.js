/* build_dashboard_agg.js — 대시보드용 소량 집계본 생성 (의존성 없음, Node)
 *
 * dashboard.html 이 Pages(app/ 만 배포)에서도 깨지지 않도록,
 * data/findings.json(소스본) 전체를 훑어 KPI·차트에 필요한 "집계본"만 뽑아
 * app/data/dashboard-agg.json 으로 저장한다. 라벨(코드북)도 내장한다.
 *
 * 실행: node pipeline/build_dashboard_agg.js
 *   옵션: --input data/findings.json  --out app/data/dashboard-agg.json
 *
 * 로컬(노트북)에서는 dashboard.html 이 여전히 전체 findings.json 을 직접 로드해
 * 상호작용 필터를 제공하고, findings 가 없는 환경(Pages)에서는 이 집계본으로 폴백한다.
 */
"use strict";
const fs = require("fs");
const path = require("path");

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : def;
}
const ROOT = path.resolve(__dirname, "..");
const INPUT = path.resolve(ROOT, arg("--input", "data/findings.json"));
const CODEBOOK = path.resolve(ROOT, arg("--codebook", "data/codebook.json"));
const OUT = path.resolve(ROOT, arg("--out", "app/data/dashboard-agg.json"));

const findings = JSON.parse(fs.readFileSync(INPUT, "utf8"));
const cb = JSON.parse(fs.readFileSync(CODEBOOK, "utf8"));

const workLabels = {};
for (const [k, v] of Object.entries(cb.work_type_관련기능 || {})) workLabels[k] = v.name;
const sectorLabels = cb.sector_발생분야 || {};
const orgOrder = cb.org_type || ["중앙", "광역", "기초", "교육", "공공기관", "기타"];

const dispLabel = (d) => (d && String(d).trim() ? String(d) : "미부과·해당없음");
const workLabel = (c) => (c && workLabels[c] ? c + " " + workLabels[c] : "미상");
const sectorLabel = (c) => (c && sectorLabels[c] ? c + " " + sectorLabels[c] : "미상");

function tally(fn) {
  const m = new Map();
  for (const r of findings) {
    const k = fn(r);
    if (k === undefined || k === null || k === "") continue;
    m.set(k, (m.get(k) || 0) + 1);
  }
  return m;
}
const pairs = (m) => [...m.entries()];
const sortDesc = (a) => a.slice().sort((x, y) => y[1] - x[1]);
const topN = (m, n) => sortDesc(pairs(m)).slice(0, n);

// record_type
const rt = tally((r) => r.record_type);
// source
const src = tally((r) => r.source);
// disposition (라벨화)
const disp = tally((r) => dispLabel(r.disposition));
// work_type (코드 그대로, 라벨은 프론트에서 붙임)
const work = tally((r) => r.work_type);
// org_type
const org = tally((r) => r.org_type);
// sector (라벨화)
const sector = tally((r) => sectorLabel(r.sector));
// year
const year = tally((r) => r.year);
// law
const lawMap = new Map();
let lawN = 0;
for (const r of findings)
  for (const l of r.legal_basis || []) {
    if (l && l.law) {
      lawMap.set(l.law, (lawMap.get(l.law) || 0) + 1);
      lawN++;
    }
  }

// work_type × org_type (top10 work, stacked by org) — parts 는 org별 건수
const workTop10 = topN(work, 10).map(([c]) => c);
const cats = orgOrder.filter((o) => findings.some((r) => r.org_type === o));
const workOrg = workTop10.map((c) => {
  const parts = {};
  let total = 0;
  for (const o of cats) {
    const n = findings.filter((r) => r.work_type === c && r.org_type === o).length;
    if (n) parts[o] = n;
    total += n;
  }
  // total 은 org 매칭분 합이 아니라 work 전체 건수로
  total = (work.get(c) || 0);
  return { code: c, label: workLabel(c), parts, total };
});

// 샘플 카드(다양성 우선): 소스·record_type 별로 골고루, source_excerpt 있는 것 우선
function sampleRecords(limit) {
  const withText = findings.filter((r) => (r.source_excerpt || "").trim());
  const bySrc = new Map();
  for (const r of withText) {
    const k = r.source || "기타";
    if (!bySrc.has(k)) bySrc.set(k, []);
    bySrc.get(k).push(r);
  }
  const picked = [];
  let round = 0;
  const keys = [...bySrc.keys()];
  while (picked.length < limit && round < 200) {
    let added = false;
    for (const k of keys) {
      const arr = bySrc.get(k);
      if (arr[round]) {
        picked.push(arr[round]);
        added = true;
        if (picked.length >= limit) break;
      }
    }
    if (!added) break;
    round++;
  }
  return picked.slice(0, limit).map((r) => ({
    id: r.id,
    record_type: r.record_type,
    work_type: r.work_type,
    disposition: r.disposition || null,
    source_excerpt: (r.source_excerpt || "").slice(0, 600),
    legal_basis: (r.legal_basis || []).filter((l) => l && l.law).slice(0, 3).map((l) => ({ law: l.law })),
    org_name: r.org_name || null,
    audit_org: r.audit_org || null,
    source: r.source,
    year: r.year || null,
    source_url: r.source_url || null,
  }));
}

const agg = {
  version: 1,
  generated_at: new Date().toISOString().slice(0, 10),
  source_file: path.basename(INPUT),
  total: findings.length,
  labels: { work: workLabels, sector: sectorLabels, org_order: orgOrder },
  record_type: { finding: rt.get("finding") || 0, consult: rt.get("consult") || 0, immunity: rt.get("immunity") || 0 },
  source: sortDesc(pairs(src)),
  disposition: sortDesc(pairs(disp)),
  work_type: sortDesc(pairs(work)),
  org_type: sortDesc(pairs(org)),
  sector: sortDesc(pairs(sector)),
  year: pairs(year).sort((a, b) => a[0] - b[0]),
  law_top: topN(lawMap, 20),
  law_total: lawN,
  work_org: workOrg,
  sample_records: sampleRecords(24),
};

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(agg, null, 2), "utf8");
const bytes = fs.statSync(OUT).size;
console.log(
  `wrote ${OUT} (${(bytes / 1024).toFixed(1)} KB) — total=${agg.total}, samples=${agg.sample_records.length}, laws=${agg.law_top.length}`
);
