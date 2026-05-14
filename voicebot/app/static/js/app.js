const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let charts = {};
let categoriesCache = [];
let callsState = { offset: 0, limit: 50, total: 0 };
let currentDataset = null;
let datasetsList = [];

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} \u2192 ${r.status}`);
  return r.json();
}

function withDataset(url) {
  if (!currentDataset) return url;
  return url + (url.includes("?") ? "&" : "?") + "dataset=" + encodeURIComponent(currentDataset);
}

function setLoading(on) {
  const el = $("#loading");
  if (!el) return;
  el.style.display = on ? "block" : "none";
}

function tile(label, value, sub = "", cls = "") {
  return `<div class="tile ${cls}"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`;
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function loadOverview() {
  const o = await fetchJSON(withDataset("/api/overview"));
  if (!o.total_calls) {
    $("#tiles").innerHTML = `<div class="tile"><div class="value">No data</div><div class="sub">Run pull → parse → detect first.</div></div>`;
    return;
  }
  const failures = o.primary_failure_mode_distribution || {};
  const topFail = Object.entries(failures).sort((a, b) => b[1] - a[1]).filter(([k]) => k !== "none")[0];
  $("#tiles").innerHTML = [
    tile("Total calls", o.total_calls),
    tile("Calls with issues", `${o.calls_with_issues_pct}%`, `${o.calls_with_issues} of ${o.total_calls}`, o.calls_with_issues_pct > 50 ? "warn" : ""),
    tile("Avg issues / call", o.avg_issues_per_call),
    tile("Qualification done", `${o.qualification_completed_pct}%`, "", o.qualification_completed_pct > 70 ? "good" : "warn"),
    tile("Latency p50", o.latency_p50_sec ? `${o.latency_p50_sec}s` : "—"),
    tile("Latency p95", o.latency_p95_sec ? `${o.latency_p95_sec}s` : "—", "", o.latency_p95_sec > 3 ? "warn" : ""),
    tile("Top failure mode", topFail ? topFail[0] : "—", topFail ? `${topFail[1]} calls` : ""),
  ].join("");
}

function renderExamples(c) {
  return c.examples.map(ex => `
    <div class="example">
      <div class="meta"><span class="tag ${ex.source}">${ex.source}</span> sev: <span class="sev-${ex.severity}">${ex.severity}</span> · turn ${ex.turn_index ?? "—"} · <a href="#" data-call="${ex.call_sid}" class="open-call">${ex.call_sid.slice(0, 12)}…</a></div>
      ${ex.user_quote ? `<div class="quote">👤 ${escapeHtml(ex.user_quote)}</div>` : ""}
      ${ex.bot_quote ? `<div class="quote">🤖 ${escapeHtml(ex.bot_quote)}</div>` : ""}
      <div>${escapeHtml(ex.explanation || "")}</div>
      ${ex.suggested_fix ? `<div class="meta">💡 ${escapeHtml(ex.suggested_fix)}</div>` : ""}
    </div>
  `).join("");
}

async function loadCategories() {
  const data = await fetchJSON(withDataset("/api/issues/categories"));
  const cats = data.categories || [];
  categoriesCache = cats;

  const ctx = $("#cat-chart");
  if (charts.cat) charts.cat.destroy();
  charts.cat = new Chart(ctx, {
    type: "bar",
    data: {
      labels: cats.map(c => c.label),
      datasets: [{ label: "issues", data: cats.map(c => c.count), backgroundColor: "#0969da" }],
    },
    options: { indexAxis: "y", animation: false, plugins: { legend: { display: false } } },
  });

  const sevCtx = $("#sev-chart");
  if (charts.sev) charts.sev.destroy();
  charts.sev = new Chart(sevCtx, {
    type: "bar",
    data: {
      labels: cats.map(c => c.label),
      datasets: [
        { label: "high", data: cats.map(c => c.severity.high || 0), backgroundColor: "#cf222e" },
        { label: "medium", data: cats.map(c => c.severity.medium || 0), backgroundColor: "#bf8700" },
        { label: "low", data: cats.map(c => c.severity.low || 0), backgroundColor: "#8b949e" },
      ],
    },
    options: { indexAxis: "y", animation: false, scales: { x: { stacked: true }, y: { stacked: true } } },
  });

  // Drill-down list — examples are LAZY (rendered on first expand)
  $("#categories").innerHTML = cats.map((c, idx) => `
    <div class="cat-row" data-idx="${idx}">
      <div class="cat-header">
        <div>
          <span class="cat-name">${c.label}</span>
          <span class="meta" style="color:#656d76;font-size:11px;margin-left:8px;">${c.category}</span>
        </div>
        <div>
          <span class="cat-count">${c.count}</span>
          <span class="sev-high">${c.severity.high || 0}H</span>
          <span class="sev-medium">${c.severity.medium || 0}M</span>
          <span class="sev-low">${c.severity.low || 0}L</span>
        </div>
      </div>
      ${c.description ? `<div class="cat-desc">${escapeHtml(c.description)}</div>` : ""}
      <div class="cat-examples"></div>
    </div>
  `).join("");

  const sel = $("#f-category");
  sel.innerHTML = `<option value="">all</option>` + cats.map(c => `<option value="${c.category}">${c.label}</option>`).join("");
}

async function loadPersonas() {
  const data = await fetchJSON(withDataset("/api/issues/by-persona"));
  const t = $("#persona-table");
  t.innerHTML = `<thead><tr>
    <th>Persona</th><th>Calls</th><th>Avg issues</th><th>Top categories</th><th>Quality (good/med/poor)</th>
  </tr></thead><tbody>` + data.personas.map(p => {
    const top = Object.entries(p.top_categories).map(([k, v]) => `${k}: ${v}`).join(", ");
    const q = p.quality_distribution || {};
    return `<tr>
      <td><strong>${p.persona}</strong></td>
      <td>${p.calls}</td>
      <td>${p.avg_issues_per_call}</td>
      <td style="font-size:12px">${escapeHtml(top)}</td>
      <td><span class="q-good">${q.good || 0}</span> / <span class="q-mediocre">${q.mediocre || 0}</span> / <span class="q-poor">${q.poor || 0}</span></td>
    </tr>`;
  }).join("") + `</tbody>`;
}

function fmt(v, suffix = "") {
  if (v == null) return "—";
  return `${v}${suffix}`;
}

function fmtDuration(sec) {
  if (sec == null || isNaN(sec)) return "—";
  const s = Math.round(Number(sec));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60), r = s % 60;
  return `${m}m${r.toString().padStart(2, "0")}s`;
}

async function loadLatency() {
  const data = await fetchJSON(withDataset("/api/latency"));
  const pc = data.per_call || {};
  const pt = data.per_turn || {};
  const pcs = pc.stats || {}, pts = pt.stats || {};

  $("#latency-tiles").innerHTML = [
    tile("Calls (with latency)", pc.n_calls ?? 0),
    tile("Per-call avg p50", fmt(pcs.p50, "s")),
    tile("Per-call avg p95", fmt(pcs.p95, "s"), "", (pcs.p95 || 0) > 4 ? "warn" : ""),
    tile("Per-call avg max", fmt(pcs.max, "s")),
    tile("Turns measured", pt.n_turns ?? 0),
    tile("Per-turn p50", fmt(pts.p50, "s")),
    tile("Per-turn p95", fmt(pts.p95, "s"), "", (pts.p95 || 0) > 5 ? "warn" : ""),
    tile("Per-turn max", fmt(pts.max, "s"), "", (pts.max || 0) > 8 ? "warn" : ""),
  ].join("");

  // Per-call avg histogram
  if (charts.latCall) charts.latCall.destroy();
  charts.latCall = new Chart($("#lat-call-chart"), {
    type: "bar",
    data: {
      labels: (pc.histogram || []).map(b => b.bucket),
      datasets: [{
        label: "calls",
        data: (pc.histogram || []).map(b => b.count),
        backgroundColor: (pc.histogram || []).map(b => b.lo >= 4 ? "#cf222e" : b.lo >= 3 ? "#bf8700" : "#0969da"),
      }],
    },
    options: {
      animation: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.parsed.y} calls` } } },
      scales: { y: { beginAtZero: true, title: { display: true, text: "# calls" } } },
    },
  });

  // Per-turn histogram
  if (charts.latTurn) charts.latTurn.destroy();
  charts.latTurn = new Chart($("#lat-turn-chart"), {
    type: "bar",
    data: {
      labels: (pt.histogram || []).map(b => b.bucket),
      datasets: [{
        label: "turns",
        data: (pt.histogram || []).map(b => b.count),
        backgroundColor: (pt.histogram || []).map(b => b.lo >= 5 ? "#cf222e" : b.lo >= 3 ? "#bf8700" : "#1a7f37"),
      }],
    },
    options: {
      animation: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${c.parsed.y} turns` } } },
      scales: { y: { beginAtZero: true, title: { display: true, text: "# turns" } } },
    },
  });

  // Per-kind table
  const kinds = data.by_kind || [];
  $("#lat-kind-table").innerHTML = `<thead><tr>
    <th>Node / kind</th><th>n turns</th><th>mean</th><th>p50</th><th>p90</th><th>p95</th><th>max</th>
  </tr></thead><tbody>` + kinds.map(k => `<tr>
    <td><code style="font-size:12px">${escapeHtml(k.kind)}</code></td>
    <td>${k.n}</td>
    <td>${fmt(k.mean, "s")}</td>
    <td>${fmt(k.p50, "s")}</td>
    <td>${fmt(k.p90, "s")}</td>
    <td class="${(k.p95 || 0) > 5 ? "sev-high" : ""}">${fmt(k.p95, "s")}</td>
    <td class="${(k.max || 0) > 8 ? "sev-high" : ""}">${fmt(k.max, "s")}</td>
  </tr>`).join("") + `</tbody>`;

  // Outliers
  const out = data.outliers || [];
  const thr = data.outlier_threshold || {};
  $("#lat-outlier-meta").textContent =
    `Threshold: per-call avg \u2265 ${thr.per_call_avg_p95_sec ?? "—"}s (p95) OR any single turn \u2265 ${thr.max_turn_sec}s. ` +
    `Found ${data.outlier_count} outlier calls (showing top ${out.length}).`;
  $("#lat-outlier-table").innerHTML = `<thead><tr>
    <th>Call SID</th><th>Persona</th><th>Model</th><th>Duration</th><th>avg latency</th><th>p95 turn</th>
    <th>max turn</th><th># turns</th><th>quality</th><th>primary failure</th>
  </tr></thead><tbody>` + out.map(c => `
    <tr data-call="${c.call_sid}" class="open-call">
      <td>${c.call_sid.slice(0, 14)}…</td>
      <td>${escapeHtml(c.persona || "—")}</td>
      <td style="font-size:12px">${escapeHtml(c.model_variant || "—")}</td>
      <td>${fmtDuration(c.call_duration_sec)}</td>
      <td><strong>${fmt(c.avg_latency_sec, "s")}</strong></td>
      <td>${fmt(c.p95_latency_sec, "s")}</td>
      <td class="${(c.max_latency_sec || 0) >= 8 ? "sev-high" : ""}">${fmt(c.max_latency_sec, "s")}</td>
      <td>${c.turn_count_with_latency} / ${c.total_turns ?? "—"}</td>
      <td><span class="q-${c.overall_quality}">${c.overall_quality || "—"}</span></td>
      <td style="font-size:12px">${escapeHtml(c.primary_failure_mode || "—")}</td>
    </tr>
  `).join("") + `</tbody>`;
}

async function loadCalls(resetPage = true) {
  if (resetPage) callsState.offset = 0;
  const params = new URLSearchParams();
  const cat = $("#f-category").value, sev = $("#f-severity").value;
  const qual = $("#f-quality").value, mn = $("#f-min").value;
  const q = $("#f-search").value.trim();
  if (cat) params.set("category", cat);
  if (sev) params.set("severity", sev);
  if (qual) params.set("quality", qual);
  if (mn) params.set("min_issues", mn);
  if (q) params.set("search", q);
  params.set("limit", callsState.limit);
  params.set("offset", callsState.offset);

  setLoading(true);
  let data;
  try {
    data = await fetchJSON(withDataset(`/api/calls?${params.toString()}`));
  } finally {
    setLoading(false);
  }
  callsState.total = data.total;

  const t = $("#calls-table");
  t.innerHTML = `<thead><tr>
    <th>Call SID</th><th>Persona</th><th>Duration</th><th># issues</th><th>Primary failure</th><th>Quality</th><th>User turns</th><th>Summary</th>
  </tr></thead><tbody>` + data.calls.map(c => `
    <tr data-call="${c.call_sid}" class="open-call">
      <td>${c.call_sid.slice(0, 14)}…</td>
      <td>${c.persona || "—"}</td>
      <td>${fmtDuration(c.call_duration_sec)}</td>
      <td><strong>${c.issue_count}</strong></td>
      <td>${c.primary_failure_mode || "—"}</td>
      <td><span class="q-${c.overall_quality}">${c.overall_quality || "—"}</span></td>
      <td>${c.user_turns ?? "—"}</td>
      <td style="font-size:12px;max-width:400px">${escapeHtml(c.summary || "")}</td>
    </tr>
  `).join("") + `</tbody>`;

  renderPager();
}

function renderPager() {
  const start = callsState.total === 0 ? 0 : callsState.offset + 1;
  const end = Math.min(callsState.offset + callsState.limit, callsState.total);
  $("#pager-info").textContent = `${start}–${end} of ${callsState.total}`;
  $("#pager-prev").disabled = callsState.offset <= 0;
  $("#pager-next").disabled = end >= callsState.total;
}

async function openCallModal(callSid) {
  setLoading(true);
  let data;
  try {
    data = await fetchJSON(withDataset(`/api/calls/${callSid}`));
  } finally {
    setLoading(false);
  }
  const m = data.metadata, s = data.stats, sum = data.issues_summary;
  const issuesByTurn = data.issues_by_turn || {};
  const turnsHtml = data.turns.map(t => {
    const tIssues = issuesByTurn[String(t.index)] || [];
    const cls = t.is_filler ? "filler" : (t.role || "user");
    const lat = t.latency_sec != null ? ` · ${t.latency_sec}s` : "";
    const asr = t.asr_min_confidence != null ? ` · ASR min ${t.asr_min_confidence}` : "";
    return `<div class="turn ${cls}">
      <div class="turn-meta">[#${t.index}] ${t.role}${t.is_filler ? " (filler)" : ""}${lat}${asr}</div>
      <div>${escapeHtml(t.text)}</div>
      ${tIssues.length ? `<div class="turn-issues">${tIssues.map(i => `
        <div class="issue-row"><span class="tag ${i.source}">${i.source}</span> <strong>${i.category}</strong> <span class="sev-${i.severity}">[${i.severity}]</span> — ${escapeHtml(i.explanation || "")} ${i.suggested_fix ? `<br/><em>💡 ${escapeHtml(i.suggested_fix)}</em>` : ""}</div>
      `).join("")}</div>` : ""}
    </div>`;
  }).join("");

  const callIssues = (issuesByTurn["None"] || []).map(i => `
    <div class="turn-issues"><span class="tag ${i.source}">${i.source}</span> <strong>${i.category}</strong> <span class="sev-${i.severity}">[${i.severity}]</span> — ${escapeHtml(i.explanation || "")}</div>
  `).join("");

  $("#modal-body").innerHTML = `
    <h2>${callSid}</h2>
    <div style="margin-bottom:14px;font-size:13px;color:#57606a;">
      <strong>User ID:</strong> ${m.user_id ?? "—"} ·
      <strong>Counsellor ID:</strong> ${m.counsellor_id ?? "—"} ·
      <strong>Persona:</strong> ${m.persona_name || "—"} ·
      <strong>Cohort:</strong> ${m.cohort_identifer || "—"} ·
      <strong>Model:</strong> ${m.model_variant || "—"} ·
      <strong>Quality:</strong> <span class="q-${sum.overall_quality}">${sum.overall_quality || "—"}</span> ·
      <strong>Issues:</strong> ${sum.total} ·
      <strong>Primary failure:</strong> ${sum.primary_failure_mode || "—"} ·
      <strong>Qualified:</strong> ${sum.qualification_completed ? "yes" : "no"}
    </div>
    <div style="margin-bottom:14px;font-size:13px;">
      <strong>Duration:</strong> ${fmtDuration(m.call_duration_sec)} ·
      <strong>Latency:</strong> avg ${s.latency_avg_sec_reported ?? s.latency_avg_sec ?? "—"}s · max ${s.latency_max_sec ?? "—"}s ·
      <strong>ASR avg:</strong> ${s.asr_avg_overall ?? "—"} ·
      <strong>User turns:</strong> ${s.user_turns}
    </div>
    ${sum.call_summary ? `<div style="background:#f6f8fa;padding:10px;border-radius:6px;margin-bottom:14px;font-size:13px;"><strong>Summary:</strong> ${escapeHtml(sum.call_summary)}</div>` : ""}
    ${callIssues ? `<div style="margin-bottom:14px;"><h3 style="font-size:14px;margin:0 0 6px 0;">Call-level issues</h3>${callIssues}</div>` : ""}
    <h3 style="font-size:14px;margin:0 0 6px 0;">Conversation</h3>
    ${turnsHtml}
  `;
  $("#modal").classList.remove("hidden");
}

function renderDatasetTabs() {
  const nav = $("#dataset-tabs");
  if (datasetsList.length <= 1) {
    nav.style.display = "none";
    return;
  }
  nav.style.display = "flex";
  nav.innerHTML = datasetsList.map(d => `
    <button class="dataset-tab ${d.name === currentDataset ? "active" : ""}" data-name="${d.name}">
      ${escapeHtml(d.label)}
      <span class="dataset-tab-count">${d.call_count}</span>
    </button>
  `).join("");
  $$(".dataset-tab").forEach(btn => {
    btn.addEventListener("click", async () => {
      if (btn.dataset.name === currentDataset) return;
      currentDataset = btn.dataset.name;
      $("#export-link").href = withDataset("/api/export");
      renderDatasetTabs();
      await refreshAll();
    });
  });
}

async function loadDatasets() {
  const data = await fetchJSON("/api/datasets");
  datasetsList = data.datasets || [];
  if (!currentDataset && datasetsList.length) {
    currentDataset = datasetsList[0].name;
  }
  $("#export-link").href = withDataset("/api/export");
  renderDatasetTabs();
}

document.addEventListener("DOMContentLoaded", async () => {
  $("#modal-close").addEventListener("click", () => $("#modal").classList.add("hidden"));
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") $("#modal").classList.add("hidden"); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $("#modal").classList.add("hidden");
  });

  $("#apply-filters").addEventListener("click", () => loadCalls(true));
  $("#f-search").addEventListener("keydown", (e) => { if (e.key === "Enter") loadCalls(true); });

  $("#pager-prev").addEventListener("click", () => {
    callsState.offset = Math.max(0, callsState.offset - callsState.limit);
    loadCalls(false);
  });
  $("#pager-next").addEventListener("click", () => {
    callsState.offset += callsState.limit;
    loadCalls(false);
  });

  $("#reload-btn").addEventListener("click", async () => {
    setLoading(true);
    try {
      await fetch("/api/reload", { method: "POST" });
      await loadDatasets();
      await refreshAll();
    } finally {
      setLoading(false);
    }
  });

  // Delegated click handler: open-call links + lazy-render category examples
  document.body.addEventListener("click", (e) => {
    const openLink = e.target.closest(".open-call");
    if (openLink && openLink.dataset.call) {
      e.preventDefault();
      openCallModal(openLink.dataset.call);
      return;
    }
    const row = e.target.closest(".cat-row");
    if (row) {
      const idx = +row.dataset.idx;
      const exBox = row.querySelector(".cat-examples");
      if (exBox && !exBox.dataset.rendered && categoriesCache[idx]) {
        exBox.innerHTML = renderExamples(categoriesCache[idx]);
        exBox.dataset.rendered = "1";
      }
      row.classList.toggle("open");
    }
  });

  refreshAll();
});

async function refreshAll() {
  setLoading(true);
  try {
    if (!currentDataset) {
      await loadDatasets();
    }
    if (!currentDataset) {
      $("#tiles").innerHTML = `<div class="tile"><div class="value">No data</div><div class="sub">Run pull → parse → detect first.</div></div>`;
      return;
    }
    await Promise.all([loadOverview(), loadCategories(), loadPersonas(), loadLatency()]);
    await loadCalls(true);
  } finally {
    setLoading(false);
  }
}
