/* status.js — 감사 결과 현황 (공직자 / 발굴자 dual lens)
 * Pages-safe: dashboard-agg.json 필수. 로컬이면 findings.json 으로 드릴다운 보강.
 * 판단 언어 금지 — 검토용 시사만.
 */
"use strict";

const SAGE_SCALE = ["#F0F4F1", "#D5E0D8", "#B7C9C0", "#8DA399", "#5B7C73", "#3F5D50"];

const state = {
  lens: "public",
  agg: null,
  findings: null, // full local list if available
  mode: "agg", // "full" | "agg"
  filterWork: "",
  filterDisp: "",
};

const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

function workName(code, labels) {
  if (!code) return "미상";
  const n = (labels && labels[code]) || (state.agg && state.agg.labels && state.agg.labels.work[code]);
  return n ? code + " " + n : String(code);
}

function dispOf(r) {
  const d = r && r.disposition;
  return d && String(d).trim() ? String(d) : "미부과·해당없음";
}

function fmtRate(rate) {
  if (rate == null) return "신규·전년0";
  const pct = Math.round(rate * 1000) / 10;
  return (pct > 0 ? "+" : "") + pct + "%";
}

function fmtNum(n) {
  return (n || 0).toLocaleString("ko-KR");
}

/* ---------- data load ---------- */
function loadData() {
  const statusEl = $("loadStatus");
  const tryFindings = fetch("../data/findings.json")
    .then((r) => {
      if (!r.ok) throw new Error("no findings");
      return r.json();
    })
    .catch(() => null);

  const tryAgg = fetch("./data/dashboard-agg.json").then((r) => {
    if (!r.ok) throw new Error("no agg");
    return r.json();
  });

  return Promise.all([tryAgg, tryFindings]).then(([agg, findings]) => {
    if (!agg) throw new Error("dashboard-agg.json 필요");
    state.agg = agg;
    if (findings && Array.isArray(findings) && findings.length) {
      state.findings = findings;
      state.mode = "full";
      statusEl.innerHTML =
        "로컬 전체 <code>findings.json</code> " +
        fmtNum(findings.length) +
        "건 · 집계 " +
        esc(agg.generated_at) +
        (agg.surge_meta ? " · 급증쌍 " + agg.surge_meta.prev + "→" + agg.surge_meta.cur : "");
    } else {
      state.mode = "agg";
      statusEl.innerHTML =
        "집계본 모드 <code>dashboard-agg.json</code> · " +
        esc(agg.source_file) +
        " 기준 " +
        fmtNum(agg.total) +
        "건 · " +
        esc(agg.generated_at) +
        " · 드릴다운은 샘플 " +
        (agg.sample_records || []).length +
        "건";
    }
    initFilters();
    renderAll();
  });
}

function initFilters() {
  const a = state.agg;
  const fw = $("fWork");
  const fd = $("fDisp");
  fw.innerHTML = '<option value="">업무유형 전체</option>';
  (a.work_type || []).forEach(([c, n]) => {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = workName(c) + " (" + n + ")";
    fw.appendChild(o);
  });
  fd.innerHTML = '<option value="">처분 전체</option>';
  (a.disposition || []).forEach(([d, n]) => {
    const o = document.createElement("option");
    o.value = d;
    o.textContent = d + " (" + n + ")";
    fd.appendChild(o);
  });
  fw.onchange = () => {
    state.filterWork = fw.value;
    renderPublic();
  };
  fd.onchange = () => {
    state.filterDisp = fd.value;
    renderPublic();
  };
  $("fReset").onclick = () => {
    state.filterWork = "";
    state.filterDisp = "";
    fw.value = "";
    fd.value = "";
    renderPublic();
  };
}

/* ---------- record pool for drilldown ---------- */
function recordPool() {
  if (state.mode === "full" && state.findings) return state.findings;
  return state.agg.sample_records || [];
}

function filterRecords(pred) {
  return recordPool().filter(pred);
}

function openDrill(title, sub, records) {
  $("drawerTitle").textContent = title;
  $("drawerSub").textContent =
    sub +
    " · " +
    records.length +
    "건" +
    (state.mode === "agg" ? " (샘플·집계본)" : "");
  const body = $("drawerBody");
  if (!records.length) {
    body.innerHTML = '<p class="placeholder">해당 조건의 선례가 없습니다.</p>';
  } else {
    body.innerHTML = records
      .slice(0, 40)
      .map((r) => {
        const title =
          workName(r.work_type) +
          (r.record_type && r.record_type !== "finding" ? " · " + r.record_type : "");
        const url = r.source_url
          ? '<a href="' + esc(r.source_url) + '" target="_blank" rel="noopener">출처 ↗</a>'
          : "<span>출처 없음</span>";
        return (
          '<article class="prec-card">' +
          '<p class="pt">' +
          esc(title) +
          "</p>" +
          '<p class="px">' +
          esc((r.source_excerpt || "").slice(0, 420) || "(발췌 없음)") +
          "</p>" +
          '<div class="pf">' +
          "<span>" +
          esc(dispOf(r)) +
          "</span>" +
          "<span>" +
          esc(r.source || "") +
          "</span>" +
          "<span>" +
          esc(r.year || "") +
          "</span>" +
          "<span>" +
          esc(r.org_name || r.org_type || "") +
          "</span>" +
          url +
          "</div></article>"
        );
      })
      .join("");
  }
  $("drawer").classList.add("is-open");
  $("drawer").setAttribute("aria-hidden", "false");
  const bd = $("drawerBackdrop");
  bd.hidden = false;
  bd.classList.add("is-open");
}

function closeDrawer() {
  $("drawer").classList.remove("is-open");
  $("drawer").setAttribute("aria-hidden", "true");
  const bd = $("drawerBackdrop");
  bd.classList.remove("is-open");
  bd.hidden = true;
}

/* ---------- bars ---------- */
function renderHBars(el, rows, opts) {
  opts = opts || {};
  const max = Math.max(1, ...rows.map((r) => r.n));
  el.innerHTML = rows
    .map((r, i) => {
      const pct = Math.round((r.n / max) * 100);
      const fillClass = opts.soft ? "soft" : i === 0 ? "deep" : "";
      return (
        '<div class="hbar-row" data-i="' +
        i +
        '" role="button" tabindex="0">' +
        '<span class="lab" title="' +
        esc(r.label) +
        '">' +
        esc(r.label) +
        "</span>" +
        '<div class="hbar-track"><div class="hbar-fill ' +
        fillClass +
        '" style="width:' +
        pct +
        '%"></div></div>' +
        '<span class="hbar-n">' +
        fmtNum(r.n) +
        "</span></div>"
      );
    })
    .join("");
  el.querySelectorAll(".hbar-row").forEach((node) => {
    const i = Number(node.getAttribute("data-i"));
    const row = rows[i];
    const go = () => {
      if (row && row.onClick) row.onClick();
    };
    node.addEventListener("click", go);
    node.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        go();
      }
    });
  });
}

/* ---------- public lens ---------- */
function publicSliceCounts() {
  const a = state.agg;
  // When filters set and full data available, recompute; else use agg + filter labels only
  if (state.mode === "full" && (state.filterWork || state.filterDisp)) {
    let rows = state.findings;
    if (state.filterWork) rows = rows.filter((r) => r.work_type === state.filterWork);
    if (state.filterDisp) rows = rows.filter((r) => dispOf(r) === state.filterDisp);
    const workM = new Map();
    const dispM = new Map();
    for (const r of rows) {
      const w = r.work_type || "미상";
      workM.set(w, (workM.get(w) || 0) + 1);
      const d = dispOf(r);
      dispM.set(d, (dispM.get(d) || 0) + 1);
    }
    return {
      total: rows.length,
      work: [...workM.entries()].sort((x, y) => y[1] - x[1]),
      disp: [...dispM.entries()].sort((x, y) => y[1] - x[1]),
      filtered: true,
    };
  }
  let work = a.work_type || [];
  let disp = a.disposition || [];
  let total = a.total;
  if (state.filterWork) {
    const hit = work.find(([c]) => c === state.filterWork);
    total = hit ? hit[1] : 0;
    work = hit ? [hit] : [];
  }
  if (state.filterDisp) {
    const hit = disp.find(([d]) => d === state.filterDisp);
    if (!state.filterWork) total = hit ? hit[1] : 0;
    disp = hit ? [hit] : [];
  }
  return { total, work, disp, filtered: !!(state.filterWork || state.filterDisp) };
}

function renderPublic() {
  const a = state.agg;
  const slice = publicSliceCounts();
  const rt = a.record_type || {};
  const kpis = $("publicKpis");
  const surgePos = (a.surge_types || []).filter((s) => s.delta > 0 && !s.small_n);
  const topSurge = surgePos[0];

  kpis.innerHTML = [
    {
      k: "표시 건수",
      v: fmtNum(slice.total),
      s: slice.filtered ? "필터 적용" : "전체 " + fmtNum(a.total),
      click: () =>
        openDrill(
          "선례 목록",
          slice.filtered ? "필터" : "전체",
          filterRecords((r) => {
            if (state.filterWork && r.work_type !== state.filterWork) return false;
            if (state.filterDisp && dispOf(r) !== state.filterDisp) return false;
            return true;
          })
        ),
    },
    {
      k: "지적",
      v: fmtNum(rt.finding || 0),
      s: "record_type",
      click: () =>
        openDrill(
          "지적 사례",
          "finding",
          filterRecords((r) => r.record_type === "finding")
        ),
    },
    {
      k: "컨설팅·면책",
      v: fmtNum((rt.consult || 0) + (rt.immunity || 0)),
      s: "consult " + (rt.consult || 0) + " · immunity " + (rt.immunity || 0),
      click: () =>
        openDrill(
          "컨설팅·면책",
          "consult|immunity",
          filterRecords((r) => r.record_type === "consult" || r.record_type === "immunity")
        ),
    },
    {
      k: "급증 유형",
      v: fmtNum(surgePos.length),
      s: a.surge_meta ? a.surge_meta.prev + "→" + a.surge_meta.cur : "—",
      click: () => {
        state.lens = "scout";
        syncLensUI();
        renderScout();
      },
    },
  ]
    .map(
      (c, i) =>
        '<button type="button" class="kpi-card" data-i="' +
        i +
        '"><div class="k">' +
        esc(c.k) +
        '</div><div class="v">' +
        esc(c.v) +
        '</div><div class="s">' +
        esc(c.s) +
        "</div></button>"
    )
    .join("");
  const cards = [
    {
      click: () =>
        openDrill(
          "선례 목록",
          slice.filtered ? "필터" : "전체",
          filterRecords((r) => {
            if (state.filterWork && r.work_type !== state.filterWork) return false;
            if (state.filterDisp && dispOf(r) !== state.filterDisp) return false;
            return true;
          })
        ),
    },
    {
      click: () =>
        openDrill(
          "지적 사례",
          "finding",
          filterRecords((r) => r.record_type === "finding")
        ),
    },
    {
      click: () =>
        openDrill(
          "컨설팅·면책",
          "consult|immunity",
          filterRecords((r) => r.record_type === "consult" || r.record_type === "immunity")
        ),
    },
    {
      click: () => {
        state.lens = "scout";
        syncLensUI();
        renderScout();
      },
    },
  ];
  kpis.querySelectorAll(".kpi-card").forEach((btn, i) => {
    btn.onclick = cards[i].click;
  });

  const workRows = slice.work.slice(0, 12).map(([c, n]) => ({
    label: workName(c),
    n,
    onClick: () =>
      openDrill(
        workName(c),
        "업무유형",
        filterRecords((r) => {
          if (r.work_type !== c) return false;
          if (state.filterDisp && dispOf(r) !== state.filterDisp) return false;
          return true;
        })
      ),
  }));
  renderHBars($("aWorkBars"), workRows);

  const dispRows = slice.disp.slice(0, 12).map(([d, n]) => ({
    label: d,
    n,
    onClick: () =>
      openDrill(
        d,
        "처분",
        filterRecords((r) => {
          if (dispOf(r) !== d) return false;
          if (state.filterWork && r.work_type !== state.filterWork) return false;
          return true;
        })
      ),
  }));
  renderHBars($("aDispBars"), dispRows, { soft: true });

  const surgeEl = $("publicSurge");
  if (topSurge) {
    surgeEl.innerHTML =
      '<button type="button" class="surge-badge" id="publicSurgeBtn">' +
      esc(topSurge.label) +
      " · " +
      (topSurge.year_prev || "") +
      "→" +
      (topSurge.year || "") +
      " " +
      fmtNum(topSurge.n_prev) +
      "→" +
      fmtNum(topSurge.n) +
      " (Δ" +
      (topSurge.delta > 0 ? "+" : "") +
      topSurge.delta +
      ", " +
      fmtRate(topSurge.rate) +
      ") — 발굴자 B1에서 더 보기</button>";
    $("publicSurgeBtn").onclick = () => {
      state.lens = "scout";
      syncLensUI();
      renderScout();
    };
  } else {
    surgeEl.innerHTML =
      '<p class="placeholder" style="margin:0">전년 대비 뚜렷한 증가(small_n 제외)가 집계되지 않았습니다.</p>';
  }

  // sample cards — prefer matching filter
  let samples = a.sample_records || [];
  if (state.filterWork) samples = samples.filter((r) => r.work_type === state.filterWork);
  if (state.filterDisp) samples = samples.filter((r) => dispOf(r) === state.filterDisp);
  if (samples.length < 3) samples = (a.sample_records || []).slice(0, 3);
  else samples = samples.slice(0, 3);
  $("publicSamples").innerHTML = samples
    .map((r, i) => {
      return (
        '<button type="button" class="sample-card" data-i="' +
        i +
        '">' +
        '<p class="t">' +
        esc(workName(r.work_type)) +
        "</p>" +
        '<p class="ex">' +
        esc((r.source_excerpt || "").slice(0, 180) || "(발췌 없음)") +
        "</p>" +
        '<div class="foot"><span>' +
        esc(dispOf(r)) +
        "</span><span>" +
        esc(r.source || "") +
        "</span><span>" +
        esc(r.year || "") +
        "</span></div></button>"
      );
    })
    .join("");
  $("publicSamples").querySelectorAll(".sample-card").forEach((btn, i) => {
    btn.onclick = () => openDrill(workName(samples[i].work_type), "샘플", [samples[i]]);
  });
}

/* ---------- scout lens ---------- */
function positiveSurges() {
  return (state.agg.surge_types || [])
    .filter((s) => s.delta > 0)
    .slice(0, 12);
}

function renderScout() {
  const a = state.agg;
  const surges = positiveSurges();
  const nonSmall = surges.filter((s) => !s.small_n);
  const denseCells = densestWorkOrgCells(6);
  const drafts = buildDraftCards(nonSmall.length ? nonSmall : surges, denseCells);

  $("scoutKpis").innerHTML = [
    { k: "패턴(급증 유형)", v: fmtNum(surges.length), s: "Δ>0" },
    { k: "유의 급증", v: fmtNum(nonSmall.length), s: "small_n 제외" },
    { k: "고밀도 셀", v: fmtNum(denseCells.length), s: "work×org" },
    { k: "초안 카드", v: fmtNum(drafts.length), s: "E 도크" },
  ]
    .map(
      (c) =>
        '<div class="kpi-card" style="cursor:default"><div class="k">' +
        esc(c.k) +
        '</div><div class="v">' +
        esc(c.v) +
        '</div><div class="s">' +
        esc(c.s) +
        "</div></div>"
    )
    .join("");

  if (a.surge_meta) {
    $("b1Hint").textContent =
      a.surge_meta.prev + "→" + a.surge_meta.cur + " · 실집계 · small_n 주의 · 수집 자료 내 증가";
  }
  const foot = $("b1Footnote");
  if (foot) {
    foot.innerHTML =
      "※ 수치는 <strong>수집 자료 내 증가</strong>입니다(전수·모집단 증가 단정 아님). small_n(표본 작음) 표시 건은 해석에 주의하세요.";
  }

  const barRows = surges.slice(0, 8).map((s) => ({
    label: s.label,
    n: s.n,
    onClick: () =>
      openDrill(
        s.label,
        "급증 " + (s.year_prev || "") + "→" + (s.year || ""),
        filterRecords((r) => r.work_type === s.code && Number(r.year) === Number(s.year))
      ),
  }));
  renderHBars($("b1Bars"), barRows);

  const tb = $("b1Table").querySelector("tbody");
  tb.innerHTML = surges
    .map((s, i) => {
      const cls = s.delta > 0 ? "delta-up" : "delta-dn";
      return (
        '<tr class="clickable" data-i="' +
        i +
        '"><td>' +
        esc(s.label) +
        (s.small_n ? '<span class="small-n">n소</span>' : "") +
        '</td><td class="num">' +
        fmtNum(s.n_prev) +
        '</td><td class="num">' +
        fmtNum(s.n) +
        '</td><td class="num ' +
        cls +
        '">' +
        (s.delta > 0 ? "+" : "") +
        s.delta +
        '</td><td class="num">' +
        fmtRate(s.rate) +
        "</td></tr>"
      );
    })
    .join("");
  tb.querySelectorAll("tr").forEach((tr) => {
    const i = Number(tr.getAttribute("data-i"));
    const s = surges[i];
    tr.onclick = () =>
      openDrill(
        s.label,
        "급증 " + (s.year_prev || "") + "→" + (s.year || ""),
        filterRecords((r) => r.work_type === s.code && (!s.year || Number(r.year) === Number(s.year)))
      );
  });

  renderHeatmap();
  renderYearLine();
  renderECards(drafts);
}

function densestWorkOrgCells(limit) {
  const cells = [];
  for (const row of state.agg.work_org || []) {
    for (const [org, n] of Object.entries(row.parts || {})) {
      cells.push({ code: row.code, label: row.label, org, n });
    }
  }
  cells.sort((a, b) => b.n - a.n);
  return cells.slice(0, limit);
}

function buildDraftCards(surges, denseCells) {
  const denseCodes = new Set(denseCells.map((c) => c.code));
  const picked = [];
  for (const s of surges) {
    if (denseCodes.has(s.code) || picked.length < 2) {
      const dens = denseCells.filter((c) => c.code === s.code);
      const orgHint = dens[0] ? dens[0].org + " 밀도 " + dens[0].n : "업무 전반";
      const samples = filterRecords((r) => r.work_type === s.code).slice(0, 3);
      const ids = samples.map((r) => r.id).filter(Boolean);
      while (ids.length < 3 && samples.length) break;
      // pad from sample_records
      if (ids.length < 3) {
        for (const r of state.agg.sample_records || []) {
          if (r.work_type === s.code && r.id && !ids.includes(r.id)) {
            ids.push(r.id);
            samples.push(r);
            if (ids.length >= 3) break;
          }
        }
      }
      picked.push({
        code: s.code,
        label: s.label,
        orgHint,
        delta: s.delta,
        rate: s.rate,
        year: s.year,
        year_prev: s.year_prev,
        n: s.n,
        n_prev: s.n_prev,
        sampleIds: ids.slice(0, 3),
        samples: samples.slice(0, 3),
      });
    }
    if (picked.length >= 3) break;
  }
  // ensure at least 1
  if (!picked.length && surges[0]) {
    const s = surges[0];
    const samples = filterRecords((r) => r.work_type === s.code).slice(0, 3);
    picked.push({
      code: s.code,
      label: s.label,
      orgHint: "급증 상위",
      delta: s.delta,
      rate: s.rate,
      year: s.year,
      year_prev: s.year_prev,
      n: s.n,
      n_prev: s.n_prev,
      sampleIds: samples.map((r) => r.id).filter(Boolean).slice(0, 3),
      samples,
    });
  }
  return picked.slice(0, 3);
}

function renderECards(drafts) {
  const el = $("eCards");
  if (!drafts.length) {
    el.innerHTML = '<p class="placeholder">초안 후보가 없습니다.</p>';
    return;
  }
  el.innerHTML = drafts
    .map((d, i) => {
      const ids = (d.sampleIds || [])
        .map(
          (id) =>
            '<button type="button" class="e-id" data-id="' + esc(id) + '">' + esc(id) + "</button>"
        )
        .join("");
      return (
        '<article class="e-card" data-i="' +
        i +
        '">' +
        "<h4>" +
        esc(d.label) +
        "</h4>" +
        "<p>검토용 시사: " +
        esc(String(d.year_prev)) +
        "→" +
        esc(String(d.year)) +
        " " +
        fmtNum(d.n_prev) +
        "→" +
        fmtNum(d.n) +
        " (Δ" +
        (d.delta > 0 ? "+" : "") +
        d.delta +
        ", " +
        fmtRate(d.rate) +
        "). " +
        esc(d.orgHint) +
        " 부근과 겹칩니다. 위법·부당을 단정하지 않습니다.</p>" +
        '<div class="e-ids">' +
        (ids || "<span class='small-n'>샘플 id 부족</span>") +
        "</div>" +
        '<button type="button" class="btn-secondary e-open" data-i="' +
        i +
        '">관련 선례 열기</button>' +
        "</article>"
      );
    })
    .join("");
  el.querySelectorAll(".e-open").forEach((btn) => {
    btn.onclick = () => {
      const d = drafts[Number(btn.getAttribute("data-i"))];
      openDrill(
        d.label + " · 초안",
        "E",
        d.samples.length
          ? d.samples
          : filterRecords((r) => r.work_type === d.code).slice(0, 12)
      );
    };
  });
  el.querySelectorAll(".e-id").forEach((btn) => {
    btn.onclick = () => {
      const id = btn.getAttribute("data-id");
      const hit = recordPool().filter((r) => String(r.id) === String(id));
      openDrill("선례 " + id, "id", hit.length ? hit : [{ id, source_excerpt: "(로컬 풀에서 미발견 — id만 표시)", disposition: null }]);
    };
  });
}

function renderHeatmap() {
  const a = state.agg;
  const rows = a.work_org || [];
  const orgs = a.labels.org_order.filter((o) => rows.some((r) => r.parts && r.parts[o]));
  let max = 1;
  for (const r of rows) for (const o of orgs) max = Math.max(max, r.parts[o] || 0);

  let html = '<table class="heat-table"><thead><tr><th></th>';
  for (const o of orgs) html += "<th>" + esc(o) + "</th>";
  html += "</tr></thead><tbody>";
  rows.forEach((r, ri) => {
    html += '<tr><th class="row-lab">' + esc(r.label) + "</th>";
    orgs.forEach((o, oi) => {
      const n = (r.parts && r.parts[o]) || 0;
      const t = n === 0 ? 0 : Math.min(SAGE_SCALE.length - 1, Math.ceil((n / max) * (SAGE_SCALE.length - 1)));
      const bg = SAGE_SCALE[t];
      const color = t >= 4 ? "#f4f7f5" : "var(--deep)";
      html +=
        '<td><button type="button" class="heat-cell' +
        (n === 0 ? " is-zero" : "") +
        '" style="background:' +
        bg +
        ";color:" +
        color +
        '" data-ri="' +
        ri +
        '" data-oi="' +
        oi +
        '">' +
        (n || "·") +
        "</button></td>";
    });
    html += "</tr>";
  });
  html += "</tbody></table>";
  $("cHeat").innerHTML = html;
  $("cHeat").querySelectorAll(".heat-cell").forEach((btn) => {
    btn.onclick = () => {
      const r = rows[Number(btn.getAttribute("data-ri"))];
      const o = orgs[Number(btn.getAttribute("data-oi"))];
      openDrill(
        r.label + " × " + o,
        "밀도",
        filterRecords((rec) => rec.work_type === r.code && rec.org_type === o)
      );
    };
  });
}

function renderYearLine() {
  const years = state.agg.year || [];
  const svg = $("cYear");
  if (!years.length) {
    svg.innerHTML = "";
    return;
  }
  const w = 640,
    h = 160,
    pad = { l: 36, r: 16, t: 16, b: 28 };
  const max = Math.max(1, ...years.map((y) => y[1]));
  const xs = years.map((_, i) => pad.l + (i * (w - pad.l - pad.r)) / Math.max(1, years.length - 1));
  const ys = years.map((y) => pad.t + (1 - y[1] / max) * (h - pad.t - pad.b));
  let d = "";
  xs.forEach((x, i) => {
    d += (i === 0 ? "M" : "L") + x.toFixed(1) + " " + ys[i].toFixed(1) + " ";
  });
  const dots = years
    .map((y, i) => {
      return (
        '<circle cx="' +
        xs[i].toFixed(1) +
        '" cy="' +
        ys[i].toFixed(1) +
        '" r="5" fill="#5B7C73" class="yr-dot" data-i="' +
        i +
        '" style="cursor:pointer" />' +
        '<text x="' +
        xs[i].toFixed(1) +
        '" y="' +
        (h - 8) +
        '" text-anchor="middle" fill="#7A8087" font-size="11">' +
        y[0] +
        "</text>"
      );
    })
    .join("");
  svg.innerHTML =
    '<polyline fill="none" stroke="#8DA399" stroke-width="2.5" points="' +
    xs.map((x, i) => x.toFixed(1) + "," + ys[i].toFixed(1)).join(" ") +
    '" />' +
    '<path d="' +
    d +
    '" fill="none" stroke="#3F5D50" stroke-width="1.5" opacity="0.35" />' +
    dots;
  svg.querySelectorAll(".yr-dot").forEach((c) => {
    c.addEventListener("click", () => {
      const i = Number(c.getAttribute("data-i"));
      const y = years[i][0];
      openDrill(
        String(y) + "년",
        "연도",
        filterRecords((r) => Number(r.year) === Number(y))
      );
    });
  });
}

/* ---------- lens switch ---------- */
function syncLensUI() {
  const isPublic = state.lens === "public";
  $("lensPublic").setAttribute("aria-pressed", isPublic ? "true" : "false");
  $("lensScout").setAttribute("aria-pressed", isPublic ? "false" : "true");
  $("lensPublicPanel").hidden = !isPublic;
  $("lensScoutPanel").hidden = isPublic;
}

function renderAll() {
  syncLensUI();
  renderPublic();
  renderScout();
}

function boot() {
  $("lensPublic").onclick = () => {
    state.lens = "public";
    syncLensUI();
  };
  $("lensScout").onclick = () => {
    state.lens = "scout";
    syncLensUI();
  };
  $("drawerClose").onclick = closeDrawer;
  $("drawerBackdrop").onclick = closeDrawer;
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });
  loadData().catch((err) => {
    $("loadStatus").textContent = "로드 실패: " + (err && err.message ? err.message : err);
  });
}

boot();
