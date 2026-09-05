/* 감사 선례 도우미 — PoC 검색·필터 (바닐라 JS)
 * 데이터: ../data/findings.json (없으면 findings.sample.json)
 * 검색은 키워드+필드 매칭. 시맨틱 검색은 pipeline/embed.py 산출물로 후속 고도화.
 */
const DATA_CANDIDATES = ["../data/findings.json", "../data/findings.sample.json"];
const RTYPE = { finding: "지적", immunity: "면책", consult: "사전컨설팅" };
let RECORDS = [];

const $ = (s) => document.querySelector(s);

async function load() {
  for (const url of DATA_CANDIDATES) {
    try {
      const r = await fetch(url);
      if (r.ok) {
        const data = await r.json();
        RECORDS = Array.isArray(data) ? data : [];
        if (url.includes("sample") || RECORDS.some((x) => x._synthetic)) {
          $("#synthetic-note").hidden = false;
        }
        return;
      }
    } catch (e) { /* try next */ }
  }
  $("#results").innerHTML = '<p class="empty">데이터를 불러오지 못했습니다. 저장소 루트에서 <code>python3 -m http.server</code> 실행 후 <code>/app/</code> 로 접속하세요.</p>';
}

function uniq(arr) { return [...new Set(arr.filter(Boolean))]; }

function fillFilters() {
  const laws = uniq(RECORDS.flatMap((r) => (r.legal_basis || []).map((l) => l.law)));
  const opts = (el, vals) => vals.forEach((v) => { const o = document.createElement("option"); o.value = v; o.textContent = v; el.appendChild(o); });
  opts($("#f-work"), uniq(RECORDS.map((r) => r.work_type)).sort());
  opts($("#f-org"), uniq(RECORDS.map((r) => r.org_type)));
  opts($("#f-year"), uniq(RECORDS.map((r) => r.year)).sort((a, b) => b - a));
  opts($("#f-law"), laws.sort());
}

function matches(r, q, f) {
  if (f.work && r.work_type !== f.work) return false;
  if (f.org && r.org_type !== f.org) return false;
  if (f.year && String(r.year) !== f.year) return false;
  if (f.type && r.record_type !== f.type) return false;
  if (f.law && !(r.legal_basis || []).some((l) => l.law === f.law)) return false;
  if (q) {
    const hay = [r.summary, r.finding_type, r.work_type, ...(r.legal_basis || []).map((l) => l.law + " " + (l.article || ""))].join(" ").toLowerCase();
    if (!q.toLowerCase().split(/\s+/).every((t) => hay.includes(t))) return false;
  }
  return true;
}

function dispositionHtml(r) {
  if (r.record_type === "immunity") {
    const o = r.immunity && r.immunity.outcome;
    return `<span class="badge ${o === "인정" ? "b-ok" : "b-no"}">면책 ${o || "-"}</span>`;
  }
  if (r.record_type === "consult") return '<span class="badge b-consult">사전컨설팅</span>';
  if (!r.disposition) return '<span class="badge b-none">처분 미부과·해당없음</span>';
  return `<span class="badge b-disp">${r.disposition}${r.binding_level ? " · 구속력 " + r.binding_level : ""}</span>`;
}

function lawViewLink(l) {
  // "관련 법령 보기": 검색이 아니라 법제처 본문을 바로 연다(딥링크).
  //   법령 → /법령/{명}[/제N조] · 행정규칙 → /행정규칙/{명} · 자치법규 → /자치법규/{명}
  // 기관 내부규정(내규)은 법제처에 없어 열리지 않음 → 원문 문서로 연결(호출부에서 처리).
  const base = l.law_type === "자치법규" ? "자치법규"
    : l.law_type === "행정규칙" ? "행정규칙"
    : "법령";
  const name = encodeURIComponent(l.law.trim());
  const art = l.article ? "/" + encodeURIComponent(String(l.article).replace(/\s+/g, "")) : "";
  return `https://www.law.go.kr/${base}/${name}${art}`;
}

function card(r) {
  const rt = RTYPE[r.record_type] || r.record_type;
  const basis = (r.legal_basis || []).map((l) =>
    `<a class="law" href="${lawViewLink(l)}" target="_blank" rel="noopener">${l.law}${l.article ? " " + l.article : ""}</a>`
  ).join(" · ") || "근거 미기재";
  const reqs = r.immunity && r.immunity.requirements ? `<div class="reqs"><b>면책 요건:</b> ${r.immunity.requirements.join(" · ")}</div>` : "";
  const budget = r.budget_link ? `<div class="reqs"><b>예산·사업:</b> ${r.budget_link.program || r.budget_link.budget_ref} (신뢰도 ${Math.round((r.budget_link.confidence || 0) * 100)}%)</div>` : "";
  return `<article class="rec rt-${r.record_type}">
    <div class="rec-top">
      <span class="rtype">${rt}</span>
      <span class="ftype">${r.finding_type || ""}</span>
      ${dispositionHtml(r)}
    </div>
    <p class="summary">${r.summary}</p>
    ${reqs}${budget}
    <div class="rec-foot">
      <span class="chips">${r.work_type} · ${r.org_type} · ${r.year}</span>
      <span class="basis">근거: ${basis} <span class="status">[${r.basis_status || "확인필요"}]</span></span>
      <a class="src" href="${r.source_url}" target="_blank" rel="noopener">출처: ${r.source} ↗</a>
    </div>
  </article>`;
}

function render() {
  const q = $("#q").value.trim();
  const f = { work: $("#f-work").value, org: $("#f-org").value, year: $("#f-year").value, law: $("#f-law").value, type: $("#f-type").value };
  const out = RECORDS.filter((r) => matches(r, q, f))
    .sort((a, b) => (b.added_at || "").localeCompare(a.added_at || ""));
  $("#count").textContent = out.length;
  $("#results").innerHTML = out.length ? out.map(card).join("") : '<p class="empty">조건에 맞는 선례가 없습니다.</p>';
}

function bind() {
  ["#q", "#f-work", "#f-org", "#f-year", "#f-law", "#f-type"].forEach((s) => {
    $(s).addEventListener("input", render);
  });
  $("#reset").addEventListener("click", () => {
    $("#q").value = "";
    ["#f-work", "#f-org", "#f-year", "#f-law", "#f-type"].forEach((s) => ($(s).value = ""));
    render();
  });
}

(async function init() {
  await load();
  fillFilters();
  bind();
  render();
})();
