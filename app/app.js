/* 감사 선례 도우미 — P0 hero (상황→보완→선례→선택→메모·출처)
 * Prefer real index; fallback hero-sample (demo). Static Pages cannot proxy gov sites.
 */
(() => {
  const params = new URLSearchParams(location.search);
  if (params.get("view") === "search") {
    params.delete("view");
    const qs = params.toString();
    location.replace("./search.html" + (qs ? "?" + qs : ""));
    return;
  }

  const INDEX_MANIFEST = "./data/index/manifest.json";
  const HERO_SAMPLE = "./data/hero-sample.json";
  const FINDINGS_LOCAL = ["../data/findings.json", "../data/findings.all.json"];
  const RESULT_CAP = 12;
  const BOOTSTRAP_BYTE_BUDGET = 6 * 1024 * 1024;
  const MIN_CONF = 0.6;
  const PACK_FILES = { contract: "contract.json", subsidy: "subsidy.json" };
  const PACK_WORK_CODES = { contract: ["02"], subsidy: ["08", "07", "06"] };

  const QUALITY_LABEL = {
    "list-only": "목록만",
    list_only: "목록만",
    secured: "본문 확보",
    body: "본문 확보",
    matched: "근거 대조 완료",
  };
  const TRUST_LABEL = { high: "고신뢰", review: "검토중" };
  const KIND_LABEL = {
    finding: "지적",
    immunity: "면책",
    consult: "사전컨설팅",
  };

  const state = {
    data: null,
    mode: "none", // index | demo | fallback
    corpusCount: null,
    connected: false,
    checked: new Set(),
    focusedId: null,
    highlighted: new Set(),
    expandedOriginal: new Set(),
    packId: "contract",
    pack: null,
    followUp: { org_type: "", work_stage: "", timing: "" },
    followUpReady: false,
    failure: null,
    manifest: null,
    shardCache: new Map(),
    hydrateMap: null, // id -> fuller record
    searchError: null,
  };

  const $ = (sel, rootEl = document) => rootEl.querySelector(sel);

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function isDemoLike() {
    return state.mode === "demo" || state.mode === "fallback";
  }

  function situationText() {
    return (($("#situationInput") && $("#situationInput").value) || "").trim();
  }

  function userWorkType() {
    return (($("#situationWorkType") && $("#situationWorkType").textContent) || "").trim();
  }

  /* —— disposition labels (do not invent) —— */
  function dispositionLabel(ev) {
    const raw = ev.disposition;
    const kind = ev.kind || ev.record_type || "finding";
    if (kind === "immunity" || kind === "consult") {
      if (kind === "consult") return { text: "해당 없음", cls: "badge-disp-none" };
      const o = (ev.immunity && ev.immunity.outcome) || raw;
      if (o == null || o === "") return { text: "처분 미확인", cls: "badge-disp-unknown" };
      return { text: "면책 " + o, cls: "badge-disp" };
    }
    if (raw == null || raw === undefined) {
      return { text: "처분 미확인", cls: "badge-disp-unknown" };
    }
    const s = String(raw).trim();
    if (s === "") {
      const q = normalizeQuality(ev.quality || ev.text_quality);
      if (q === "list-only") return { text: "처분 미확인", cls: "badge-disp-unknown" };
      return { text: "원문에 처분 기재 없음", cls: "badge-disp-nobody" };
    }
    if (/해당\s*없/.test(s) || s === "-" || s === "—") {
      return { text: "해당 없음", cls: "badge-disp-none" };
    }
    if (/미부과|처분\s*없|부과\s*없/.test(s) || s === "없음") {
      return { text: "미부과 확인", cls: "badge-disp-nopenalty" };
    }
    return { text: s, cls: "badge-disp" };
  }

  function normalizeQuality(q) {
    if (q === "body" || q === "secured") return "secured";
    if (q === "matched") return "matched";
    if (q === "list_only" || q === "list-only") return "list-only";
    return q || "list-only";
  }

  function hasOriginal(ev) {
    const url = (ev.source_url || "").trim();
    const excerpt = (ev.excerpt || ev.source_excerpt || "").trim();
    const hasUrl = !!(url && url !== "#");
    const hasExcerpt = excerpt.length > 0 && normalizeQuality(ev.quality) !== "list-only";
    return { hasUrl, hasExcerpt, ok: hasUrl || hasExcerpt };
  }

  /* —— scope badge —— */
  function renderScopeBadge() {
    const badge = $("#scopeBadge");
    const modeEl = $("#scopeMode");
    const countEl = $("#scopeCount");
    const noteEl = $("#scopeNote");
    if (!badge) return;
    badge.classList.remove("is-demo", "is-fallback", "is-index");
    let modeLabel = "확인 중…";
    let note = "";
    if (state.mode === "index") {
      modeLabel = "실인덱스";
      badge.classList.add("is-index");
      note = "샤드 검색 · 로컬/Pages 정적";
    } else if (state.mode === "demo") {
      modeLabel = "데모 샘플";
      badge.classList.add("is-demo");
      note = "합성·데모 포함 · 실무 내보내기 잠금";
    } else if (state.mode === "fallback") {
      modeLabel = "폴백";
      badge.classList.add("is-fallback");
      note = "인덱스 없음 · 실무 내보내기 잠금";
    }
    modeEl.textContent = modeLabel;
    if (state.corpusCount != null) {
      countEl.textContent = "· " + Number(state.corpusCount).toLocaleString("ko-KR") + "건";
    } else {
      countEl.textContent = "";
    }
    noteEl.textContent = note ? "· " + note : "";
    const banner = $("#demoLockBanner");
    if (banner) banner.hidden = !isDemoLike();
    updateExportLocks();
  }

  function updateExportLocks() {
    const lock = isDemoLike() || !state.connected;
    const btnSources = $("#btnCopyWithSources");
    const btnConfirm = $("#btnConfirmExport");
    const btnDraft = $("#btnCopyDraft");
    if (btnDraft) btnDraft.disabled = !state.connected;
    if (btnSources) {
      btnSources.disabled = lock;
      btnSources.title = isDemoLike()
        ? "데모/폴백 — 실무용 출처포함 복사 잠금"
        : "메모 + 출처 목록(URL·수집일) 복사";
    }
    if (btnConfirm) {
      btnConfirm.disabled = lock;
      btnConfirm.title = isDemoLike()
        ? "데모/폴백 — 실무용 확정/내보내기 잠금"
        : "실무용 검토메모 확정(출처 포함 복사)";
    }
  }

  /* —— data load —— */
  async function loadSample() {
    const res = await fetch(HERO_SAMPLE, { cache: "no-store" });
    if (!res.ok) throw new Error("hero-sample.json 로드 실패");
    state.data = await res.json();
    if (state.mode === "none") {
      state.mode = "demo";
      state.corpusCount = (state.data.evidence || []).length;
    }
    hydrateStatic();
    renderMemoFields(false);
    renderScopeBadge();
  }

  async function tryLoadIndex() {
    try {
      const r = await fetch(INDEX_MANIFEST, { cache: "no-store" });
      if (!r.ok) return false;
      const man = await r.json();
      if (!man || !Array.isArray(man.shards) || !man.shards.length) return false;
      state.manifest = man;
      state.mode = "index";
      state.corpusCount = man.n_docs || null;
      renderScopeBadge();
      return true;
    } catch {
      return false;
    }
  }

  async function tryHydrateFindings() {
    for (const url of FINDINGS_LOCAL) {
      try {
        const r = await fetch(url, { cache: "no-store" });
        if (!r.ok) continue;
        const data = await r.json();
        const arr = Array.isArray(data) ? data : [];
        if (!arr.length) continue;
        const map = new Map();
        for (const rec of arr) {
          if (rec && rec.id) map.set(String(rec.id), rec);
        }
        state.hydrateMap = map;
        return true;
      } catch {
        /* next — Pages cannot reach ../data */
      }
    }
    return false;
  }

  function hydrateStatic() {
    const d = state.data;
    if (!d) return;
    if (d.appTitle) $("#appTitle").textContent = d.appTitle;
    if (d.tagline) $("#tagline").textContent = d.tagline;
    if (d.situation) {
      $("#situationLabel").textContent = d.situation.label || "지금 하려는 일";
      const input = $("#situationInput");
      if (input && !input.dataset.userEdited) {
        input.value = d.situation.text || "";
      }
      $("#situationDomain").textContent = d.situation.domain || "";
      $("#situationWorkType").textContent = d.situation.workType || "";
    }
    if (state.pack) applyPackToUi();
  }

  async function loadPack(packId) {
    const file = PACK_FILES[packId];
    if (!file) throw new Error("unknown pack: " + packId);
    const res = await fetch("./domain-packs/" + file, { cache: "no-store" });
    if (!res.ok) throw new Error("pack load failed: " + file);
    const pack = await res.json();
    state.packId = packId;
    state.pack = pack;
    return pack;
  }

  function applyPackToUi() {
    const pack = state.pack;
    if (!pack) return;
    $("#situationDomain").textContent = pack.situationDomain || pack.label;
    $("#situationWorkType").textContent = pack.defaultWorkType || pack.labelLong || "";
    const input = $("#situationInput");
    if (input && pack.situationPlaceholder) {
      input.placeholder = pack.situationPlaceholder;
    }
    document.querySelectorAll(".pack-btn").forEach((btn) => {
      const on = btn.getAttribute("data-pack") === state.packId;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
    renderWorkTypeChips();
    renderChecklist();
    if (state.data && state.data.memo) {
      const prev = {};
      (state.data.memo.fields || []).forEach((f) => {
        const el = $("#memo-" + f.id);
        if (el) prev[f.id] = el.value;
      });
      renderMemoFields(state.connected);
      Object.keys(prev).forEach((id) => {
        const el = $("#memo-" + id);
        if (el && prev[id]) el.value = prev[id];
      });
    }
  }

  function renderWorkTypeChips() {
    const host = $("#workTypeChips");
    if (!host) return;
    host.innerHTML = "";
    const types = (state.pack && state.pack.workTypes) || [];
    const current = userWorkType();
    types.forEach((wt) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "worktype-chip" + (wt === current ? " is-on" : "");
      btn.textContent = wt;
      btn.addEventListener("click", () => {
        $("#situationWorkType").textContent = wt;
        host.querySelectorAll(".worktype-chip").forEach((c) => c.classList.remove("is-on"));
        btn.classList.add("is-on");
      });
      host.appendChild(btn);
    });
  }

  function renderChecklist() {
    const box = $("#packChecklist");
    const list = $("#checklistList");
    if (!box || !list) return;
    list.innerHTML = "";
    const items = (state.pack && state.pack.checklist) || [];
    if (!items.length) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item.prompt + (item.hint ? " (" + item.hint + ")" : "");
      list.appendChild(li);
    });
  }

  function memoPlaceholderFor(field) {
    const hints = (state.pack && state.pack.memoFieldHints) || {};
    return hints[field.id] || field.placeholder || "";
  }

  function ensureMemoFields() {
    if (!state.data) state.data = {};
    if (!state.data.memo) {
      state.data.memo = {
        fields: [
          { id: "overview", label: "업무 개요", placeholder: "하려는 업무를 한 줄로" },
          { id: "refs", label: "참고 선례", placeholder: "인용할 선례 제목·출처" },
          { id: "diff", label: "적용상 차이", placeholder: "같음/다름 요약" },
          { id: "grounds", label: "근거 발췌", placeholder: "본문 확보된 근거만" },
          { id: "sources", label: "출처·수집일", placeholder: "선택 근거의 URL·수집일" },
          { id: "open", label: "미확인 사항", placeholder: "미확인·추가 확인 필요" },
          { id: "decision", label: "담당자 판단", placeholder: "결재권자 판단용 메모" },
        ],
        draft: {},
      };
    }
    const ids = (state.data.memo.fields || []).map((f) => f.id);
    if (!ids.includes("sources")) {
      const openIdx = state.data.memo.fields.findIndex((f) => f.id === "open");
      const srcField = {
        id: "sources",
        label: "출처·수집일",
        placeholder: "선택 근거의 URL·수집일",
      };
      if (openIdx >= 0) state.data.memo.fields.splice(openIdx, 0, srcField);
      else state.data.memo.fields.push(srcField);
    }
    if (!ids.includes("open")) {
      state.data.memo.fields.push({
        id: "open",
        label: "미확인 사항",
        placeholder: "미확인·추가 확인 필요",
      });
    }
  }

  function renderMemoFields(fillDraft) {
    ensureMemoFields();
    const form = $("#memoForm");
    form.innerHTML = "";
    const fields = state.data.memo.fields;
    const draft = state.data.memo.draft || {};
    fields.forEach((f) => {
      const wrap = document.createElement("div");
      wrap.className = "field";
      const label = document.createElement("label");
      label.htmlFor = "memo-" + f.id;
      label.textContent = f.label;
      const ta = document.createElement("textarea");
      ta.id = "memo-" + f.id;
      ta.name = f.id;
      ta.rows = f.id === "grounds" || f.id === "diff" || f.id === "sources" || f.id === "open" ? 3 : 2;
      ta.placeholder = memoPlaceholderFor(f);
      if (fillDraft && draft[f.id]) ta.value = draft[f.id];
      ta.addEventListener("input", persistDraftLocal);
      wrap.append(label, ta);
      form.append(wrap);
    });
    updateExportLocks();
  }

  function persistDraftLocal() {
    try {
      const payload = collectMemoObject();
      localStorage.setItem("audit-helper-hero-draft", JSON.stringify({
        at: Date.now(),
        situation: situationText(),
        followUp: { ...state.followUp },
        memo: payload,
        checked: [...state.checked],
      }));
    } catch {
      /* ignore */
    }
  }

  function collectMemoObject() {
    ensureMemoFields();
    const out = {};
    (state.data.memo.fields || []).forEach((f) => {
      out[f.id] = (($("#memo-" + f.id) || {}).value || "").trim();
    });
    return out;
  }

  function byId(id) {
    return (state.data.evidence || []).find((e) => e.id === id);
  }

  function enrichFromHydrate(ev) {
    if (!state.hydrateMap || !ev || !ev.id) return ev;
    const full = state.hydrateMap.get(String(ev.id));
    if (!full) return ev;
    return {
      ...ev,
      source_url: ev.source_url || full.source_url || "",
      source_excerpt: ev.source_excerpt || full.source_excerpt || ev.excerpt || "",
      excerpt: ev.excerpt || full.source_excerpt || full.excerpt || "",
      added_at: ev.added_at || full.added_at || "",
      disposition: ev.disposition != null ? ev.disposition : full.disposition,
      org_type: ev.org_type || full.org_type || "",
      work_type: ev.work_type || full.work_type || "",
      year: ev.year != null ? ev.year : full.year,
      org: ev.org || full.org_name || "",
    };
  }

  /* —— match why / diff —— */
  function tokenize(text) {
    return String(text || "")
      .toLowerCase()
      .split(/[\s,./·|]+/)
      .map((t) => t.trim())
      .filter((t) => t.length >= 2);
  }

  function whyMatched(ev, sit, workType) {
    if (ev.matchWhy) return ev.matchWhy;
    const tokens = tokenize(sit);
    const hay = [ev.title, ev.excerpt, ev.search_text, ev.work_type, ev.org]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    const hits = tokens.filter((t) => hay.includes(t)).slice(0, 6);
    const wt = workType || userWorkType();
    const wtHit =
      wt &&
      (String(ev.work_type_label || "").includes(wt) ||
        String(ev.title || "").includes(wt) ||
        String(ev.excerpt || "").includes(wt) ||
        (state.pack &&
          (state.pack.workTypes || []).some(
            (w) => hay.includes(w.toLowerCase()) && w === wt
          )));
    const parts = [];
    if (hits.length) parts.push("키워드 겹침: " + hits.join(", "));
    if (wtHit) parts.push("업무유형 유사: " + wt);
    if (ev.work_type && PACK_WORK_CODES[state.packId]?.includes(String(ev.work_type))) {
      parts.push("업무코드 " + ev.work_type);
    }
    if (!parts.length) parts.push("검색어·도메인 팩 기준으로 후보에 포함");
    return parts.join(" · ");
  }

  function diffVsUser(ev) {
    if (ev.matchDiff) return ev.matchDiff;
    const diffs = [];
    const uOrg = state.followUp.org_type;
    const uYear = state.followUp.timing;
    const uWt = userWorkType();
    if (uOrg && ev.org_type && String(ev.org_type) !== uOrg) {
      diffs.push("기관유형: 나 " + uOrg + " / 선례 " + ev.org_type);
    } else if (!uOrg) {
      diffs.push("기관유형: 내 상황 미확인");
    }
    if (uYear && ev.year && String(ev.year) !== String(uYear).replace(/이전.*/, "")) {
      if (!(uYear === "2022이전" && Number(ev.year) <= 2022)) {
        diffs.push("연도: 나 " + uYear + " / 선례 " + ev.year);
      }
    } else if (!uYear) {
      diffs.push("시기: 내 상황 미확인");
    }
    const evWt = ev.work_type_label || ev.workTypeLabel || "";
    if (uWt && evWt && evWt !== uWt && !String(ev.title || "").includes(uWt)) {
      diffs.push("업무유형: 나 " + uWt + (evWt ? " / 선례 " + evWt : ""));
    }
    if (!diffs.length) return "명백한 기관·연도·업무유형 차이는 표시할 만큼 확인되지 않음";
    return diffs.join(" · ");
  }

  function formatAddedAt(v) {
    if (!v) return "";
    const s = String(v);
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    return s;
  }

  /* —— cards —— */
  function renderEvidence() {
    const list = $("#evidenceList");
    list.classList.add("is-filled");
    list.innerHTML = "";
    const tip = $("#originalTip");
    if (tip) tip.hidden = false;

    const showInMain = (state.data.evidence || []).filter((ev) => {
      if (ev.kind === "immunity" || ev.kind === "consult") return false;
      return true;
    });

    if (!showInMain.length) {
      list.classList.remove("is-filled");
      list.innerHTML = '<p class="placeholder">표시할 지적 선례가 없습니다.</p>';
    } else {
      showInMain.forEach((ev) => {
        list.appendChild(buildEvidenceCard(enrichFromHydrate(ev), { selectable: true }));
      });
    }
    renderRelated();
    renderDistance();
    rebuildMemoFromSelection();
  }

  function buildEvidenceCard(ev, opts = {}) {
    const card = document.createElement("article");
    const q = normalizeQuality(ev.quality || ev.text_quality);
    card.className = `evidence-card quality-${q}`;
    card.dataset.id = ev.id;
    if (state.highlighted.has(ev.id)) card.classList.add("highlighted");
    if (state.focusedId === ev.id) card.classList.add("is-selected");
    if (state.checked.has(ev.id)) card.classList.add("is-checked");
    if (ev._synthetic) card.classList.add("is-synthetic");

    if (opts.selectable) {
      const selRow = document.createElement("div");
      selRow.className = "card-select-row";
      const lab = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = state.checked.has(ev.id);
      const canCheck = ev.canAddToMemo !== false && q !== "list-only";
      cb.disabled = !canCheck;
      cb.addEventListener("click", (e) => e.stopPropagation());
      cb.addEventListener("change", (e) => {
        e.stopPropagation();
        if (cb.checked) state.checked.add(ev.id);
        else state.checked.delete(ev.id);
        card.classList.toggle("is-checked", cb.checked);
        rebuildMemoFromSelection();
        persistDraftLocal();
      });
      lab.append(cb, document.createTextNode(canCheck ? "메모에 포함" : "목록만 — 선택 불가"));
      selRow.append(lab);
      card.append(selRow);
    }

    const badgeRow = document.createElement("div");
    badgeRow.className = "badge-row";

    const qBadge = document.createElement("span");
    qBadge.className = `badge badge-${q}`;
    qBadge.textContent = QUALITY_LABEL[q] || q;
    badgeRow.append(qBadge);

    const trust = document.createElement("span");
    const tKey = ev.trust === "high" || (ev.tag_confidence != null && Number(ev.tag_confidence) >= MIN_CONF && !ev.review)
      ? "high"
      : "review";
    trust.className = `badge badge-trust-${tKey}`;
    trust.textContent = TRUST_LABEL[tKey];
    badgeRow.append(trust);

    const disp = dispositionLabel(ev);
    const dBadge = document.createElement("span");
    dBadge.className = `badge ${disp.cls}`;
    dBadge.textContent = disp.text;
    badgeRow.append(dBadge);

    const orig = hasOriginal(ev);
    const oBadge = document.createElement("span");
    oBadge.className = `badge ${orig.ok ? "badge-original-yes" : "badge-original-no"}`;
    oBadge.textContent = orig.hasUrl
      ? "원문 URL"
      : orig.hasExcerpt
        ? "발췌만"
        : "원문 없음";
    badgeRow.append(oBadge);

    if (ev.kind && ev.kind !== "finding") {
      const k = document.createElement("span");
      k.className = "badge badge-kind";
      k.textContent = KIND_LABEL[ev.kind] || ev.kind;
      badgeRow.append(k);
    }
    if (ev._synthetic) {
      const syn = document.createElement("span");
      syn.className = "badge badge-synthetic";
      syn.textContent = "합성 예시";
      badgeRow.append(syn);
    }

    const title = document.createElement("h4");
    title.className = "card-title";
    title.textContent = ev.title || "(제목 없음)";

    const meta = document.createElement("p");
    meta.className = "card-meta";
    const metaParts = [
      ev.source || [ev.audit_org, ev.year].filter(Boolean).join(" · "),
      ev.org || ev.org_name,
      ev.org_type,
      ev.work_type ? "업무 " + ev.work_type : "",
    ].filter(Boolean);
    meta.textContent = metaParts.join(" · ");

    const why = document.createElement("p");
    why.className = "card-why";
    why.innerHTML = "<strong>왜 매칭</strong> — " + escapeHtml(whyMatched(ev, situationText(), userWorkType()));

    const diff = document.createElement("p");
    diff.className = "card-diff";
    diff.innerHTML = "<strong>나와의 차이</strong> — " + escapeHtml(diffVsUser(ev));

    const excerpt = document.createElement("p");
    excerpt.className = "card-excerpt";
    const exText = ev.excerpt || ev.source_excerpt || "";
    excerpt.innerHTML = applyHighlights(exText, ev.highlightSpans, state.highlighted.has(ev.id));

    const actions = document.createElement("div");
    actions.className = "card-actions";

    if (opts.selectable) {
      const focusBtn = document.createElement("button");
      focusBtn.type = "button";
      focusBtn.className = "btn-ghost" + (state.focusedId === ev.id ? " is-on" : "");
      focusBtn.textContent = state.focusedId === ev.id ? "선택됨 · 관련" : "관련 보기";
      focusBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        focusFinding(ev.id);
      });
      actions.append(focusBtn);
    }

    const origBtn = document.createElement("button");
    origBtn.type = "button";
    origBtn.className = "btn-ghost" + (state.expandedOriginal.has(ev.id) ? " is-on" : "");
    origBtn.textContent = "원문 불러오기";
    origBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openOriginal(ev);
    });
    actions.append(origBtn);

    const canHighlight = q === "secured" || q === "matched";
    if (canHighlight) {
      const hl = document.createElement("button");
      hl.type = "button";
      hl.className = "btn-ghost" + (state.highlighted.has(ev.id) ? " is-on" : "");
      hl.textContent = state.highlighted.has(ev.id) ? "하이라이트 끄기" : "원문 하이라이트";
      hl.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleHighlight(ev.id);
      });
      actions.append(hl);
    }

    card.append(badgeRow, title, meta, why, diff, excerpt, actions);

    const panel = document.createElement("div");
    panel.className = "excerpt-panel";
    panel.id = "excerpt-panel-" + ev.id;
    panel.hidden = !state.expandedOriginal.has(ev.id);
    const fullEx = ev.source_excerpt || ev.excerpt || "(발췌 없음)";
    const urlLine = (ev.source_url && ev.source_url !== "#")
      ? "출처 URL: " + ev.source_url
      : "출처 URL: 없음 (발췌만 또는 목록만)";
    const added = formatAddedAt(ev.added_at);
    panel.textContent =
      urlLine +
      (added ? "\n수집일: " + added : "") +
      "\n\n" +
      fullEx;
    card.append(panel);

    if (opts.selectable) {
      card.addEventListener("click", () => focusFinding(ev.id));
      card.setAttribute("role", "button");
      card.tabIndex = 0;
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          focusFinding(ev.id);
        }
      });
    }

    return card;
  }

  function applyHighlights(text, spans, active) {
    if (!active || !spans || !spans.length) return escapeHtml(text);
    const sorted = [...spans].sort((a, b) => a.start - b.start);
    let out = "";
    let cursor = 0;
    for (const s of sorted) {
      const start = Math.max(0, s.start);
      const end = Math.min(text.length, s.end);
      if (start < cursor) continue;
      out += escapeHtml(text.slice(cursor, start));
      out += `<mark>${escapeHtml(text.slice(start, end))}</mark>`;
      cursor = end;
    }
    out += escapeHtml(text.slice(cursor));
    return out;
  }

  function focusFinding(id) {
    state.focusedId = state.focusedId === id ? null : id;
    const ev = byId(id);
    if (ev && state.focusedId === id) {
      // selecting a card also triggers best-effort original expand if URL/excerpt
      const o = hasOriginal(ev);
      if (o.hasExcerpt || o.hasUrl) {
        /* keep existing expand state; user can click 원문 */
      }
    }
    renderEvidence();
  }

  function openOriginal(ev) {
    const enriched = enrichFromHydrate(ev);
    const url = (enriched.source_url || "").trim();
    if (url && url !== "#") {
      try {
        window.open(url, "_blank", "noopener,noreferrer");
      } catch {
        /* ignore */
      }
    }
    if (state.expandedOriginal.has(ev.id)) state.expandedOriginal.delete(ev.id);
    else state.expandedOriginal.add(ev.id);
    // re-render just panel if possible
    const panel = document.getElementById("excerpt-panel-" + ev.id);
    if (panel) {
      const fullEx = enriched.source_excerpt || enriched.excerpt || "(발췌 없음)";
      const urlLine = url && url !== "#"
        ? "출처 URL: " + url
        : "출처 URL: 없음 (발췌만 또는 목록만)";
      const added = formatAddedAt(enriched.added_at);
      panel.textContent =
        urlLine +
        (added ? "\n수집일: " + added : "") +
        "\n\n" +
        fullEx;
      panel.hidden = !state.expandedOriginal.has(ev.id);
    } else {
      renderEvidence();
    }
    $("#copyStatus").textContent = url && url !== "#"
      ? "출처 URL을 새 탭으로 열었습니다. 발췌 패널을 확인하세요."
      : "URL 없음 — 발췌 패널만 펼칩니다. (Pages는 외부 원문 대리 수집 불가)";
  }

  function renderRelated() {
    const lane = $("#relatedLane");
    const list = $("#relatedList");
    if (!lane || !list) return;
    list.innerHTML = "";
    if (!state.focusedId) {
      lane.hidden = true;
      return;
    }
    const selected = byId(state.focusedId);
    const ids = (selected && selected.relatedIds) || [];
    const related = ids
      .map(byId)
      .filter(Boolean)
      .filter((ev) => ev.kind === "immunity" || ev.kind === "consult");
    if (!related.length) {
      lane.hidden = true;
      return;
    }
    lane.hidden = false;
    related.forEach((ev) => {
      list.appendChild(buildEvidenceCard(enrichFromHydrate(ev), { selectable: false }));
    });
  }

  function toggleHighlight(id) {
    if (state.highlighted.has(id)) state.highlighted.delete(id);
    else state.highlighted.add(id);
    renderEvidence();
  }

  function renderDistance() {
    const panel = $("#distancePanel");
    if (!panel) return;
    const checked = [...state.checked].map(byId).filter(Boolean);
    const focus = state.focusedId ? byId(state.focusedId) : null;
    const base = checked[0] || focus;

    if (!state.connected) {
      panel.classList.remove("is-filled");
      panel.innerHTML = '<p class="placeholder">연결 후 같음·다름·확인 포인트가 표시됩니다.</p>';
      return;
    }

    panel.classList.add("is-filled");
    if (!base && state.data && state.data.distance) {
      const d = state.data.distance;
      panel.innerHTML = `
        <div class="distance-row"><span class="distance-chip">같음</span><p class="distance-body">${escapeHtml(d.same)}</p></div>
        <div class="distance-row"><span class="distance-chip">다름</span><p class="distance-body">${escapeHtml(d.diff)}</p></div>
        <div class="distance-row"><span class="distance-chip">확인</span><p class="distance-body">${escapeHtml(d.check)}</p></div>
        <div class="tip-card"><h4>한 줄 정리</h4><p>${escapeHtml(d.summary)}</p></div>`;
      return;
    }

    if (!base) {
      panel.innerHTML = `
        <div class="tip-card"><h4>카드 선택</h4>
        <p>왼쪽에서 선례를 체크하거나 「관련 보기」로 고르면 같음/다름이 채워집니다.</p></div>`;
      return;
    }

    const sameParts = [];
    const wt = userWorkType();
    if (wt) sameParts.push(wt);
    if (state.pack) sameParts.push(state.pack.label);
    const why = whyMatched(base, situationText(), wt);
    const diff = diffVsUser(base);
    const openBits = [];
    if (!state.followUp.org_type) openBits.push("기관유형 미확인");
    if (!state.followUp.timing) openBits.push("시기 미확인");
    if (!state.followUp.work_stage) openBits.push("업무단계 미확인(선택)");

    panel.innerHTML = `
      <div class="distance-row"><span class="distance-chip">같음</span>
        <p class="distance-body">${escapeHtml(sameParts.join(" · ") || "도메인 팩 기준 후보")}<br><span style="color:var(--muted);font-size:0.8rem">${escapeHtml(why)}</span></p></div>
      <div class="distance-row"><span class="distance-chip">다름</span>
        <p class="distance-body">${escapeHtml(diff)}</p></div>
      <div class="distance-row"><span class="distance-chip">확인</span>
        <p class="distance-body">${escapeHtml(openBits.length ? openBits.join(" · ") : "필수 보완항목 입력됨")}</p></div>
      <div class="tip-card"><h4>한 줄 정리</h4>
        <p>${escapeHtml(checked.length ? "체크 " + checked.length + "건 기준 · 목록만은 근거에서 제외됩니다." : "체크된 근거가 없습니다. 본문 확보 카드를 선택하세요.")}</p></div>`;
  }

  function rebuildMemoFromSelection() {
    if (!state.connected) return;
    ensureMemoFields();
    const sit = situationText();
    const selected = [...state.checked].map(byId).filter(Boolean).map(enrichFromHydrate);
    const usable = selected.filter((ev) => {
      const q = normalizeQuality(ev.quality || ev.text_quality);
      return q !== "list-only" && ev.canAddToMemo !== false;
    });

    const overview = sit || (state.data.memo.draft && state.data.memo.draft.overview) || "";
    const refs = usable
      .map((ev, i) => {
        const syn = ev._synthetic ? " [합성 예시]" : "";
        return `${i + 1}. ${ev.title}${syn} (${ev.source || ev.org || ""})`;
      })
      .join("\n");

    const diffLines = usable.map((ev) => `· ${ev.title}: ${diffVsUser(ev)}`).join("\n");
    const grounds = usable
      .map((ev) => {
        const q = QUALITY_LABEL[normalizeQuality(ev.quality)] || "";
        const snip = (ev.excerpt || ev.source_excerpt || "").slice(0, 280);
        const syn = ev._synthetic ? " [합성]" : "";
        return `· [${q}] ${ev.title}${syn}\n  ${snip}`;
      })
      .join("\n");

    const sources = usable
      .map((ev) => {
        const url = ev.source_url && ev.source_url !== "#" ? ev.source_url : "(URL 없음)";
        const added = formatAddedAt(ev.added_at) || "수집일 미확인";
        return `· ${ev.title}\n  URL: ${url}\n  수집일: ${added}`;
      })
      .join("\n");

    const openParts = [];
    if (!state.followUp.org_type) openParts.push("기관유형 미확인");
    if (!state.followUp.work_stage) openParts.push("업무 단계 미확인(선택)");
    if (!state.followUp.timing) openParts.push("대략 시기 미확인");
    if (!usable.length) openParts.push("메모에 포함된 본문 확보 근거 없음");
    if (usable.some((e) => e._synthetic)) openParts.push("합성 예시 포함 — 실무 제출 전 제거");
    if (isDemoLike()) openParts.push("데모/폴백 모드 — 실무 확정 전 실인덱스 확인");
    openParts.push("관련 법령·지침 현행성 확인 필요");

    const setVal = (id, val) => {
      const el = $("#memo-" + id);
      if (el) el.value = val;
    };

    setVal("overview", overview);
    setVal("refs", refs || "(선택된 선례 없음)");
    setVal("diff", diffLines || "(선택 후 차이 표시)");
    setVal("grounds", grounds || "(본문 확보 근거를 체크하세요. 목록만은 불가)");
    setVal("sources", sources || "(선택 근거 없음)");
    setVal("open", openParts.map((x) => "· " + x).join("\n"));
    if (!$("#memo-decision")?.value) {
      setVal(
        "decision",
        "단정하지 않음. 본문 확보·출처 확인된 건만 인용. 담당자·결재권자 최종 판단."
      );
    }
    persistDraftLocal();
  }

  /* —— failure states —— */
  function showFailure(kind, detail) {
    state.failure = kind;
    const panel = $("#failurePanel");
    if (!panel) return;
    const map = {
      no_results: {
        title: "검색 결과 없음",
        body: "조건에 맞는 선례가 없습니다.",
        next: "다음: 키워드를 줄이거나 기관유형·시기를 비우고 다시 연결해 보세요. 검색 페이지에서 연도·기관 샤드를 지정할 수도 있습니다.",
        cls: "is-empty",
      },
      list_only: {
        title: "목록만 확보",
        body: "후보가 있으나 본문 발췌가 없어 메모 근거로 쓸 수 없습니다.",
        next: "다음: 「원문 불러오기」로 출처 URL을 확인하거나, 본문 확보 건이 있는 다른 키워드로 다시 검색하세요.",
        cls: "is-empty",
      },
      not_comparable: {
        title: "비교 어려움",
        body: "기관유형·시기·업무유형이 비어 있거나 선례와 어긋나 단순 비교가 어렵습니다.",
        next: "다음: 위의 보완 항목을 아는 범위만 채운 뒤 다시 연결하세요. 모르는 값은 미확인으로 둡니다.",
        cls: "",
      },
      search_error: {
        title: "검색 오류",
        body: detail || "인덱스/데이터를 불러오지 못했습니다.",
        next: "다음: 네트워크·경로를 확인하거나 페이지를 새로고침하세요. 데모 샘플로 흐름만 확인할 수 있습니다.",
        cls: "is-error",
      },
    };
    const m = map[kind];
    if (!m) {
      panel.hidden = true;
      return;
    }
    panel.hidden = false;
    panel.className = "failure-panel " + (m.cls || "");
    panel.innerHTML = `<p class="fail-title">${escapeHtml(m.title)}</p><p>${escapeHtml(m.body)}</p><p class="fail-next">${escapeHtml(m.next)}</p>`;
  }

  function clearFailure() {
    state.failure = null;
    const panel = $("#failurePanel");
    if (panel) {
      panel.hidden = true;
      panel.innerHTML = "";
    }
  }

  /* —— index search —— */
  function selectShardsForHero(f) {
    const shards = (state.manifest && state.manifest.shards) || [];
    const matchKey = (s) => {
      const [y, ot] = String(s.key).split("__");
      if (f.year && String(y) !== String(f.year)) return false;
      if (f.org && String(ot) !== f.org) return false;
      // hide edu school shard by default unless org filter is 교육
      if (!f.org && String(ot) === "교육") return false;
      return true;
    };
    let cand = shards.filter(matchKey);
    if (!cand.length) cand = shards.filter((s) => !String(s.key).includes("__교육"));
    const scored = cand
      .map((s) => {
        const y = Number(String(s.key).split("__")[0]) || 0;
        return { s, y };
      })
      .sort((a, b) => b.y - a.y || a.s.bytes - b.s.bytes);
    const picked = [];
    let budget = 0;
    for (const { s } of scored) {
      if (picked.length >= 5 && budget >= BOOTSTRAP_BYTE_BUDGET) break;
      picked.push(s);
      budget += s.bytes || 0;
      if (picked.length >= 8) break;
    }
    return picked;
  }

  async function fetchShard(meta) {
    if (state.shardCache.has(meta.id)) return state.shardCache.get(meta.id);
    const r = await fetch(`./data/index/${meta.file}`);
    if (!r.ok) throw new Error(`shard ${meta.id} HTTP ${r.status}`);
    const data = await r.json();
    const docs = Array.isArray(data.docs) ? data.docs : [];
    state.shardCache.set(meta.id, docs);
    return docs;
  }

  function keywordMatch(r, q) {
    if (!q) return true;
    const hay = [r.search_text, r.title, r.excerpt, r.org_name, r.work_type]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    const tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
    if (!tokens.length) return true;
    const hit = tokens.filter((t) => hay.includes(t));
    return hit.length >= Math.min(2, tokens.length) || hit.length >= 1;
  }

  function docToEvidence(r) {
    const q = normalizeQuality(r.text_quality);
    const trust =
      !r.review && r.tag_confidence != null && Number(r.tag_confidence) >= MIN_CONF
        ? "high"
        : "review";
    return {
      id: r.id,
      title: r.title || r.summary || "(제목 없음)",
      source: [r.audit_org || r.source || "", r.year].filter(Boolean).join(" · "),
      org: r.org_name || "",
      org_type: r.org_type || "",
      work_type: r.work_type || "",
      year: r.year,
      quality: q,
      text_quality: r.text_quality,
      trust,
      tag_confidence: r.tag_confidence,
      review: r.review,
      kind: r.record_type || "finding",
      excerpt: r.excerpt || r.source_excerpt || "",
      source_excerpt: r.source_excerpt || r.excerpt || "",
      source_url: r.source_url || r.document_url || "",
      added_at: r.added_at || "",
      disposition: r.disposition,
      immunity: r.immunity,
      highlightSpans: [],
      canAddToMemo: q !== "list-only",
      relatedIds: [],
      search_text: r.search_text || "",
    };
  }

  async function searchIndexEvidence() {
    const sit = situationText();
    const yearRaw = state.followUp.timing;
    const year =
      yearRaw && /^\d{4}$/.test(yearRaw) ? yearRaw : "";
    const org = state.followUp.org_type || "";
    const metas = selectShardsForHero({ year, org });
    let pool = [];
    for (const m of metas) {
      const docs = await fetchShard(m);
      pool.push(...docs);
    }
    const codes = PACK_WORK_CODES[state.packId] || [];
    const packWords = ((state.pack && state.pack.workTypes) || []).join(" ");
    const q = [sit, userWorkType(), packWords].filter(Boolean).join(" ");

    let out = pool.filter((r) => {
      if (r.hide_by_default || r.edu_school) return false;
      if (org && String(r.org_type) !== org) return false;
      if (year && String(r.year) !== year) return false;
      if (codes.length && r.work_type && codes.includes(String(r.work_type))) return true;
      return keywordMatch(r, q);
    });

    // prefer pack work codes, then keyword
    out.sort((a, b) => {
      const ac = codes.includes(String(a.work_type)) ? 1 : 0;
      const bc = codes.includes(String(b.work_type)) ? 1 : 0;
      if (bc !== ac) return bc - ac;
      const ta = !a.review && Number(a.tag_confidence) >= MIN_CONF ? 1 : 0;
      const tb = !b.review && Number(b.tag_confidence) >= MIN_CONF ? 1 : 0;
      if (tb !== ta) return tb - ta;
      return (Number(b.year) || 0) - (Number(a.year) || 0);
    });

    return out.slice(0, RESULT_CAP).map(docToEvidence);
  }

  function readFollowUpFromDom() {
    state.followUp = {
      org_type: ($("#fuOrgType") && $("#fuOrgType").value) || "",
      work_stage: ($("#fuWorkStage") && $("#fuWorkStage").value) || "",
      timing: ($("#fuTiming") && $("#fuTiming").value) || "",
    };
  }

  function needsFollowUpPrompt() {
    // Show once if org_type or timing missing — work_stage optional
    if (state.followUpReady) return false;
    return !state.followUp.org_type || !state.followUp.timing;
  }

  async function connectPrecedents() {
    const sit = situationText();
    if (!sit) {
      $("#copyStatus").textContent = "상황을 먼저 입력해 주세요.";
      return;
    }

    readFollowUpFromDom();
    const panel = $("#followUpPanel");
    if (needsFollowUpPrompt()) {
      if (panel) panel.hidden = false;
      state.followUpReady = true; // allow proceed on next click even if still blank
      $("#copyStatus").textContent =
        "기관유형·시기를 알면 선택하세요. 모르면 미확인으로 두고 다시 「선례 연결하기」를 눌러 주세요.";
      // If user already can see panel, still allow continue this click only after second intent:
      // First click reveals panel; second runs search. Unless they filled values already mid-way.
      if (!panel || panel.dataset.revealed === "1") {
        /* fall through on second click */
      } else {
        panel.dataset.revealed = "1";
        return;
      }
    } else if (panel) {
      panel.hidden = false; // keep visible for edits
    }

    readFollowUpFromDom();
    clearFailure();
    const cta = $("#ctaConnect");
    cta.disabled = true;
    cta.textContent = "연결 중…";

    try {
      let evidence = [];
      if (state.mode === "index" && state.manifest) {
        evidence = await searchIndexEvidence();
        // keep sample related/immunity only if demo merge not needed
        state.data.evidence = evidence;
        state.data.distance = null;
      } else {
        // demo / fallback: use sample evidence
        if (!state.data || !state.data.evidence) await loadSample();
        evidence = state.data.evidence || [];
      }

      const mainFindings = evidence.filter(
        (e) => e.kind === "finding" || !e.kind || e.kind === "finding"
      );
      const withBody = mainFindings.filter(
        (e) => normalizeQuality(e.quality || e.text_quality) !== "list-only"
      );

      if (!mainFindings.length) {
        showFailure("no_results");
      } else if (!withBody.length) {
        showFailure("list_only");
      } else if (!state.followUp.org_type && !state.followUp.timing) {
        showFailure("not_comparable");
      }

      state.connected = true;
      state.checked = new Set();
      // auto-check first usable non-list-only finding (max 2)
      let auto = 0;
      for (const ev of evidence) {
        if ((ev.kind === "immunity" || ev.kind === "consult") && ev.kind) continue;
        if (normalizeQuality(ev.quality) === "list-only") continue;
        if (ev.canAddToMemo === false) continue;
        state.checked.add(ev.id);
        auto++;
        if (auto >= 2) break;
      }

      renderMemoFields(true);
      renderEvidence();
      cta.textContent = "선례 연결됨 · 다시 검색";
      cta.classList.add("is-done");
      cta.disabled = false;
      // allow re-run
      state.connected = true;
      updateExportLocks();
      $("#copyStatus").textContent = isDemoLike()
        ? "데모/폴백 초안입니다. 실무용 내보내기는 잠겨 있습니다."
        : "초안이 채워졌습니다. 체크한 근거만 메모에 반영됩니다.";
    } catch (err) {
      console.error(err);
      showFailure("search_error", String(err.message || err));
      // fall back to sample if possible
      try {
        if (!state.data) await loadSample();
        state.mode = state.mode === "index" ? "fallback" : state.mode;
        if (state.mode === "index") state.mode = "fallback";
        renderScopeBadge();
        state.connected = true;
        renderMemoFields(true);
        renderEvidence();
      } catch {
        /* ignore */
      }
      cta.textContent = "선례 연결하기";
      cta.disabled = false;
      cta.classList.remove("is-done");
    }
  }

  function buildMemoText() {
    ensureMemoFields();
    const fields = state.data.memo.fields;
    return fields
      .map((f) => {
        const val = (($("#memo-" + f.id) || {}).value || "").trim();
        return `【${f.label}】\n${val}`;
      })
      .join("\n\n");
  }

  function buildSourcesAppendix() {
    const selected = [...state.checked].map(byId).filter(Boolean).map(enrichFromHydrate);
    const usable = selected.filter((ev) => normalizeQuality(ev.quality) !== "list-only");
    const lines = usable.map((ev, i) => {
      const url = ev.source_url && ev.source_url !== "#" ? ev.source_url : "(URL 없음)";
      const added = formatAddedAt(ev.added_at) || "수집일 미확인";
      return `${i + 1}. ${ev.title}\n   URL: ${url}\n   수집일: ${added}`;
    });
    return "【출처 목록】\n" + (lines.join("\n") || "(선택 근거 없음)");
  }

  async function copyText(text, okMsg) {
    try {
      await navigator.clipboard.writeText(text);
      $("#copyStatus").textContent = okMsg;
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
      $("#copyStatus").textContent = okMsg;
    }
  }

  async function copyDraft() {
    const banner = isDemoLike()
      ? "※ 데모/폴백 초안 미리보기 — 실무 제출·결재 근거로 사용하지 마세요.\n\n"
      : "";
    await copyText(banner + buildMemoText(), "초안을 클립보드에 복사했습니다.");
  }

  async function copyWithSources() {
    if (isDemoLike()) {
      $("#copyStatus").textContent = "데모/폴백에서는 실무용 출처포함 복사가 잠겨 있습니다.";
      return;
    }
    const text = buildMemoText() + "\n\n" + buildSourcesAppendix();
    await copyText(text, "메모+출처 목록을 복사했습니다.");
  }

  async function confirmExport() {
    if (isDemoLike()) {
      $("#copyStatus").textContent = "데모/폴백에서는 실무용 확정·내보내기가 잠겨 있습니다.";
      return;
    }
    const text =
      "【실무용 검토메모 — 확정 초안】\n" +
      "확정 시각: " +
      new Date().toLocaleString("ko-KR", { timeZone: "Asia/Seoul" }) +
      "\n\n" +
      buildMemoText() +
      "\n\n" +
      buildSourcesAppendix();
    await copyText(text, "실무용 검토메모(출처 포함)를 복사했습니다. 결재 시스템에 붙여 넣으세요.");
  }

  async function selectPack(packId) {
    try {
      await loadPack(packId);
      applyPackToUi();
    } catch (err) {
      console.warn("domain pack load failed; keeping sample defaults", err);
    }
  }

  function bind() {
    $("#ctaConnect").addEventListener("click", () => {
      connectPrecedents().catch(console.error);
    });
    $("#btnCopyDraft").addEventListener("click", () => {
      copyDraft().catch(console.error);
    });
    $("#btnCopyWithSources").addEventListener("click", () => {
      copyWithSources().catch(console.error);
    });
    $("#btnConfirmExport").addEventListener("click", () => {
      confirmExport().catch(console.error);
    });
    document.querySelectorAll(".pack-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-pack");
        if (id) selectPack(id);
      });
    });
    const input = $("#situationInput");
    if (input) {
      input.addEventListener("input", () => {
        input.dataset.userEdited = "1";
      });
    }
    ["#fuOrgType", "#fuWorkStage", "#fuTiming"].forEach((sel) => {
      const el = $(sel);
      if (!el) return;
      el.addEventListener("change", () => {
        readFollowUpFromDom();
        if (state.connected) {
          renderDistance();
          rebuildMemoFromSelection();
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    bind();
    const indexed = await tryLoadIndex();
    try {
      await loadSample();
      if (indexed) {
        state.mode = "index";
        state.corpusCount = state.manifest.n_docs;
        renderScopeBadge();
      } else {
        state.mode = "demo";
        state.corpusCount = (state.data.evidence || []).length;
        renderScopeBadge();
      }
    } catch (err) {
      console.error(err);
      state.mode = "fallback";
      renderScopeBadge();
      $("#evidenceList").innerHTML =
        '<p class="placeholder">hero-sample.json을 불러오지 못했습니다. 로컬 정적 서버로 app/을 열어 주세요.</p>';
      showFailure("search_error", String(err.message || err));
    }
    // best-effort hydrate (local only)
    tryHydrateFindings().then((ok) => {
      if (ok) {
        const note = $("#scopeNote");
        if (note && state.hydrateMap) {
          note.textContent = (note.textContent || "") + " · findings 로컬 보강 가능";
        }
      }
    });
    const want = (params.get("pack") || "contract").toLowerCase();
    const packId = PACK_FILES[want] ? want : "contract";
    await selectPack(packId);
  });

  window.__auditHelper = {
    connect: () => connectPrecedents(),
    getState: () => ({
      mode: state.mode,
      connected: state.connected,
      checked: [...state.checked],
      followUp: { ...state.followUp },
      corpusCount: state.corpusCount,
    }),
    selectPack,
  };
})();
