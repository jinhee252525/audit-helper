/* 감사 선례 도우미 — situation-memo hero prototype */
(() => {
  const QUALITY_LABEL = {
    "list-only": "목록만",
    secured: "본문 확보",
    matched: "근거 대조 완료",
  };

  const state = {
    data: null,
    connected: false,
    highlighted: new Set(),
    memoGrounds: [],
  };

  const $ = (sel, root = document) => root.querySelector(sel);

  async function loadSample() {
    const res = await fetch("./sample.json", { cache: "no-store" });
    if (!res.ok) throw new Error("sample.json 로드 실패");
    state.data = await res.json();
    hydrateStatic();
    renderMemoFields(false);
  }

  function hydrateStatic() {
    const d = state.data;
    $("#appTitle").textContent = d.appTitle;
    $("#tagline").textContent = d.tagline;
    $("#situationLabel").textContent = d.situation.label;
    $("#situationText").textContent = d.situation.text;
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

  function applyHighlights(text, spans, active) {
    if (!active || !spans || !spans.length) {
      return escapeHtml(text);
    }
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

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderEvidence() {
    const list = $("#evidenceList");
    list.classList.add("is-filled");
    list.innerHTML = "";

    state.data.evidence.forEach((ev) => {
      const card = document.createElement("article");
      card.className = `evidence-card ${qualityClass(ev.quality)}`;
      card.dataset.id = ev.id;
      if (state.highlighted.has(ev.id)) card.classList.add("highlighted");

      const badgeRow = document.createElement("div");
      badgeRow.className = "badge-row";
      const badge = document.createElement("span");
      badge.className = badgeClass(ev.quality);
      badge.textContent = QUALITY_LABEL[ev.quality] || ev.quality;
      badgeRow.append(badge);
      if (ev.kind === "immunity") {
        const extra = document.createElement("span");
        extra.className = "badge badge-secured";
        extra.textContent = "면책·컨설팅";
        badgeRow.append(extra);
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

      const canHighlight = ev.quality === "secured" || ev.quality === "matched";
      if (canHighlight) {
        const hl = document.createElement("button");
        hl.type = "button";
        hl.className = "btn-ghost" + (state.highlighted.has(ev.id) ? " is-on" : "");
        hl.textContent = state.highlighted.has(ev.id)
          ? "하이라이트 끄기"
          : "원문 하이라이트";
        hl.addEventListener("click", () => toggleHighlight(ev.id));
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
      add.addEventListener("click", () => addGroundToMemo(ev));
      actions.append(add);

      card.append(badgeRow, title, meta, excerpt, actions);
      list.append(card);
    });
  }

  function toggleHighlight(id) {
    if (state.highlighted.has(id)) state.highlighted.delete(id);
    else state.highlighted.add(id);
    renderEvidence();
  }

  function addGroundToMemo(ev) {
    if (!ev.canAddToMemo || ev.quality === "list-only") return;
    const ta = $("#memo-grounds");
    if (!ta) return;
    const line = `· [${QUALITY_LABEL[ev.quality]}] ${ev.title} — ${ev.excerpt}`;
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
    renderEvidence();
    renderDistance();
    renderMemoFields(true);
    const cta = $("#ctaConnect");
    cta.textContent = "선례 연결됨";
    cta.classList.add("is-done");
    cta.disabled = true;
    $("#btnCopyMemo").disabled = false;
    $("#copyStatus").textContent = "초안이 채워졌습니다. 필요 시 수정 후 복사하세요.";
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
      // fallback
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
        `<p class="placeholder">sample.json을 불러오지 못했습니다. 로컬 서버로 열어 주세요.</p>`;
    }
  });

  // expose for screenshot / debug
  window.__auditHelper = {
    connect: connectPrecedents,
    getState: () => ({ ...state, connected: state.connected }),
  };
})();
