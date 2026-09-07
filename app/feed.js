/* F10 — 신규피드 / 검수큐 (vanilla)
 * Prefer ./data/demo.json; fallback ./data/hero-sample.json feed[]
 */
(() => {
  const $ = (s) => document.querySelector(s);
  const RTYPE = { finding: "지적", immunity: "면책", consult: "사전컨설팅" };
  const QLABEL = {
    "list-only": "목록만",
    list_only: "목록만",
    secured: "본문 확보",
    body: "본문 확보",
    matched: "근거 대조 완료",
  };

  let ITEMS = [];

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalizeFromDemo(arr) {
    return (arr || []).map((r) => ({
      id: r.id,
      title: r.title || r.summary || r.source_title || "(제목 없음)",
      record_type: r.record_type || "finding",
      source: r.source || r.org_name || "",
      org: r.org_name || r.org || "",
      quality: r.text_quality || r.quality || "list_only",
      review: !!r.review,
      added_at: r.added_at || r.collected_at || "",
      excerpt: r.excerpt || r.source_excerpt || r.summary || "",
      _synthetic: !!r._synthetic,
    }));
  }

  function normalizeFromHero(data) {
    if (Array.isArray(data.feed)) {
      return data.feed.map((r) => ({
        id: r.id,
        title: r.title,
        record_type: r.record_type || "finding",
        source: r.source || "",
        org: r.org || "",
        quality: r.quality || "list_only",
        review: !!r.review,
        added_at: r.added_at || "",
        excerpt: r.excerpt || "",
        _synthetic: !!r._synthetic,
      }));
    }
    return [];
  }

  function parseDate(s) {
    const t = Date.parse(s);
    return Number.isFinite(t) ? t : 0;
  }

  function qualityClass(q) {
    if (q === "matched") return "badge-matched";
    if (q === "secured" || q === "body") return "badge-secured";
    return "badge-list-only";
  }

  function card(item) {
    const rt = RTYPE[item.record_type] || item.record_type;
    const q = QLABEL[item.quality] || item.quality;
    const syn = item._synthetic
      ? '<span class="badge badge-synthetic">합성 예시</span>'
      : "";
    const review = item.review
      ? '<span class="badge badge-review-queue">검수큐</span>'
      : "";
    const when = item.added_at
      ? `<span class="feed-when">${escapeHtml(item.added_at)}</span>`
      : "";
    return `<article class="feed-card${item.review ? " is-review" : ""}${item._synthetic ? " is-synthetic" : ""}">
      <div class="badge-row">
        <span class="badge badge-kind">${escapeHtml(rt)}</span>
        <span class="badge ${qualityClass(item.quality)}">${escapeHtml(q)}</span>
        ${review}
        ${syn}
      </div>
      <h3 class="card-title">${escapeHtml(item.title)}</h3>
      <p class="card-meta">${escapeHtml([item.source, item.org].filter(Boolean).join(" · "))}</p>
      ${item.excerpt ? `<p class="card-excerpt">${escapeHtml(item.excerpt)}</p>` : ""}
      <div class="feed-foot">${when}</div>
    </article>`;
  }

  function render() {
    const onlyReview = $("#f-review-only").checked;
    let list = ITEMS.slice();
    if (onlyReview) {
      list = list.filter((x) => x.review);
    }
    list.sort((a, b) => parseDate(b.added_at) - parseDate(a.added_at));
    const el = $("#feedList");
    if (!list.length) {
      el.innerHTML = '<p class="placeholder">표시할 항목이 없습니다.</p>';
      return;
    }
    el.innerHTML = list.map(card).join("");
  }

  async function load() {
    const status = $("#feed-status");
    // demo.json may be large; try, then hero-sample
    try {
      const r = await fetch("./data/demo.json", { cache: "no-store" });
      if (r.ok) {
        const data = await r.json();
        const arr = Array.isArray(data) ? data : [];
        // Prefer review:true or recent added_at (last 30 days-ish: take top by date)
        const norm = normalizeFromDemo(arr);
        const withDate = norm.filter((x) => x.added_at || x.review);
        // Cap for UI
        withDate.sort((a, b) => {
          if (a.review !== b.review) return a.review ? -1 : 1;
          return parseDate(b.added_at) - parseDate(a.added_at);
        });
        ITEMS = withDate.slice(0, 80);
        if (ITEMS.length) {
          status.textContent = `demo.json · ${ITEMS.length}건`;
          render();
          return;
        }
      }
    } catch (e) {
      /* fallback */
    }

    const r2 = await fetch("./data/hero-sample.json", { cache: "no-store" });
    if (!r2.ok) throw new Error("feed data load failed");
    const hero = await r2.json();
    ITEMS = normalizeFromHero(hero);
    status.textContent = `hero-sample · ${ITEMS.length}건`;
    render();
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("#f-review-only").addEventListener("change", render);
    load().catch((err) => {
      console.error(err);
      $("#feedList").innerHTML =
        '<p class="placeholder">피드 데이터를 불러오지 못했습니다.</p>';
    });
  });
})();
