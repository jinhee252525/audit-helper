/* 감사 선례 도우미 — shard 인덱스 + 신뢰/품질 배지
 * 인덱스 재빌드: python pipeline/build_index.py --input data/findings.all.json --out app/data/index
 * Prefer ./data/index/manifest.json; fallback findings.sample / demo.
 */
const INDEX_MANIFEST = "./data/index/manifest.json";
const FALLBACK_DATA = ["../data/findings.sample.json", "./data/demo.json", "../data/findings.json"];
const RESULT_CAP = 80;
const BOOTSTRAP_BYTE_BUDGET = 8 * 1024 * 1024; // ~8MB when no year/org filter
const DEBOUNCE_MS = 280;
const MIN_CONF = 0.6;
const RTYPE = { finding: "지적", immunity: "면책", consult: "사전컨설팅" };
const QLABEL = { list_only: "목록만", body: "본문 확보", matched: "근거 대조 완료" };

const $ = (s) => document.querySelector(s);

let MODE = "none"; // "index" | "flat"
let MANIFEST = null;
let SHARD_CACHE = new Map(); // id -> docs[]
let SHARD_LOADING = new Set();
let FLAT_RECORDS = [];
let debounceTimer = null;
let renderSeq = 0;

function isHighTrust(r) {
  const conf = r.tag_confidence;
  if (r.review) return false;
  if (conf == null || conf === "") return false;
  return Number(conf) >= MIN_CONF;
}

function setStatus(msg) {
  const el = $("#load-status");
  if (el) el.textContent = msg || "";
}

function parseQueryState() {
  const p = new URLSearchParams(location.search);
  return {
    q: p.get("q") || "",
    work: p.get("work") || "",
    org: p.get("org") || "",
    year: p.get("year") || "",
    type: p.get("type") || "",
    edu: p.get("edu") === "1",
  };
}

function writeQueryState(f) {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  if (f.work) p.set("work", f.work);
  if (f.org) p.set("org", f.org);
  if (f.year) p.set("year", f.year);
  if (f.type) p.set("type", f.type);
  if (f.edu) p.set("edu", "1");
  const qs = p.toString();
  const url = qs ? `${location.pathname}?${qs}` : location.pathname;
  history.replaceState(null, "", url);
}

function readFilters() {
  return {
    q: ($("#q").value || "").trim(),
    work: $("#f-work").value,
    org: $("#f-org").value,
    year: $("#f-year").value,
    type: $("#f-type").value,
    edu: $("#f-edu").checked,
  };
}

function applyFiltersToForm(st) {
  $("#q").value = st.q || "";
  if (st.work) $("#f-work").value = st.work;
  if (st.org) $("#f-org").value = st.org;
  if (st.year) $("#f-year").value = st.year;
  if (st.type) $("#f-type").value = st.type;
  $("#f-edu").checked = !!st.edu;
}

function uniq(arr) {
  return [...new Set(arr.filter((v) => v !== null && v !== undefined && v !== ""))];
}

function opts(el, vals, keepFirst) {
  const first = keepFirst ? el.querySelector("option") : null;
  el.innerHTML = "";
  if (first) el.appendChild(first);
  else {
    const o = document.createElement("option");
    o.value = "";
    o.textContent = el.id === "f-work" ? "업무유형 전체" : el.id === "f-org" ? "기관유형 전체" : "연도 전체";
    el.appendChild(o);
  }
  vals.forEach((v) => {
    const o = document.createElement("option");
    o.value = String(v);
    o.textContent = String(v);
    el.appendChild(o);
  });
}

function fillFiltersFromManifest() {
  const keys = (MANIFEST.shards || []).map((s) => s.key);
  const years = uniq(keys.map((k) => String(k).split("__")[0])).sort((a, b) => Number(b) - Number(a));
  const orgs = uniq(keys.map((k) => String(k).split("__")[1]));
  opts($("#f-year"), years, true);
  opts($("#f-org"), orgs, true);
  // work_type: common codebook range; refined as shards load
  const works = [];
  for (let i = 1; i <= 25; i++) works.push(String(i).padStart(2, "0"));
  opts($("#f-work"), works, true);
}

function fillFiltersFromFlat(recs) {
  opts($("#f-work"), uniq(recs.map((r) => r.work_type)).sort(), true);
  opts($("#f-org"), uniq(recs.map((r) => r.org_type)), true);
  opts($("#f-year"), uniq(recs.map((r) => r.year)).sort((a, b) => b - a), true);
}

function selectShards(f) {
  const shards = MANIFEST.shards || [];
  const matchKey = (s) => {
    const [y, ot] = String(s.key).split("__");
    if (f.year && String(y) !== String(f.year)) return false;
    if (f.org && String(ot) !== String(f.org)) return false;
    return true;
  };

  if (f.year || f.org) {
    return shards.filter(matchKey).sort((a, b) => a.bytes - b.bytes);
  }

  // No year/org: recent years first, smaller shards first, soft byte budget
  const scored = shards
    .map((s) => {
      const y = Number(String(s.key).split("__")[0]) || 0;
      return { s, y };
    })
    .sort((a, b) => b.y - a.y || a.s.bytes - b.s.bytes);

  const picked = [];
  let budget = 0;
  for (const { s } of scored) {
    if (picked.length >= 6 && budget >= BOOTSTRAP_BYTE_BUDGET) break;
    picked.push(s);
    budget += s.bytes || 0;
    if (picked.length >= 10) break;
  }
  return picked;
}

async function fetchShard(meta) {
  if (SHARD_CACHE.has(meta.id)) return SHARD_CACHE.get(meta.id);
  if (SHARD_LOADING.has(meta.id)) {
    while (SHARD_LOADING.has(meta.id)) await new Promise((r) => setTimeout(r, 40));
    return SHARD_CACHE.get(meta.id) || [];
  }
  SHARD_LOADING.add(meta.id);
  try {
    const r = await fetch(`./data/index/${meta.file}`);
    if (!r.ok) throw new Error(`shard ${meta.id} HTTP ${r.status}`);
    const data = await r.json();
    const docs = Array.isArray(data.docs) ? data.docs : [];
    SHARD_CACHE.set(meta.id, docs);
    return docs;
  } finally {
    SHARD_LOADING.delete(meta.id);
  }
}

async function ensureShardsLoaded(metas, seq) {
  const pending = metas.filter((m) => !SHARD_CACHE.has(m.id));
  if (pending.length) {
    setStatus(`샤드 로딩 중… (${pending.length}개)`);
  }
  // serial-ish for large shards: 2 at a time
  const conc = 2;
  for (let i = 0; i < pending.length; i += conc) {
    if (seq !== renderSeq) return;
    await Promise.all(pending.slice(i, i + conc).map(fetchShard));
  }
  if (seq === renderSeq) {
    const loadedN = [...SHARD_CACHE.values()].reduce((a, d) => a + d.length, 0);
    setStatus(`인덱스 ${MANIFEST.n_shards}샤드 · 캐시 ${SHARD_CACHE.size}개 · 문서 ${loadedN.toLocaleString("ko-KR")}건`);
  }
}

function allCachedDocs() {
  const out = [];
  for (const docs of SHARD_CACHE.values()) out.push(...docs);
  return out;
}

function normalizeFlat(r) {
  // map legacy findings sample → index-like doc
  if (r.search_text || r.excerpt || r.title) return r;
  const title = r.source_title || r.summary || r.finding_type || "";
  const excerpt = (r.source_excerpt || r.summary || "").slice(0, 400);
  return {
    ...r,
    title: String(title).slice(0, 200),
    excerpt,
    search_text: `${title} ${excerpt}`.slice(0, 800),
    text_quality: r.text_quality || (excerpt ? "body" : "list_only"),
    review: !!r.review,
    tag_confidence: r.tag_confidence ?? null,
    hide_by_default: !!r.hide_by_default || !!r.edu_school,
    edu_school: !!r.edu_school,
    source_url: r.source_url || "#",
  };
}

function keywordMatch(r, q) {
  if (!q) return true;
  const hay = [r.search_text, r.title, r.excerpt, r.org_name, r.work_type]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return q.toLowerCase().split(/\s+/).filter(Boolean).every((t) => hay.includes(t));
}

function matches(r, f) {
  if (!f.edu && (r.hide_by_default || r.edu_school)) return false;
  if (f.work && String(r.work_type) !== f.work) return false;
  if (f.org && String(r.org_type) !== f.org) return false;
  if (f.year && String(r.year) !== f.year) return false;
  if (f.type && r.record_type !== f.type) return false;
  if (!keywordMatch(r, f.q)) return false;
  return true;
}

function sortDocs(arr) {
  return arr.sort((a, b) => {
    const ta = isHighTrust(a) ? 1 : 0;
    const tb = isHighTrust(b) ? 1 : 0;
    if (tb !== ta) return tb - ta;
    const ya = Number(a.year) || 0;
    const yb = Number(b.year) || 0;
    if (yb !== ya) return yb - ya;
    return String(b.id || "").localeCompare(String(a.id || ""));
  });
}

function dispositionHtml(r) {
  if (r.record_type === "immunity") {
    const o = (r.immunity && r.immunity.outcome) || r.disposition || "";
    const ok = o === "인정";
    return `<span class="badge ${ok ? "b-ok" : "b-no"}">면책 ${o || "-"}</span>`;
  }
  if (r.record_type === "consult") return '<span class="badge b-consult">사전컨설팅</span>';
  if (!r.disposition) return '<span class="badge b-none">처분 미부과·해당없음</span>';
  return `<span class="badge b-disp">${r.disposition}</span>`;
}

function qualityBadge(r) {
  const q = r.text_quality || "list_only";
  const label = QLABEL[q] || q;
  const cls = q === "matched" ? "b-q-matched" : q === "body" ? "b-q-body" : "b-q-list";
  const tip = q === "list_only" ? " title=\"목록만 — 검토메모 근거로 쓰기 전 본문 확인 필요\"" : "";
  return `<span class="badge ${cls}"${tip}>${label}</span>`;
}

function trustBadge(r) {
  if (isHighTrust(r)) return '<span class="badge b-trust">고신뢰</span>';
  return '<span class="badge b-review">검토중</span>';
}

function card(r) {
  const rt = RTYPE[r.record_type] || r.record_type || "지적";
  const title = r.title || r.summary || "(제목 없음)";
  const excerpt = r.excerpt || "";
  const src = r.source_url || r.document_url || "#";
  const listOnly = (r.text_quality || "") === "list_only";
  return `<article class="rec rt-${r.record_type || "finding"}${listOnly ? " rec-list-only" : ""}">
    <div class="rec-top">
      <span class="rtype">${rt}</span>
      ${dispositionHtml(r)}
      ${qualityBadge(r)}
      ${trustBadge(r)}
    </div>
    <p class="summary">${escapeHtml(title)}</p>
    ${excerpt ? `<p class="excerpt">${escapeHtml(excerpt)}</p>` : ""}
    <div class="rec-foot">
      <span class="chips">${[r.work_type, r.org_type, r.year, r.org_name].filter(Boolean).join(" · ")}</span>
      <a class="src" href="${src}" target="_blank" rel="noopener">출처 ↗</a>
    </div>
  </article>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function render() {
  const seq = ++renderSeq;
  const f = readFilters();
  writeQueryState(f);

  let pool = [];
  if (MODE === "index") {
    const metas = selectShards(f);
    await ensureShardsLoaded(metas, seq);
    if (seq !== renderSeq) return;
    // Only search within selected shards' docs (not entire cache of unrelated filters)
    for (const m of metas) {
      const docs = SHARD_CACHE.get(m.id) || [];
      pool.push(...docs);
    }
    // If query present and few hits, optionally note limited shard coverage
    $("#loaded-meta").textContent = ` · 검색범위 샤드 ${metas.length}개`;
  } else {
    pool = FLAT_RECORDS.map(normalizeFlat);
    $("#loaded-meta").textContent = " · 샘플/폴백";
  }

  let out = pool.filter((r) => matches(r, f));
  out = sortDocs(out);
  const total = out.length;
  out = out.slice(0, RESULT_CAP);
  $("#count").textContent = total > RESULT_CAP ? `${RESULT_CAP}+` : String(total);
  if (!out.length) {
    $("#results").innerHTML = '<p class="empty">조건에 맞는 선례가 없습니다. 연도·기관유형을 지정하면 해당 샤드만 추가로 불러옵니다.</p>';
    return;
  }
  const more = total > RESULT_CAP ? `<p class="cap-note">상위 ${RESULT_CAP}건만 표시 (고신뢰·최근 연도 우선). 전체 후보 ${total.toLocaleString("ko-KR")}건.</p>` : "";
  $("#results").innerHTML = more + out.map(card).join("");
}

function scheduleRender() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => { render().catch(console.error); }, DEBOUNCE_MS);
}

function bind() {
  ["#q", "#f-work", "#f-org", "#f-year", "#f-type", "#f-edu"].forEach((s) => {
    $(s).addEventListener("input", scheduleRender);
    $(s).addEventListener("change", scheduleRender);
  });
  $("#reset").addEventListener("click", () => {
    $("#q").value = "";
    ["#f-work", "#f-org", "#f-year", "#f-type"].forEach((s) => { $(s).value = ""; });
    $("#f-edu").checked = false;
    scheduleRender();
  });
}

async function loadIndex() {
  try {
    const r = await fetch(INDEX_MANIFEST);
    if (!r.ok) return false;
    MANIFEST = await r.json();
    if (!MANIFEST || !Array.isArray(MANIFEST.shards) || !MANIFEST.shards.length) return false;
    MODE = "index";
    if (MANIFEST.default_filters && MANIFEST.default_filters.min_confidence_expose_hint != null) {
      // keep module const aligned visually via status only
    }
    fillFiltersFromManifest();
    setStatus(`인덱스 준비 · ${MANIFEST.n_docs?.toLocaleString?.("ko-KR") || "?"}건 · ${MANIFEST.n_shards}샤드`);
    return true;
  } catch (e) {
    return false;
  }
}

async function loadFlatFallback() {
  for (const url of FALLBACK_DATA) {
    try {
      const r = await fetch(url);
      if (!r.ok) continue;
      const data = await r.json();
      FLAT_RECORDS = Array.isArray(data) ? data : [];
      MODE = "flat";
      fillFiltersFromFlat(FLAT_RECORDS);
      $("#synthetic-note").hidden = false;
      setStatus(`폴백 데이터 로드: ${url}`);
      return true;
    } catch (e) { /* next */ }
  }
  return false;
}

(async function init() {
  const st = parseQueryState();
  const ok = (await loadIndex()) || (await loadFlatFallback());
  if (!ok) {
    $("#results").innerHTML = '<p class="empty">데이터를 불러오지 못했습니다. 저장소에서 정적 서버로 <code>/app/</code> 에 접속하세요.<br>인덱스 재빌드: <code>python pipeline/build_index.py --input data/findings.all.json --out app/data/index</code></p>';
    return;
  }
  applyFiltersToForm(st);
  bind();
  await render();
})();
