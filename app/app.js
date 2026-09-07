/* 감사 선례 도우미 — MVP hero (situation → evidence → distance → memo)
 * data: ./data/hero-sample.json
 * deep-link: ?view=search → search.html
 */
(() => {
  const params = new URLSearchParams(location.search);
  if (params.get("view") === "search") {
    params.delete("view");
    const qs = params.toString();
    location.replace("./search.html" + (qs ? "?" + qs : ""));
    return;
  }

  const QUALITY_LABEL = {
    "list-only": "목록만",
    secured: "본문 확보",
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
    connected: false,
    highlighted: new Set(),
    memoGrounds: [],
    selectedId: null,
  };

  const $ = (sel, rootEl = document) => rootEl.querySelector(sel);

  async function loadSample() {
    const res = await fetch("./data/hero-sample.json", { cache: "no-store" });
    if (!res.ok) throw new Error("hero-sample.json 로드 실패");
    state.data = await res.json();
    hydrateStatic();
    renderMemoFields(false);
  }

  function hydrateStatic() {
    const d = state.data;
    $("#appTitle").textContent = d.appTitle;
    $("#tagline").textContent = d.tagline;
    $("#situationLabel").textContent = d.situation.label;
    const input = $("#situationInput");
    input.value = d.situation.text || "";
    $("#situationDomain").textContent = d.situation.domain;
    $("#situationWorkType").textContent = d.situation.workType;
  }

  function renderMemoFields(fillDraft) {
    const form = $("#memoForm");
    form.innerHTML = "";
    const fields = state.data.memo.fields;
    const draft = state.data.memo.draft;
    fields.forEach((f) => {
      const wrap = document.createElement("div");
      wrap.className = "field";
      const label = document.createElement("label");
      label.htmlFor = `memo-${f.id}`;
      label.textContent = f.label;
      const ta = document.createElement("textarea");
      ta.id = `memo-${f.id}`;
      ta.name = f.id;
      ta.rows = f.id === "grounds" || f.id === "diff" ? 3 : 2;
      ta.placeholder = f.placeholder;
      if (fillDraft && draft[f.id]) ta.value = draft[f.id];
      wrap.append(label, ta);
      form.append(wrap);
    });
    $("#btnCopyMemo").disabled = !fillDraft;
  }

  function qualityClass(q) {
    return `quality-${q}`;
  }

  function badgeClass(q) {
    return `badge badge-${q}`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
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

  function byId(id) {
    return (state.data.evidence || []).find((e) => e.id === id);
  }

  function renderEvidence() {
    const list = $("#evidenceList");
    list.classList.add("is-filled");
    list.innerHTML = "";

    // Main lane: findings only; related immunity/consult in F8 panel.
    const showInMain = (state.data.evidence || []).filter((ev) => {
      if (ev.kind === "immunity" || ev.kind === "consult") return false;
      return true;
    });

    showInMain.forEach((ev) => {
      list.appendChild(buildEvidenceCard(ev, { selectable: true }));
    });

    renderRelated();
  }

  function buildEvidenceCard(ev, opts = {}) {
    const card = document.createElement("article");
    card.className = `evidence-card ${qualityClass(ev.quality)}`;
    card.dataset.id = ev.id;
    if (state.highlighted.has(ev.id)) card.classList.add("highlighted");
    if (opts.selectable && state.selectedId === ev.id) card.classList.add("is-selected");
    if (ev._synthetic) card.classList.add("is-synthetic");

    const badgeRow = document.createElement("div");
    badgeRow.className = "badge-row";

    const qBadge = document.createElement("span");
    qBadge.className = badgeClass(ev.quality);
    qBadge.textContent = QUALITY_LABEL[ev.quality] || ev.quality;
    badgeRow.append(qBadge);

    const trust = document.createElement("span");
    const tKey = ev.trust === "high" ? "high" : "review";
    trust.className = `badge badge-trust-${tKey}`;
    trust.textContent = TRUST_LABEL[tKey];
    badgeRow.append(trust);

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
    title.textContent = ev.title;

    const meta = document.createElement("p");
    meta.className = "card-meta";
    meta.textContent = `${ev.source} · ${ev.org}`;

    const excerpt = document.createElement("p");
    excerpt.className = "card-excerpt";
    excerpt.innerHTML = applyHighlights(
      ev.excerpt,
      ev.highlightSpans,
      state.highlighted.has(ev.id)
    );

    const actions = document.createElement("div");
    actions.className = "card-actions";

    if (opts.selectable) {
      const sel = document.createElement("button");
      sel.type = "button";
      sel.className = "btn-ghost" + (state.selectedId === ev.id ? " is-on" : "");
      sel.textContent = state.selectedId === ev.id ? "선택됨 · 관련 보기" : "선택 · 관련 보기";
      sel.addEventListener("click", (e) => {
        e.stopPropagation();
        selectFinding(ev.id);
      });
      actions.append(sel);
    }

    const canHighlight = ev.quality === "secured" || ev.quality === "matched";
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

    const add = document.createElement("button");
    add.type = "button";
    add.className = "btn-add";
    add.textContent = "메모에 근거 추가";
    const allowAdd = ev.canAddToMemo && ev.quality !== "list-only";
    add.disabled = !allowAdd;
    if (!allowAdd) {
      add.title = "목록만 — 본문 미확보로 근거 추가 불가";
    }
    add.addEventListener("click", (e) => {
      e.stopPropagation();
      addGroundToMemo(ev);
    });
    actions.append(add);

    card.append(badgeRow, title, meta, excerpt, actions);

    if (opts.selectable) {
      card.addEventListener("click", () => selectFinding(ev.id));
      card.setAttribute("role", "button");
      card.tabIndex = 0;
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          selectFinding(ev.id);
        }
      });
    }

    return card;
  }

  function selectFinding(id) {
    state.selectedId = state.selectedId === id ? null : id;
    renderEvidence();
  }

  function renderRelated() {
    const lane = $("#relatedLane");
    const list = $("#relatedList");
    list.innerHTML = "";
    if (!state.selectedId) {
      lane.hidden = true;
      return;
    }
    const selected = byId(state.selectedId);
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
      list.appendChild(buildEvidenceCard(ev, { selectable: false }));
    });
  }

  function toggleHighlight(id) {
    if (state.highlighted.has(id)) state.highlighted.delete(id);
    else state.highlighted.add(id);
    renderEvidence();
  }

  function addGroundToMemo(ev) {
    // Hard rule: list-only must NOT fill grounds as if matched
    if (!ev.canAddToMemo || ev.quality === "list-only") {
      $("#copyStatus").textContent = "목록만 건은 근거로 추가할 수 없습니다.";
      return;
    }
    const ta = $("#memo-grounds");
    if (!ta) return;
    const syn = ev._synthetic ? " [합성 예시]" : "";
    const line = `· [${QUALITY_LABEL[ev.quality]}] ${ev.title}${syn} — ${ev.excerpt}`;
    if (state.memoGrounds.includes(ev.id)) return;
    state.memoGrounds.push(ev.id);
    ta.value = ta.value ? `${ta.value}\n${line}` : line;
    $("#copyStatus").textContent = "근거가 메모에 추가되었습니다.";
  }

  function renderDistance() {
    const panel = $("#distancePanel");
    panel.classList.add("is-filled");
    const d = state.data.distance;
    panel.innerHTML = `
      <div class="distance-row">
        <span class="distance-chip">같음</span>
        <p class="distance-body">${escapeHtml(d.same)}</p>
      </div>
      <div class="distance-row">
        <span class="distance-chip">다름</span>
        <p class="distance-body">${escapeHtml(d.diff)}</p>
      </div>
      <div class="distance-row">
        <span class="distance-chip">확인</span>
        <p class="distance-body">${escapeHtml(d.check)}</p>
      </div>
      <div class="tip-card">
        <h4>한 줄 정리</h4>
        <p>${escapeHtml(d.summary)}</p>
      </div>
    `;
  }

  function connectPrecedents() {
    if (!state.data || state.connected) return;
    state.connected = true;
    // Sync situation text into overview draft if user edited
    const sit = ($("#situationInput").value || "").trim();
    if (sit && state.data.memo && state.data.memo.draft) {
      state.data.memo.draft.overview = sit;
    }
    renderEvidence();
    renderDistance();
    renderMemoFields(true);
    // Ensure grounds draft does not include list-only as matched
    const grounds = $("#memo-grounds");
    if (grounds && /목록만/.test(grounds.value)) {
      /* leave as-is if draft already correct from sample */
    }
    const cta = $("#ctaConnect");
    cta.textContent = "선례 연결됨";
    cta.classList.add("is-done");
    cta.disabled = true;
    $("#btnCopyMemo").disabled = false;
    $("#copyStatus").textContent =
      "초안이 채워졌습니다. 목록만 건은 근거에 넣지 마세요. 필요 시 수정 후 복사하세요.";
  }

  async function copyMemo() {
    const fields = state.data.memo.fields;
    const lines = fields.map((f) => {
      const val = ($(`#memo-${f.id}`) || {}).value || "";
      return `【${f.label}】\n${val.trim()}`;
    });
    const text = lines.join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      $("#copyStatus").textContent = "클립보드에 복사했습니다.";
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
      $("#copyStatus").textContent = "클립보드에 복사했습니다.";
    }
  }

  function bind() {
    $("#ctaConnect").addEventListener("click", connectPrecedents);
    $("#btnCopyMemo").addEventListener("click", copyMemo);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    bind();
    try {
      await loadSample();
    } catch (err) {
      console.error(err);
      $("#evidenceList").innerHTML =
        `<p class="placeholder">hero-sample.json을 불러오지 못했습니다. 로컬 정적 서버로 app/을 열어 주세요.</p>`;
    }
  });

  window.__auditHelper = {
    connect: connectPrecedents,
    getState: () => ({ ...state, connected: state.connected }),
  };
})();
