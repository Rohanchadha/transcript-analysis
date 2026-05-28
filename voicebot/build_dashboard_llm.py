"""Build the LLM-classified theme dashboard. Fully data-driven by DOMAINS list."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10_000_000)

ROOT = Path(r"C:\Users\rohan.chadha")
HERE = Path(__file__).parent
DATA_DIR = HERE / "bot_query_analysis" / "llm"
OUT_HTML = HERE / "bot_query_analysis" / "dashboard_llm.html"

# (csv_filename, domain_id, display_label, color_hex)
DOMAINS = [
    ("law-bot-transcripts.csv", "law", "Law", "#2563eb"),
    ("design-bot-transcripts.csv", "design", "Design", "#db2777"),
    ("bba-bot-transcripts.csv", "bba", "BBA", "#16a34a"),
    ("bsc-bot-transcripts.csv", "bsc", "B.Sc", "#f59e0b"),
    ("llm-bot-transcripts.csv", "llm", "LLM", "#a855f7"),
    ("mba-bot-transcripts.csv", "mba", "MBA", "#06b6d4"),
    ("ba-bot-transcripts.csv", "ba", "B.A.", "#ef4444"),
    ("bed-bot-transcripts.csv", "bed", "B.Ed", "#84cc16"),
]


def load_call_stats(csv_path: Path) -> dict:
    n_total = 0
    n_no_user = 0
    n_silence_term = 0
    lat = []
    cohorts: Counter = Counter()
    if not csv_path.exists():
        return {"n_total": 0, "n_no_user": 0, "n_silence_term": 0,
                "avg_lat": None, "cohorts": []}
    with csv_path.open(encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            try:
                info = json.loads(row.get("info") or "")
            except Exception:
                continue
            n_total += 1
            cohorts[info.get("cohort_identifer") or info.get("cohort_identifier") or "unknown"] += 1
            if info.get("avgLatencySec") is not None:
                try:
                    lat.append(float(info["avgLatencySec"]))
                except Exception:
                    pass
            try:
                turns = json.loads(info.get("transcript") or "[]")
            except Exception:
                turns = []
            if not any(t.get("role") == "user" and (t.get("content") or "").strip()
                       for t in turns):
                n_no_user += 1
            try:
                v2 = json.loads(info.get("transcriptV2") or "[]")
            except Exception:
                v2 = []
            if any(t.get("kind") == "silence_timeout_terminal" for t in v2):
                n_silence_term += 1
    return {
        "n_total": n_total,
        "n_no_user": n_no_user,
        "n_silence_term": n_silence_term,
        "avg_lat": round(sum(lat) / len(lat), 2) if lat else None,
        "cohorts": cohorts.most_common(),
    }


def aggregate_domain(domain_id: str) -> dict:
    themes_path = DATA_DIR / f"{domain_id}_themes.json"
    assign_path = DATA_DIR / f"{domain_id}_assignments.json"
    if not themes_path.exists() or not assign_path.exists():
        return {"themes": [], "n_calls_with_extraction": 0}
    themes = json.loads(themes_path.read_text(encoding="utf-8")).get("themes", [])
    calls = json.loads(assign_path.read_text(encoding="utf-8")).get("calls", [])

    theme_calls: dict[str, set] = defaultdict(set)
    theme_quotes: dict[str, list[dict]] = defaultdict(list)
    for c in calls:
        sid = c.get("call_sid")
        cohort = c.get("cohort")
        for it in c.get("items", []):
            tid = it.get("theme") or "other"
            theme_calls[tid].add(sid)
            theme_quotes[tid].append({
                "quote": it.get("quote", ""),
                "nuance": it.get("nuance", ""),
                "kind": it.get("kind", ""),
                "cohort": cohort,
            })

    enriched = []
    for t in themes:
        tid = t["id"]
        enriched.append({**t, "call_count": len(theme_calls.get(tid, set())),
                         "quotes": theme_quotes.get(tid, [])})
    if "other" in theme_calls:
        enriched.append({
            "id": "other", "title": "Other / unmatched nuances",
            "description": "Nuances that didn't fit any synthesized theme.",
            "kind": "other",
            "call_count": len(theme_calls["other"]),
            "quotes": theme_quotes["other"], "sample_quotes": [],
        })
    enriched.sort(key=lambda x: -x["call_count"])

    # Per-call queries (only actual student questions — drop vague stuff).
    theme_titles = {t["id"]: t["title"] for t in themes}
    theme_titles["other"] = "Other / unmatched"
    query_calls = []
    for c in calls:
        qs = [
            {
                "quote": it.get("quote", ""),
                "nuance": it.get("nuance", ""),
                "theme": it.get("theme") or "other",
                "theme_title": theme_titles.get(it.get("theme") or "other", "—"),
            }
            for it in c.get("items", [])
            if (it.get("kind") or "").lower() == "question"
            and (it.get("quote") or "").strip()
        ]
        if qs:
            query_calls.append({
                "call_sid": c.get("call_sid"),
                "cohort": c.get("cohort"),
                "queries": qs,
            })
    # Sort: most queries first
    query_calls.sort(key=lambda c: -len(c["queries"]))

    return {
        "themes": enriched,
        "n_calls_with_extraction": len(calls),
        "query_calls": query_calls,
    }


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Voice Bot — Nuanced Student Query Themes</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root { --bg:#0b1220; --card:#161e2e; --card2:#1e2942; --text:#f1f5f9;
          --muted:#94a3b8; --border:#2a3352; __DOMAIN_VARS__ }
  * { box-sizing: border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background:var(--bg); color:var(--text); padding:24px; }
  h1 { margin:0 0 4px; font-size:24px; }
  .lede { color:var(--muted); margin-bottom:20px; font-size:14px; }
  .stats { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:12px; margin-bottom:24px; }
  .stat { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:14px; }
  .stat h3 { margin:0 0 10px; font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; }
  .stat h3 .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:middle; }
  .stat .num { font-size:22px; font-weight:700; }
  .stat .lbl { font-size:11px; color:var(--muted); }
  .modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,.7); display:none; z-index:1000; align-items:flex-start; justify-content:center; padding:40px 16px; overflow-y:auto; }
  .modal-backdrop.open { display:flex; }
  .modal { background:var(--card); border:1px solid var(--border); border-radius:10px; max-width:820px; width:100%; padding:20px 22px; box-shadow:0 20px 40px rgba(0,0,0,.5); }
  .modal-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:14px; padding-bottom:10px; border-bottom:1px solid var(--border); }
  .modal-head h3 { margin:0; font-size:16px; line-height:1.35; }
  .modal-close { background:transparent; border:1px solid var(--border); color:var(--text); border-radius:6px; padding:4px 10px; cursor:pointer; font-size:13px; }
  .modal-close:hover { background:var(--card2); }
  .modal ul { margin:0; padding-left:18px; max-height:60vh; overflow-y:auto; }
  .modal li { font-size:13px; line-height:1.55; margin-bottom:10px; color:#e2e8f0; }
  .modal li .nuance { color:var(--muted); font-size:11.5px; display:block; margin-top:3px; font-style:italic; }
  .quote-btn { background:var(--card2); color:var(--text); border:1px solid var(--border); padding:6px 12px; font-size:12px; border-radius:6px; cursor:pointer; font-weight:500; }
  .quote-btn:hover { background:#293a5e; border-color:#475569; }
  .tabs { display:flex; gap:6px; margin-bottom:16px; flex-wrap:wrap; }
  .tabs button { background:var(--card); color:var(--text); border:1px solid var(--border);
                 padding:8px 14px; border-radius:6px; cursor:pointer; font-size:14px; font-weight:500; }
  .tabs button.active { color:#fff; border-color:transparent; }
  .panel { display:none; }
  .panel.active { display:block; }
  .theme-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(380px, 1fr)); gap:14px; }
  .theme-card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:14px; border-left:4px solid var(--border); }
  .theme-card .head { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; margin-bottom:6px; }
  .theme-card h3 { margin:0; font-size:15px; line-height:1.3; }
  .theme-card .count { background:var(--card2); border-radius:14px; padding:3px 10px; font-size:12px;
                       color:#fff; white-space:nowrap; font-weight:600; }
  .theme-card .desc { color:var(--muted); font-size:12.5px; margin-bottom:10px; line-height:1.45; }
  .kind-pill { display:inline-block; font-size:10px; padding:2px 7px; border-radius:10px;
               background:#0f172a; border:1px solid var(--border); color:var(--muted);
               margin-bottom:8px; text-transform:uppercase; letter-spacing:.4px; }
  .quotes { border-top:1px solid var(--border); padding-top:8px; margin-top:6px; }
  .quotes details summary { cursor:pointer; font-size:12px; color:var(--muted); user-select:none; }
  .quotes ul { margin:8px 0 0; padding-left:18px; }
  .quotes li { font-size:12.5px; line-height:1.5; margin-bottom:6px; color:#e2e8f0; }
  .quotes li .nuance { color:var(--muted); font-size:11px; display:block; margin-top:2px; font-style:italic; }
  .chart-wrap { background:var(--card); border:1px solid var(--border); border-radius:8px;
                padding:16px; margin-bottom:18px; }
  .chart-wrap h2 { margin:0 0 12px; font-size:18px; }
</style>
</head>
<body>
  <h1>Voice Bot — Nuanced Student Query Themes</h1>
  <div class="lede">LLM-extracted concerns, questions and signals from real bot calls. Themes are domain-specific and were synthesized to be <b>actionable</b>, not generic. Click a theme card to expand verbatim student quotes.</div>

  <div class="stats" id="stats"></div>
  <div class="tabs" id="tabs"></div>
  <div id="panels"></div>

  <!-- Shared quotes modal -->
  <div id="quotes-modal" class="modal-backdrop" role="dialog" aria-modal="true">
    <div class="modal">
      <div class="modal-head">
        <h3 id="qm-title"></h3>
        <button class="modal-close" id="qm-close" type="button">Close ✕</button>
      </div>
      <ul id="qm-list"></ul>
    </div>
  </div>

<script>
const DATA = __DATA__;
const DOMAINS = __DOMAINS__;   // [{id, label, color}, ...]

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function fmtPct(num, total) { return total ? Math.round(num*100/total) + '%' : '—'; }

// ---- Stat cards ----
const statsHost = document.getElementById('stats');
DOMAINS.forEach(d => {
  const s = DATA.stats[d.id] || {};
  const el = document.createElement('div');
  el.className = 'stat';
  el.innerHTML = `
    <h3><span class="dot" style="background:${d.color}"></span>${escapeHtml(d.label)}</h3>
    <div><div class="num">${s.n_total || 0}</div><div class="lbl">total calls</div></div>`;
  statsHost.appendChild(el);
});

// ---- Tabs + panels ----
const tabsHost = document.getElementById('tabs');
const panelsHost = document.getElementById('panels');

function makeTab(label, key, color, active) {
  const b = document.createElement('button');
  b.textContent = label;
  b.dataset.tab = key;
  if (active) { b.classList.add('active'); b.style.background = color; }
  b.onclick = () => {
    document.querySelectorAll('#tabs button').forEach(x => {
      x.classList.remove('active');
      x.style.background = '';
    });
    b.classList.add('active');
    b.style.background = color;
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.getElementById('panel-' + key).classList.add('active');
  };
  return b;
}

// Student queries first + active by default
tabsHost.appendChild(makeTab('Student queries', 'queries', '#0ea5e9', true));
DOMAINS.forEach((d) => {
  tabsHost.appendChild(makeTab(d.label + ' themes', d.id, d.color, false));
});
tabsHost.appendChild(makeTab('Compare', 'compare', '#475569', false));

DOMAINS.forEach((d, i) => {
  const panel = document.createElement('div');
  panel.id = 'panel-' + d.id;
  panel.className = 'panel';
  const total = (DATA.stats[d.id] || {}).n_total || 0;
  const themes = (DATA.domains[d.id] || {}).themes || [];
  const grid = document.createElement('div');
  grid.className = 'theme-grid';
  themes.forEach(t => {
    const card = document.createElement('div');
    card.className = 'theme-card';
    card.style.borderLeftColor = d.color;
    const pct = total ? Math.round(t.call_count*100/total) : 0;
    card.innerHTML = `
      <div class="head">
        <h3>${escapeHtml(t.title)}</h3>
        <span class="count" style="background:${d.color}">${t.call_count} • ${pct}%</span>
      </div>
      ${t.kind ? `<div class="kind-pill">${escapeHtml(t.kind)}</div>` : ''}
      <div class="desc">${escapeHtml(t.description || '')}</div>
      <div class="quotes">
        <button type="button" class="quote-btn">${(t.quotes||[]).length} verbatim quote${(t.quotes||[]).length===1?'':'s'} →</button>
      </div>`;
    const qBtn = card.querySelector('.quote-btn');
    if (qBtn) qBtn.onclick = () => openQuotesModal(t.title, t.quotes || []);
    grid.appendChild(card);
  });
  panel.appendChild(grid);
  panelsHost.appendChild(panel);
});

// Compare panel
const cmpPanel = document.createElement('div');
cmpPanel.id = 'panel-compare';
cmpPanel.className = 'panel';
cmpPanel.innerHTML = `
  <div class="chart-wrap">
    <h2>Top themes per domain (top 10 each)</h2>
    <div id="cmp-hosts"></div>
  </div>
  <div class="chart-wrap">
    <h2>Cross-cutting signals across domains</h2>
    <div id="cross-cutting" style="font-size:13px; color:#cbd5e1; line-height:1.6;"></div>
  </div>`;
panelsHost.appendChild(cmpPanel);

const cmpHost = document.getElementById('cmp-hosts');
DOMAINS.forEach(d => {
  const wrap = document.createElement('div');
  wrap.style.marginBottom = '24px';
  const h = document.createElement('h3');
  h.textContent = d.label;
  h.style.cssText = `margin:6px 0; font-size:14px; color:${d.color};`;
  wrap.appendChild(h);
  const cv = document.createElement('canvas');
  const themes = ((DATA.domains[d.id] || {}).themes || []).filter(t => t.id !== 'other').slice(0, 10);
  cv.height = themes.length * 26 + 60;
  wrap.appendChild(cv);
  cmpHost.appendChild(wrap);
  const total = (DATA.stats[d.id] || {}).n_total || 1;
  new Chart(cv.getContext('2d'), {
    type: 'bar',
    data: {
      labels: themes.map(t => t.title.length > 65 ? t.title.slice(0,62)+'…' : t.title),
      datasets: [{
        data: themes.map(t => Math.round(t.call_count*1000/total)/10),
        backgroundColor: d.color,
      }],
    },
    options: {
      indexAxis: 'y',
      maintainAspectRatio: false,
      plugins: { legend: { display:false }, tooltip: { callbacks: { label: c => c.parsed.x + '% of calls' }}},
      scales: {
        x: { ticks: { color:'#94a3b8', callback:v=>v+'%' }, grid:{ color:'#334155' }},
        y: { ticks: { color:'#e2e8f0', font:{size:11} }, grid:{ color:'#1e293b' }},
      },
    },
  });
});

// ---- Queries panel (all real student questions across calls) ----
const qPanel = document.createElement('div');
qPanel.id = 'panel-queries';
qPanel.className = 'panel active';

// ---- Quotes modal ----
function openQuotesModal(title, quotes) {
  document.getElementById('qm-title').textContent = `${title} — ${quotes.length} quote${quotes.length===1?'':'s'}`;
  document.getElementById('qm-list').innerHTML = quotes.length
    ? quotes.map(q => `<li>"${escapeHtml(q.quote||'')}"<span class="nuance">→ ${escapeHtml(q.nuance||'')}${q.cohort ? ' · ' + escapeHtml(q.cohort) : ''}</span></li>`).join('')
    : '<li style="color:#94a3b8;font-style:italic;">No quotes available for this theme.</li>';
  document.getElementById('quotes-modal').classList.add('open');
}
document.getElementById('qm-close').onclick = () => document.getElementById('quotes-modal').classList.remove('open');
document.getElementById('quotes-modal').addEventListener('click', (e) => {
  if (e.target.id === 'quotes-modal') e.currentTarget.classList.remove('open');
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') document.getElementById('quotes-modal').classList.remove('open');
});
qPanel.innerHTML = `
  <div class="chart-wrap">
    <h2>Student queries (kind = question) — grouped by call</h2>
    <div style="display:flex; flex-wrap:wrap; gap:10px; margin-bottom:14px; align-items:center;">
      <div>
        <label style="font-size:12px; color:#94a3b8; margin-right:6px;">Domain:</label>
        <select id="q-domain" style="background:#0f172a; color:#fff; border:1px solid #334155; padding:6px 10px; border-radius:6px;"></select>
      </div>
      <div style="flex:1; min-width:240px;">
        <input id="q-search" placeholder="Search queries, themes, or call sid…" style="width:100%; background:#0f172a; color:#fff; border:1px solid #334155; padding:7px 10px; border-radius:6px;" />
      </div>
      <div>
        <label style="font-size:12px; color:#94a3b8; margin-right:6px;">Theme:</label>
        <select id="q-theme" style="background:#0f172a; color:#fff; border:1px solid #334155; padding:6px 10px; border-radius:6px; max-width:340px;"></select>
      </div>
      <div id="q-meta" style="font-size:12px; color:#94a3b8;"></div>
    </div>
    <div id="q-list"></div>
  </div>`;
panelsHost.appendChild(qPanel);

const qDomainSel = qPanel.querySelector('#q-domain');
const qThemeSel = qPanel.querySelector('#q-theme');
const qSearch = qPanel.querySelector('#q-search');
const qList = qPanel.querySelector('#q-list');
const qMeta = qPanel.querySelector('#q-meta');

DOMAINS.forEach(d => {
  const o = document.createElement('option');
  o.value = d.id; o.textContent = d.label;
  qDomainSel.appendChild(o);
});

function renderQueries() {
  const did = qDomainSel.value;
  const color = (DOMAINS.find(d => d.id === did) || {}).color || '#0ea5e9';
  const calls = ((DATA.domains[did] || {}).query_calls) || [];
  const themeFilter = qThemeSel.value;
  const search = (qSearch.value || '').toLowerCase().trim();

  // rebuild theme dropdown when domain changes
  if (qThemeSel.dataset.domain !== did) {
    qThemeSel.innerHTML = '';
    const all = document.createElement('option');
    all.value = ''; all.textContent = 'All themes';
    qThemeSel.appendChild(all);
    const tset = new Map();
    calls.forEach(c => c.queries.forEach(q => {
      if (!tset.has(q.theme)) tset.set(q.theme, q.theme_title);
    }));
    [...tset.entries()].sort((a,b) => a[1].localeCompare(b[1])).forEach(([id, title]) => {
      const o = document.createElement('option');
      o.value = id; o.textContent = title;
      qThemeSel.appendChild(o);
    });
    qThemeSel.dataset.domain = did;
  }

  let totalQ = 0, shownQ = 0, shownCalls = 0;
  const parts = [];
  calls.forEach(c => {
    const filtered = c.queries.filter(q => {
      if (themeFilter && q.theme !== themeFilter) return false;
      if (search) {
        const hay = (q.quote + ' ' + q.theme_title + ' ' + (c.call_sid||'')).toLowerCase();
        if (!hay.includes(search)) return false;
      }
      return true;
    });
    totalQ += c.queries.length;
    if (!filtered.length) return;
    shownQ += filtered.length;
    shownCalls += 1;
    parts.push(`
      <div style="background:#161e2e; border:1px solid #2a3352; border-radius:8px; padding:12px 14px; margin-bottom:10px; border-left:4px solid ${color};">
        <div style="display:flex; justify-content:space-between; font-size:12px; color:#94a3b8; margin-bottom:8px;">
          <div>Call <code style="color:#e2e8f0;">${escapeHtml(c.call_sid || '—')}</code> · cohort: ${escapeHtml(c.cohort || '—')}</div>
          <div>${filtered.length} quer${filtered.length === 1 ? 'y' : 'ies'}</div>
        </div>
        <ul style="margin:0; padding-left:18px;">
          ${filtered.map(q => `
            <li style="font-size:13px; line-height:1.55; margin-bottom:8px; color:#e2e8f0;">
              "${escapeHtml(q.quote)}"
              <div style="margin-top:3px;">
                <span style="display:inline-block; font-size:10px; padding:2px 8px; border-radius:10px; background:${color}; color:#fff; font-weight:600;">${escapeHtml(q.theme_title)}</span>
                ${q.nuance ? `<span style="font-size:11px; color:#94a3b8; margin-left:6px; font-style:italic;">${escapeHtml(q.nuance)}</span>` : ''}
              </div>
            </li>`).join('')}
        </ul>
      </div>`);
  });
  qMeta.textContent = `${shownQ} of ${totalQ} queries · ${shownCalls} of ${calls.length} calls`;
  qList.innerHTML = parts.join('') || '<div style="color:#94a3b8; padding:20px; text-align:center;">No queries match.</div>';
}

qDomainSel.onchange = () => { qThemeSel.dataset.domain = ''; renderQueries(); };
qThemeSel.onchange = renderQueries;
qSearch.oninput = renderQueries;
renderQueries();

// Cross-cutting heuristic
const KEYWORDS = [
  ['WhatsApp / async info preference', /whatsapp|sms/i],
  ['Family / parent decision-making', /family|parent|consult|discuss before|deciding on behalf|husband|wife|child/i],
  ['Working professional / job-friendly mode', /working|job|online|distance|part-time|part time/i],
  ['Government college preference', /government|govt|sarkari/i],
  ['Fee anxiety / scholarship / affordability', /fee|afford|financ|scholar|cost|loan/i],
  ['Specific city / location constraint', /city|state|delhi|mumbai|bangalore|kolkata|pune|location|out of|district|near/i],
  ['Doubts about future / ROI', /future|prospect|career|return|salary|opportunit/i],
  ['"Is this a bot? / human please"', /bot|robot|human|computer|authentic/i],
  ['Already disengaged / not interested', /disinterest|not interested|not ready|not engage|cancel/i],
  ['Language barrier (Hindi / regional)', /hindi|kannada|tamil|language|english/i],
  ['Callback later / busy', /busy|callback|later|driving|schedule a call/i],
  ['Off-domain (wrong subject)', /off.?domain|instead of|wrong|nursing|engineering/i],
];
const cc = document.getElementById('cross-cutting');
let html = '<table style="width:100%; border-collapse:collapse;"><thead><tr>'
        + '<th style="text-align:left; padding:6px; border-bottom:1px solid #334155;">Cross-cutting signal</th>'
        + DOMAINS.map(d => `<th style="padding:6px; border-bottom:1px solid #334155; color:${d.color};">${escapeHtml(d.label)}</th>`).join('')
        + '</tr></thead><tbody>';
KEYWORDS.forEach(([label, re]) => {
  const cells = DOMAINS.map(d => {
    const total = (DATA.stats[d.id] || {}).n_total || 0;
    let count = 0;
    ((DATA.domains[d.id] || {}).themes || []).forEach(t => {
      if (re.test(t.title) || re.test(t.description || '')) count += t.call_count;
    });
    return total ? `${count} <span style="color:#94a3b8">(${Math.round(count*100/total)}%)</span>` : '—';
  });
  html += `<tr><td style="padding:6px; border-bottom:1px solid #1e293b;">${escapeHtml(label)}</td>`
        + cells.map(c => `<td style="padding:6px; text-align:center; border-bottom:1px solid #1e293b;">${c}</td>`).join('')
        + '</tr>';
});
html += '</tbody></table>';
cc.innerHTML = html;
</script>
</body>
</html>
"""


def main():
    payload = {"stats": {}, "domains": {}}
    for csv_name, did, _label, _color in DOMAINS:
        payload["stats"][did] = load_call_stats(ROOT / csv_name)
        payload["domains"][did] = aggregate_domain(did)

    domain_meta = [{"id": d[1], "label": d[2], "color": d[3]} for d in DOMAINS]
    domain_vars = " ".join(f"--{d[1]}:{d[3]};" for d in DOMAINS)

    out = (HTML
           .replace("__DATA__", json.dumps(payload, ensure_ascii=False))
           .replace("__DOMAINS__", json.dumps(domain_meta))
           .replace("__DOMAIN_VARS__", domain_vars))
    OUT_HTML.write_text(out, encoding="utf-8")
    print(f"Wrote {OUT_HTML}")

    for d in DOMAINS:
        did = d[1]
        s = payload["stats"][did]
        if not s["n_total"]:
            continue
        themes = payload["domains"][did]["themes"]
        print(f"\n=== {did.upper()} === ({s['n_total']} calls, {s['n_no_user']} silent)")
        for t in themes[:8]:
            print(f"  [{t['call_count']:3d}] {t['title']}")


if __name__ == "__main__":
    main()
