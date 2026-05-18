/* ======================================================================
   Shiksha Transcript Insights — Dashboard JS
   Uses: Chart.js (loaded via CDN in HTML)
   Data: window.__DATA__ (injected by server)
   ====================================================================== */

const D = window.__DATA__ || {};

const COLORS = [
  '#4F46E5','#7C3AED','#EC4899','#EF4444','#F97316',
  '#EAB308','#22C55E','#14B8A6','#06B6D4','#3B82F6',
  '#8B5CF6','#D946EF','#F43F5E','#FB923C','#84CC16'
];
const BG = COLORS.map(c => c + '22');

/* ---- helpers ---- */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const h = s => {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
};
const fmt = n => typeof n === 'number' ? n.toLocaleString() : n;
const pct = (n, t) => t ? Math.round(n / t * 100) : 0;
const mins = s => `${Math.floor(s/60)}m ${Math.round(s%60)}s`;

// Format "2026-04-30 21:51:42" -> "30 Apr 2026, 9:51 PM". Falls back to original string.
const fmtDateTime = (s) => {
  if (!s || typeof s !== 'string') return '';
  // Treat as local time (server already returns IST-style "YYYY-MM-DD HH:MM:SS")
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?/);
  if (!m) return s;
  const [, Y, Mo, D, hh, mm] = m;
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  let out = `${parseInt(D)} ${months[parseInt(Mo)-1]} ${Y}`;
  if (hh != null) {
    let H = parseInt(hh);
    const ampm = H >= 12 ? 'PM' : 'AM';
    H = H % 12 || 12;
    out += `, ${H}:${mm} ${ampm}`;
  }
  return out;
};
const fmtTimeOnly = (s) => {
  const dt = fmtDateTime(s);
  const ix = dt.indexOf(', ');
  return ix >= 0 ? dt.slice(ix + 2) : '';
};

/* ---- tab switching ---- */
function initTabs() {
  // Inject the actual analysed-call count wherever the page expects it.
  const totalCalls = D.total_calls || (D.call_list ? D.call_list.length : 0) || 0;
  const hdr = document.getElementById('hdr-call-count');
  if (hdr) hdr.textContent = fmt(totalCalls);
  document.querySelectorAll('.dyn-call-count').forEach(el => { el.textContent = fmt(totalCalls); });

  $$('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.tab-btn').forEach(b => b.classList.remove('active'));
      $$('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const target = btn.dataset.tab;
      $(`#tab-${target}`).classList.add('active');
      // lazy-init charts
      if (target === 'overview' && !window._overviewInit) { initOverview(); window._overviewInit = true; }
      if (target === 'queries' && !window._queriesInit) { initQueries(); window._queriesInit = true; }
      if (target === 'tactics' && !window._tacticsInit) { initTactics(); window._tacticsInit = true; }
      if (target === 'objections' && !window._objectionsInit) { initObjections(); window._objectionsInit = true; }
      if (target === 'flow' && !window._flowInit) { initFlow(); window._flowInit = true; }
      if (target === 'explorer' && !window._explorerInit) { initExplorer(); window._explorerInit = true; }
      if (target === 'users' && !window._usersInit) { initUsers(); window._usersInit = true; }
      if (target === 'direct-admissions' && !window._daInit) { initDirectAdmissions(); window._daInit = true; }
      if (target === 'institutes' && !window._institutesInit) { initInstitutes(); window._institutesInit = true; }
      if (target === 'deepdive' && !window._deepdiveInit) { initDeepDive(); window._deepdiveInit = true; }
      if (target === 'playbook' && !window._playbookInit) { initPlaybook(); window._playbookInit = true; }
    });
  });
  // trigger default tab
  initOverview(); window._overviewInit = true;
}

/* ==================================================================== */
/*  OVERVIEW TAB                                                         */
/* ==================================================================== */
function initOverview() {
  // stat cards
  $('#stat-total').textContent = fmt(D.total_calls);
  $('#stat-analyzed').textContent = fmt(D.analyzed_calls);
  $('#stat-avgdur').textContent = mins(D.avg_duration);
  $('#stat-totaldur').textContent = `${fmt(D.total_duration_mins)} min`;

  // Outcome donut
  chartDonut('chart-outcomes', D.outcomes, 'Call Outcomes');

  // Stage bar
  chartBar('chart-stages', D.stages, 'Calls by Pipeline Stage');

  // Course bar
  chartBar('chart-courses', D.courses, 'Course Interest');

  // Caller type donut
  chartDonut('chart-callers', D.caller_types, 'Caller Type');

  // Team bar
  chartBar('chart-teams', D.teams, 'Calls by Team');

  // Counsellor bar
  chartBar('chart-counsellors', D.counsellors, 'Calls per Counsellor');

  // ---- Bottom row: Query Buckets / Tactics / Objections charts ----
  const buckets = D.query_buckets || {};
  const bKeys = Object.keys(buckets).slice(0, 8);
  const bCounts = bKeys.map(k => buckets[k].count);
  chartHBar('chart-ov-queries', bKeys, bCounts, 'Top Student Query Buckets');

  const tactics = D.tactics || {};
  const tKeys = Object.keys(tactics).slice(0, 8);
  const tCounts = tKeys.map(k => tactics[k].count);
  chartHBar('chart-ov-tactics', tKeys, tCounts, 'Top Counsellor Tactics');

  const objs = D.objections || {};
  const oKeys = Object.keys(objs);
  const oLabels = oKeys.map(k => k.replace(/_/g, ' '));
  const oCounts = oKeys.map(k => objs[k].count);
  chartHBar('chart-ov-objections', oLabels, oCounts, 'Objection Types');
}

/* ==================================================================== */
/*  QUERY BUCKETS TAB                                                    */
/* ==================================================================== */
function initQueries() {
  const buckets = D.query_buckets || {};
  const labels = Object.keys(buckets);
  const counts = labels.map(l => buckets[l].count);

  chartHBar('chart-buckets', labels, counts, 'Query Frequency');

  // Populate filter dropdown
  const filterEl = $('#query-bucket-filter');
  labels.forEach(label => {
    const opt = document.createElement('option');
    opt.value = label;
    opt.textContent = `${label} (${buckets[label].count})`;
    filterEl.appendChild(opt);
  });

  function renderBucketCards(filterVal) {
    const container = $('#bucket-cards');
    container.innerHTML = '';
    const showLabels = filterVal === 'all' ? labels : labels.filter(l => l === filterVal);
    showLabels.forEach((bucket, i) => {
      const data = buckets[bucket];
      const INITIAL = 3;
      const hasMore = data.examples.length > INITIAL;
      const uid = `bucket-${labels.indexOf(bucket)}`;
      const card = document.createElement('div');
      card.className = 'insight-card';
      card.id = `${uid}-card`;
      card.innerHTML = `
        <div class="flex items-center justify-between mb-2">
          <h4 class="font-semibold text-slate-800">${h(bucket)}</h4>
          <span class="badge badge-indigo">${data.count} queries</span>
        </div>
        <div class="space-y-2" id="${uid}-list">
          ${data.examples.slice(0, INITIAL).map(ex => renderBucketExample(ex)).join('')}
        </div>
        ${hasMore ? renderToggleBtn(uid, 'bucket', labels.indexOf(bucket), data.examples.length - INITIAL) : ''}`;
      container.appendChild(card);
    });
  }

  filterEl.addEventListener('change', () => renderBucketCards(filterEl.value));
  renderBucketCards('all');
}

/* ==================================================================== */
/*  TACTICS TAB                                                          */
/* ==================================================================== */
function initTactics() {
  const tactics = D.tactics || {};
  const labels = Object.keys(tactics);
  const counts = labels.map(l => tactics[l].count);

  chartHBar('chart-tactics', labels, counts, 'Tactic Usage (# of calls)');

  // Populate filter dropdown
  const filterEl = $('#tactic-filter');
  labels.forEach(label => {
    const opt = document.createElement('option');
    opt.value = label;
    opt.textContent = `${label} (${tactics[label].count})`;
    filterEl.appendChild(opt);
  });

  const tacticTips = {
    'Rapport Building': 'Start every bot call with warm greeting + reference to their website action.',
    'Structured Qualification': 'Bot must ask: Course → Exam scores → Category → Location → Budget, in this order.',
    'Reality Check': 'When scores are low, be honest. Builds trust. "With X percentile, Y branch is realistic."',
    'Tiered College Recommendation': 'Always offer 2-3 tiers: dream (stretch), match (realistic), safety (guaranteed).',
    'Placement Data Anchoring': 'Lead with numbers: avg LPA, highest LPA, top recruiters. Students anchor on these.',
    'Urgency Creation': 'Mention deadlines, form closings, limited seats. "Application deadline is next week."',
    'Friction Removal': 'Offer free applications, coupon codes, "I\'ll help you fill the form." Reduce every barrier.',
    'Objection Reframing': 'Reframe concerns: budget → ROI, distance → placement quality, private → brand value.',
    'Multi-Option Strategy': '"Apply to 3-4 colleges, then choose." Reduces decision pressure.',
    'WhatsApp Handoff': 'Move to WhatsApp for documents, lists, follow-ups. Bot should send auto-messages.',
    'Parent/Family Engagement': 'If parent is calling, address both parent concerns (fees) and student interests (course).',
    'Empathy & Reassurance': 'Never dismiss anxiety. "I understand your concern" before any counter-argument.',
    'Comparison Nudge': '"Compare VIT vs SRM on placements." Helps the undecided make choices.',
    'Callback Scheduling': 'Always set a specific next touchpoint. "I\'ll call Monday with more options."',
  };

  function renderTacticCards(filterVal) {
    const container = $('#tactic-cards');
    container.innerHTML = '';
    const showLabels = filterVal === 'all' ? labels : labels.filter(l => l === filterVal);
    showLabels.forEach((tactic) => {
      const i = labels.indexOf(tactic);
      const data = tactics[tactic];
      const INITIAL = 3;
      const hasMore = data.examples.length > INITIAL;
      const uid = `tactic-${i}`;
      const card = document.createElement('div');
      card.className = 'insight-card';
      card.id = `${uid}-card`;
      const tip = tacticTips[tactic] || '';
      card.innerHTML = `
        <div class="flex items-center justify-between mb-2">
          <h4 class="font-semibold text-slate-800">${h(tactic)}</h4>
          <div>
            <span class="badge badge-indigo">${data.count} calls</span>
            <span class="badge badge-green ml-1">${data.pct}%</span>
          </div>
        </div>
        ${tip ? `<div class="text-sm text-indigo-700 bg-indigo-50 rounded px-3 py-2 mb-2">🤖 <strong>Bot Tip:</strong> ${h(tip)}</div>` : ''}
        <div class="space-y-2" id="${uid}-list">
          ${data.examples.slice(0, INITIAL).map(ex => renderTacticExample(ex)).join('')}
        </div>
        ${hasMore ? renderToggleBtn(uid, 'tactic', i, data.examples.length - INITIAL) : ''}`;
      container.appendChild(card);
    });
  }

  filterEl.addEventListener('change', () => renderTacticCards(filterEl.value));
  renderTacticCards('all');
}

/* ==================================================================== */
/*  OBJECTIONS TAB                                                       */
/* ==================================================================== */
function initObjections() {
  const objs = D.objections || {};
  const labels = Object.keys(objs);
  const counts = labels.map(l => objs[l].count);
  const resRates = labels.map(l => objs[l].resolution_rate);

  chartHBar('chart-objections', labels.map(l => l.replace(/_/g,' ')), counts, 'Objection Frequency');

  // Resolution rate bars
  const resContainer = $('#objection-resolution');
  resContainer.innerHTML = '<h3 class="font-semibold text-slate-800 mb-3">Resolution Rate by Objection Type</h3>';
  labels.forEach((label, i) => {
    const rate = resRates[i];
    const color = rate >= 70 ? '#22C55E' : rate >= 40 ? '#EAB308' : '#EF4444';
    resContainer.innerHTML += `
      <div class="mb-2">
        <div class="flex justify-between text-sm mb-1">
          <span class="text-slate-600">${h(label.replace(/_/g,' '))}</span>
          <span class="font-semibold" style="color:${color}">${rate}%</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width:${rate}%;background:${color}">${rate}%</div>
        </div>
      </div>`;
  });

  // Populate filter dropdown
  const filterEl = $('#objection-filter');
  labels.forEach(label => {
    const opt = document.createElement('option');
    opt.value = label;
    opt.textContent = `${label.replace(/_/g, ' ')} (${objs[label].count})`;
    filterEl.appendChild(opt);
  });

  const botScripts = {
    'budget_concern': 'Acknowledge budget, then pitch ROI: "I understand budget is important. Let me show you colleges where the placement package is 5-10x the fee investment."',
    'location_concern': 'Validate preference, then expand: "Staying close to home makes sense. Here are options in [city]. But also consider [nearby city] — just 2 hours away with stronger placements."',
    'exam_not_ready': 'Reassure and redirect: "Many good colleges accept 12th marks directly, no entrance exam needed. Let me share those options."',
    'not_interested': 'Re-engage with a question: "I understand. Just curious — have you already finalized a college, or are you still exploring options?"',
    'already_decided': 'Respect decision, offer value: "Great choice! Would you like me to share the placement data for that college, or suggest a backup option just in case?"',
    'quality_doubt': 'Use data: "That\'s a fair concern. Let me share verified placement data — [X]% of students got placed last year with an average package of [Y] LPA."',
    'wants_government': 'Reality check gently: "Government colleges are excellent, but at [X] rank/percentile, the competition is very high. Would you like to see private options as a safety net?"',
    'family_pressure': 'Involve family: "I\'d love to speak with your parents too. Often a quick chat about placement data helps families feel confident about the decision."',
  };

  function renderObjCards(filterVal) {
    const container = $('#objection-cards');
    container.innerHTML = '';
    const showLabels = filterVal === 'all' ? labels : labels.filter(l => l === filterVal);
    showLabels.forEach((objType) => {
      const i = labels.indexOf(objType);
      const data = objs[objType];
      const INITIAL = 3;
      const hasMore = data.examples.length > INITIAL;
      const uid = `obj-${i}`;
      const card = document.createElement('div');
      card.className = 'insight-card';
      card.id = `${uid}-card`;
      const script = botScripts[objType] || '';
      card.innerHTML = `
        <div class="flex items-center justify-between mb-2">
          <h4 class="font-semibold text-slate-800">${h(objType.replace(/_/g, ' '))}</h4>
          <div>
            <span class="badge badge-amber">${data.count} times</span>
            <span class="badge ${data.resolution_rate >= 60 ? 'badge-green' : 'badge-red'} ml-1">${data.resolution_rate}% resolved</span>
          </div>
        </div>
        ${script ? `<div class="text-sm text-amber-800 bg-amber-50 rounded px-3 py-2 mb-2">🤖 <strong>Suggested Bot Script:</strong> ${h(script)}</div>` : ''}
        <div class="space-y-3" id="${uid}-list">
          ${data.examples.slice(0, INITIAL).map(ex => renderObjExample(ex)).join('')}
        </div>
        ${hasMore ? renderToggleBtn(uid, 'objection', i, data.examples.length - INITIAL) : ''}`;
      container.appendChild(card);
    });
  }

  filterEl.addEventListener('change', () => renderObjCards(filterEl.value));
  renderObjCards('all');
}

/* ==================================================================== */
/*  CALL FLOW TAB                                                        */
/* ==================================================================== */
function initFlow() {
  const flow = D.call_flow || {};
  const labels = Object.keys(flow);
  const pcts = labels.map(l => flow[l].pct);

  // Funnel
  const funnel = $('#flow-funnel');
  funnel.innerHTML = '';
  const maxPct = Math.max(...pcts, 1);
  labels.forEach((phase, i) => {
    const w = Math.max(pcts[i] / maxPct * 100, 15);
    funnel.innerHTML += `
      <div class="mb-2">
        <div class="flex justify-between text-sm mb-1">
          <span class="font-medium text-slate-700">${i+1}. ${h(phase)}</span>
          <span class="text-slate-500">${flow[phase].count} calls (${pcts[i]}%)</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width:${w}%;background:${COLORS[i % COLORS.length]}">${pcts[i]}%</div>
        </div>
      </div>`;
  });

  // Outcome comparison
  const outcomes = D.outcomes || {};
  const outcomeContainer = $('#flow-outcomes');
  outcomeContainer.innerHTML = '<h3 class="font-semibold text-slate-800 mb-3">Call Outcome Distribution</h3>';
  const totalOutcomes = Object.values(outcomes).reduce((a, b) => a + b, 0);
  Object.entries(outcomes).forEach(([outcome, count]) => {
    const p = pct(count, totalOutcomes);
    const color = outcome.includes('application') ? '#22C55E' :
                  outcome.includes('interested') ? '#3B82F6' :
                  outcome.includes('lukewarm') ? '#EAB308' :
                  outcome.includes('callback') ? '#8B5CF6' : '#94a3b8';
    outcomeContainer.innerHTML += `
      <div class="mb-2">
        <div class="flex justify-between text-sm mb-1">
          <span class="text-slate-600">${h(outcome.replace(/_/g, ' '))}</span>
          <span class="font-semibold">${count} (${p}%)</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width:${p}%;background:${color}">${p}%</div>
        </div>
      </div>`;
  });
}

/* ==================================================================== */
/*  EXPLORER TAB                                                         */
/* ==================================================================== */
let explorerData = [];

function initExplorer() {
  explorerData = D.call_list || [];

  // ── Build filter option sets from data ──
  const filterDefs = {
    outcome:    { field: 'outcome',    label: 'All Outcomes',    search: false, extract: c => [c.outcome] },
    stage:      { field: 'stage',      label: 'All Stages',      search: false, extract: c => [c.stage] },
    counsellor: { field: 'counsellor', label: 'All Counsellors', search: true,  extract: c => [c.counsellor] },
    team:       { field: 'team',       label: 'All Teams',       search: false, extract: c => [c.team] },
    course:     { field: 'course',     label: 'All Courses',     search: true,  extract: c => [c.course] },
    tactic:     { field: 'tactic',     label: 'All Tactics',     search: false, extract: c => c.tactics_used || [] },
    college:    { field: 'college',    label: 'All Colleges',    search: true,  extract: c => c.colleges || [] },
    bucket:     { field: 'bucket',     label: 'All Queries',     search: false, extract: c => c.buckets || [] },
  };

  const activeFilters = {};  // { field: Set of checked values }

  // ── Populate each dropdown ──
  Object.entries(filterDefs).forEach(([key, def]) => {
    activeFilters[key] = new Set();
    const vals = new Map();
    explorerData.forEach(c => {
      def.extract(c).forEach(v => {
        if (v && v !== 'N/A' && v !== 'Unknown' && v !== 'error' && v !== 'too_short') {
          vals.set(v, (vals.get(v) || 0) + 1);
        }
      });
    });
    const sorted = [...vals.entries()].sort((a, b) => b[1] - a[1]);

    const container = $(`#filter-${key}`);
    const trigger = container.querySelector('.explorer-dropdown-trigger');
    const menu = container.querySelector('.explorer-dropdown-menu');

    let menuHtml = '';
    if (def.search) menuHtml += `<input type="text" class="dd-search" placeholder="Type to filter…">`;
    sorted.forEach(([val, cnt]) => {
      const id = `flt-${key}-${val.replace(/[^a-zA-Z0-9]/g, '_')}`;
      menuHtml += `<label data-val="${h(val)}"><input type="checkbox" value="${h(val)}" id="${id}"> ${h(val)} <span style="color:#94a3b8;margin-left:auto">(${cnt})</span></label>`;
    });
    menu.innerHTML = menuHtml;

    // Toggle dropdown
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      document.querySelectorAll('.explorer-dropdown-menu').forEach(m => { if (m !== menu) m.classList.add('hidden'); });
      menu.classList.toggle('hidden');
    });

    // Checkbox change
    menu.addEventListener('change', (e) => {
      if (e.target.type !== 'checkbox') return;
      if (e.target.checked) activeFilters[key].add(e.target.value);
      else activeFilters[key].delete(e.target.value);
      const n = activeFilters[key].size;
      trigger.textContent = n ? `${n} selected ▾` : `${def.label} ▾`;
      applyExplorerFilters();
    });

    // Type-ahead search within dropdown
    if (def.search) {
      const searchInput = menu.querySelector('.dd-search');
      searchInput.addEventListener('input', () => {
        const q = searchInput.value.toLowerCase();
        menu.querySelectorAll('label').forEach(lbl => {
          lbl.style.display = lbl.dataset.val.toLowerCase().includes(q) ? '' : 'none';
        });
      });
      searchInput.addEventListener('click', e => e.stopPropagation());
    }
  });

  // ── Close dropdowns on outside click ──
  document.addEventListener('click', () => {
    document.querySelectorAll('.explorer-dropdown-menu').forEach(m => m.classList.add('hidden'));
  });

  // ── Sort state ──
  let sortField = null, sortDir = 'desc';

  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const field = th.dataset.sort;
      if (sortField === field) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
      else { sortField = field; sortDir = 'desc'; }
      document.querySelectorAll('th[data-sort]').forEach(t => t.classList.remove('sort-asc', 'sort-desc'));
      th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      applyExplorerFilters();
    });
  });

  // ── Clear all ──
  $('#explorer-clear-filters').addEventListener('click', () => {
    Object.keys(activeFilters).forEach(key => activeFilters[key].clear());
    document.querySelectorAll('.explorer-dropdown-menu input[type=checkbox]').forEach(cb => cb.checked = false);
    Object.entries(filterDefs).forEach(([key, def]) => {
      $(`#filter-${key} .explorer-dropdown-trigger`).textContent = `${def.label} ▾`;
    });
    $('#explorer-search').value = '';
    sortField = null; sortDir = 'desc';
    document.querySelectorAll('th[data-sort]').forEach(t => t.classList.remove('sort-asc', 'sort-desc'));
    applyExplorerFilters();
  });

  // ── Search ──
  $('#explorer-search').addEventListener('input', applyExplorerFilters);

  // ── Date range filter ──
  const dateFrom = $('#explorer-date-from');
  const dateTo   = $('#explorer-date-to');
  if (dateFrom) dateFrom.addEventListener('change', applyExplorerFilters);
  if (dateTo)   dateTo.addEventListener('change', applyExplorerFilters);
  const dateClear = $('#explorer-date-clear');
  if (dateClear) dateClear.addEventListener('click', () => {
    if (dateFrom) dateFrom.value = '';
    if (dateTo)   dateTo.value = '';
    applyExplorerFilters();
  });
  const appliedOnly = $('#explorer-applied-only');
  if (appliedOnly) appliedOnly.addEventListener('change', applyExplorerFilters);

  // ── Main filter + sort function ──
  function applyExplorerFilters() {
    let filtered = explorerData;

    // Multi-select filters
    Object.entries(activeFilters).forEach(([key, selected]) => {
      if (selected.size === 0) return;
      const def = filterDefs[key];
      filtered = filtered.filter(c => {
        const vals = def.extract(c);
        return vals.some(v => selected.has(v));
      });
    });

    // Text search
    const q = ($('#explorer-search').value || '').toLowerCase();
    if (q) {
      filtered = filtered.filter(c =>
        (c.counsellor || '').toLowerCase().includes(q) ||
        (c.course || '').toLowerCase().includes(q) ||
        (c.summary || '').toLowerCase().includes(q) ||
        (c.team || '').toLowerCase().includes(q) ||
        (c.stage || '').toLowerCase().includes(q) ||
        (c.outcome || '').toLowerCase().includes(q) ||
        (c.user_id || '').toLowerCase().includes(q) ||
        (c.mobile || '').toLowerCase().includes(q) ||
        (c.buckets || []).join(' ').toLowerCase().includes(q) ||
        (c.colleges || []).join(' ').toLowerCase().includes(q)
      );
    }

    // Date range filter (uses created_date YYYY-MM-DD)
    const fromVal = ($('#explorer-date-from')?.value || '').trim();
    const toVal   = ($('#explorer-date-to')?.value   || '').trim();
    if (fromVal || toVal) {
      filtered = filtered.filter(c => {
        const d = c.created_date || '';
        if (!d) return false;
        if (fromVal && d < fromVal) return false;
        if (toVal   && d > toVal)   return false;
        return true;
      });
    }

    // Applied-only filter
    if ($('#explorer-applied-only')?.checked) {
      filtered = filtered.filter(c => c.applied);
    }

    // Sort
    if (sortField) {
      filtered = [...filtered].sort((a, b) => {
        const va = a[sortField] ?? '', vb = b[sortField] ?? '';
        // String sort for date / text fields, numeric for numbers
        if (typeof va === 'string' || typeof vb === 'string') {
          if (va < vb) return sortDir === 'asc' ? -1 : 1;
          if (va > vb) return sortDir === 'asc' ? 1 : -1;
          return 0;
        }
        return sortDir === 'asc' ? va - vb : vb - va;
      });
    }

    // Active filter tags
    const tagContainer = $('#explorer-active-filters');
    const tags = [];
    Object.entries(activeFilters).forEach(([key, selected]) => {
      selected.forEach(v => tags.push(`<span class="filter-tag" data-key="${key}" data-val="${h(v)}">${key}: ${h(v)} ✕</span>`));
    });
    if (tags.length) {
      tagContainer.innerHTML = tags.join('');
      tagContainer.classList.remove('hidden');
      tagContainer.querySelectorAll('.filter-tag').forEach(tag => {
        tag.addEventListener('click', () => {
          const k = tag.dataset.key, v = tag.dataset.val;
          activeFilters[k].delete(v);
          const cb = document.querySelector(`#filter-${k} input[value="${v}"]`);
          if (cb) cb.checked = false;
          const n = activeFilters[k].size;
          $(`#filter-${k} .explorer-dropdown-trigger`).textContent = n ? `${n} selected ▾` : `${filterDefs[k].label} ▾`;
          applyExplorerFilters();
        });
      });
    } else {
      tagContainer.classList.add('hidden');
    }

    renderExplorerTable(filtered);
  }

  applyExplorerFilters();
}

function renderExplorerTable(data) {
  const tbody = $('#explorer-tbody');
  tbody.innerHTML = '';
  $('#explorer-count').textContent = `${data.length} calls`;

  data.forEach(c => {
    const outcomeBadge = c.outcome === 'application_started' ? 'badge-green' :
                         c.outcome.includes('interested') ? 'badge-indigo' :
                         c.outcome.includes('callback') ? 'badge-amber' : 'badge-slate';

    // "Other calls" pill if this user has more transcripts
    const userKey = c.user_id || c.mobile || '';
    const sameUser = userKey ? explorerData.filter(o => (o.user_id || o.mobile || '') === userKey && o.id !== c.id) : [];
    const userBadge = sameUser.length
      ? `<span class="badge badge-cyan" title="This user has ${sameUser.length} other transcripts">+${sameUser.length} more</span>`
      : '';
    const userLabel = c.user_id ? `${h(c.user_id)}` : (c.mobile ? `📞 ${h(c.mobile)}` : '—');

    const tr = document.createElement('tr');
    tr.className = 'cursor-pointer';
    tr.onclick = () => openTranscript(c.id);
    tr.innerHTML = `
      <td class="text-xs whitespace-nowrap">${h(fmtDateTime(c.created_on) || c.created_date || '—')}</td>
      <td class="font-medium">${h(c.counsellor)}</td>
      <td class="text-xs">${h(c.team)}</td>
      <td>${h(c.course)}</td>
      <td>${mins(c.duration)}</td>
      <td>${c.total_turns}</td>
      <td><span class="badge badge-slate">${h(c.stage)}</span></td>
      <td><span class="badge ${outcomeBadge}">${h(c.outcome.replace(/_/g,' '))}</span></td>
      <td class="text-center">${c.applied ? '<span class="badge badge-green" title="Confirmed: this user submitted an application after the call">✅ Applied</span>' : '<span class="text-slate-300 text-xs">—</span>'}</td>
      <td class="text-xs whitespace-nowrap">${userLabel} ${userBadge}</td>
      <td class="text-xs text-slate-500 max-w-xs truncate">${h(c.summary)}</td>`;
    tbody.appendChild(tr);
  });
}

async function openTranscript(callId) {
  const modal = $('#transcript-modal');
  const body = $('#modal-body');
  body.innerHTML = '<div class="text-center py-8 text-slate-400">Loading transcript…</div>';
  modal.classList.remove('hidden');

  try {
    const res = await fetch(`/api/calls/${encodeURIComponent(callId)}`);
    const data = await res.json();
    if (data.error) { body.innerHTML = `<p class="text-red-500">${h(data.error)}</p>`; return; }

    const { analysis: a, transcript: t } = data;
    const an = a?.analysis;
    const meta = a?.metadata;
    const turns = t?.turns || [];

    // Helper: find the turn index whose text best matches a quote
    function findTurnForQuote(quote) {
      if (!quote || !turns.length) return -1;
      const normalize = s => s.toLowerCase().replace(/[^\w\s]/g, '').replace(/\s+/g, ' ').trim();
      const q = normalize(quote);
      if (!q) return -1;

      // Extract meaningful words (length > 2)
      const qWords = q.split(' ').filter(w => w.length > 2);
      if (!qWords.length) return -1;

      // Score each turn by word overlap
      let bestIdx = -1, bestScore = 0;
      for (let i = 0; i < turns.length; i++) {
        const txt = normalize(turns[i].text);
        const tWords = new Set(txt.split(' '));
        let overlap = 0;
        for (const w of qWords) {
          if (tWords.has(w)) overlap++;
        }
        // Also try substring containment for short quotes
        if (txt.includes(q)) return i;
        if (overlap > bestScore) { bestScore = overlap; bestIdx = i; }
      }
      // Require at least 40% of quote words to match
      return (bestScore >= 2 && bestScore >= qWords.length * 0.3) ? bestIdx : -1;
    }

    let html = '';

    // Meta header
    if (meta) {
      // Identifier banner: date/time + call id
      const dateLabel = fmtDateTime(meta.created_on || '') || '—';
      const callListAll = (D && D.call_list) || [];
      const thisCall = callListAll.find(x => x.id === callId);
      const appliedBadge = thisCall && thisCall.applied
        ? '<span class="px-2 py-0.5 rounded-full bg-emerald-500 text-white text-xs font-semibold" title="Confirmed: this user submitted an application after the call">✅ Applied</span>'
        : '';
      html += `<div class="mb-3 px-3 py-2 rounded-lg bg-slate-900 text-white flex flex-wrap items-center justify-between gap-2">
        <div class="text-sm flex items-center gap-3"><span class="text-slate-300">📞 Call</span><span class="font-semibold">${h(dateLabel)}</span>${appliedBadge}</div>
        <div class="text-xs text-slate-300 font-mono">id: ${h(callId)}</div>
      </div>`;

      html += `<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div class="card-sm bg-slate-50"><div class="stat-label">Counsellor</div><div class="text-sm font-semibold">${h(meta.counsellor_name)}</div></div>
        <div class="card-sm bg-slate-50"><div class="stat-label">Duration</div><div class="text-sm font-semibold">${mins(meta.duration)}</div></div>
        <div class="card-sm bg-slate-50"><div class="stat-label">Stage</div><div class="text-sm font-semibold">${h(meta.stage_name)}</div></div>
        <div class="card-sm bg-slate-50"><div class="stat-label">Team</div><div class="text-sm font-semibold">${h(meta.team_name)}</div></div>
      </div>`;

      // —— Other calls from same user (collapsible, sorted ascending) ——
      const userKey = (meta.user_id ? String(meta.user_id) : '') || (meta.mobile_number ? String(meta.mobile_number) : '');
      const callList = (D && D.call_list) || [];
      const sameUser = userKey ? callList.filter(c => {
        const k = (meta.user_id ? c.user_id : c.mobile);
        return k && String(k) === userKey && c.id !== callId;
      }) : [];
      if (sameUser.length) {
        // Ascending by created_on (oldest first), so the journey reads top-to-bottom in time order
        sameUser.sort((x, y) => (x.created_on || '').localeCompare(y.created_on || ''));
        html += `<details class="mb-4 rounded-lg border border-cyan-100 bg-cyan-50">
          <summary class="cursor-pointer select-none px-3 py-2 flex items-center justify-between">
            <span class="font-semibold text-cyan-900">👥 ${sameUser.length} other call${sameUser.length>1?'s':''} from this user</span>
            <span class="text-xs text-cyan-700">${meta.user_id ? 'user_id: '+h(meta.user_id) : 'mobile: '+h(meta.mobile_number||'')}</span>
          </summary>
          <div class="flex flex-col gap-1 px-3 pb-3 pt-1">
            ${sameUser.map(c => `
              <button class="text-left text-sm px-2 py-1.5 rounded hover:bg-white border border-cyan-100 cursor-pointer related-call-link" data-call-id="${h(c.id)}">
                <span class="text-xs text-cyan-700 font-mono mr-2 whitespace-nowrap">${h(fmtDateTime(c.created_on) || c.created_date || '—')}</span>
                <span class="badge badge-slate mr-2">${h(c.stage)}</span>
                <span class="text-slate-700">${mins(c.duration)} · ${h(c.counsellor)}</span>
                <span class="text-xs text-slate-500 ml-2">${h((c.summary || '').slice(0,80))}${(c.summary||'').length>80?'…':''}</span>
              </button>`).join('')}
          </div>
        </details>`;
      }
    }

    // Analysis summary
    if (an) {
      html += `<div class="card mb-4 bg-indigo-50 border border-indigo-100">
        <h4 class="font-semibold text-indigo-900 mb-1">Summary</h4>
        <p class="text-sm text-indigo-800">${h(an.summary)}</p>
      </div>`;

      // Student profile
      const sp = an.student_profile;
      html += `<div class="card mb-4">
        <h4 class="font-semibold text-slate-800 mb-2">Student Profile</h4>
        <div class="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
          <div><span class="text-slate-500">Course:</span> ${h(sp.course_interest)}</div>
          <div><span class="text-slate-500">Scores:</span> ${h(sp.exam_scores)}</div>
          <div><span class="text-slate-500">Category:</span> ${h(sp.category)}</div>
          <div><span class="text-slate-500">Location:</span> ${h(sp.location_preference)}</div>
          <div><span class="text-slate-500">Budget:</span> ${h(sp.budget)}</div>
          <div><span class="text-slate-500">Stage:</span> ${h(sp.decision_stage)}</div>
        </div>
      </div>`;

      // Student Queries
      if (an.query_buckets?.length) {
        html += `<div class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <h4 class="font-semibold text-slate-800">Student Queries</h4>
            <button class="text-xs text-green-600 hover:text-green-800 font-medium" onclick="this.parentElement.nextElementSibling.nextElementSibling.classList.toggle('hidden');this.textContent=this.textContent==='Show details'?'Hide details':'Show details'">Show details</button>
          </div>
          <div class="flex flex-wrap gap-1 mb-2">${[...new Set(an.query_buckets.map(q => q.bucket))].map(b =>
            `<span class="badge badge-green cursor-pointer hover:ring-2 hover:ring-green-300 transcript-nav-pill" data-quote-source="query" data-bucket="${h(b)}">${h(b)}</span>`
          ).join('')}</div>
          <div class="space-y-2 hidden">
          ${an.query_buckets.map(q => `<div class="text-sm bg-green-50 rounded p-2 border border-green-100">
            <span class="font-medium text-green-800">${h(q.bucket)}:</span>
            <span class="text-green-700">${h(q.query)}</span>
            ${q.quote ? `<div class="text-xs text-green-600 mt-1 italic">"${h(q.quote)}"</div>` : ''}
            ${q.translation ? `<div class="text-xs text-slate-500">${h(q.translation)}</div>` : ''}
          </div>`).join('')}
          </div>
        </div>`;
      }

      // Tactics used — clickable pills with quotes
      html += `<div class="mb-4">
        <div class="flex items-center justify-between mb-2">
          <h4 class="font-semibold text-slate-800">Tactics Used</h4>
          <button class="text-xs text-indigo-600 hover:text-indigo-800 font-medium" onclick="this.parentElement.nextElementSibling.nextElementSibling.classList.toggle('hidden');this.textContent=this.textContent==='Show details'?'Hide details':'Show details'">Show details</button>
        </div>
        <div class="flex flex-wrap gap-1 mb-2">${an.counsellor_tactics.map((t, ti) =>
          `<span class="badge badge-indigo cursor-pointer hover:ring-2 hover:ring-indigo-300 transcript-nav-pill" data-quote-source="tactic" data-tactic-idx="${ti}">${h(t.tactic)}</span>`
        ).join('')}</div>
        <div class="space-y-2 hidden">
        ${an.counsellor_tactics.map(t => `<div class="text-sm bg-indigo-50 rounded p-2 border border-indigo-100">
          <span class="font-medium text-indigo-800">${h(t.tactic)}:</span>
          <span class="text-indigo-700">${h(t.description)}</span>
          ${t.quote ? `<div class="text-xs text-indigo-600 mt-1 italic">"${h(t.quote)}"</div>` : ''}
          ${t.translation ? `<div class="text-xs text-slate-500">${h(t.translation)}</div>` : ''}
        </div>`).join('')}
        </div>
      </div>`;

      // Colleges
      if (an.colleges_discussed?.length) {
        html += `<div class="card mb-4"><h4 class="font-semibold text-slate-800 mb-2">Colleges Discussed</h4>
          <table class="data-table"><thead><tr><th>College</th><th>Location</th><th>Fee</th><th>Placement</th><th>Reaction</th></tr></thead><tbody>
          ${an.colleges_discussed.map(c => `<tr>
            <td class="font-medium">${h(c.name)}</td><td>${h(c.location)}</td>
            <td>${h(c.fee_mentioned)}</td><td>${h(c.placement_mentioned)}</td>
            <td><span class="badge ${c.student_reaction==='positive'?'badge-green':c.student_reaction==='negative'?'badge-red':'badge-slate'}">${h(c.student_reaction)}</span></td>
          </tr>`).join('')}
          </tbody></table></div>`;
      }
    }

    // Full transcript — each turn gets a unique ID for navigation
    if (turns.length) {
      html += `<div class="card"><h4 class="font-semibold text-slate-800 mb-3">Full Transcript</h4>
        <div class="space-y-1" id="transcript-turns">
        ${turns.map((turn, i) => `
          <div class="turn turn-${turn.speaker.toLowerCase()}" id="turn-${i}">
            <span class="turn-time">[${turn.start_time}]</span>
            <span class="turn-speaker">${turn.speaker}:</span>
            <span class="turn-text">${h(turn.text)}</span>
          </div>
        `).join('')}
        </div></div>`;
    }

    body.innerHTML = html;

    // Wire up related-call links to swap modal content
    body.querySelectorAll('.related-call-link').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = btn.dataset.callId;
        if (id) openTranscript(id);
      });
    });

    // Wire up clickable pills to navigate to transcript
    if (an && turns.length) {
      body.querySelectorAll('.transcript-nav-pill').forEach(pill => {
        pill.addEventListener('click', () => {
          let quote = '';
          const src = pill.dataset.quoteSource;
          if (src === 'tactic') {
            const idx = parseInt(pill.dataset.tacticIdx);
            quote = an.counsellor_tactics[idx]?.quote || '';
          } else if (src === 'query') {
            const bucket = pill.dataset.bucket;
            const q = an.query_buckets.find(q => q.bucket === bucket);
            quote = q?.quote || '';
          }
          const turnIdx = findTurnForQuote(quote);
          if (turnIdx >= 0) {
            const el = document.getElementById(`turn-${turnIdx}`);
            if (el) {
              // Remove previous highlights
              body.querySelectorAll('.turn-highlight').forEach(t => t.classList.remove('turn-highlight'));
              el.classList.add('turn-highlight');
              el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
          }
        });
      });
    }
  } catch (err) {
    body.innerHTML = `<p class="text-red-500">Error loading transcript: ${h(err.message)}</p>`;
  }
}

function closeModal() {
  $('#transcript-modal').classList.add('hidden');
}

/* ==================================================================== */
/*  DIRECT ADMISSIONS TAB                                                */
/* ==================================================================== */
let daData = {};
let daCalls = [];

function initDirectAdmissions() {
  daData = D.direct_admissions || {};
  daCalls = daData.calls || [];

  // Stats
  $('#da-stat-total').textContent = fmt(daData.total_flagged || 0);
  $('#da-stat-pct').textContent = `${daData.pct_of_calls || 0}%`;
  const initiated = daData.initiated_by || {};
  $('#da-stat-student').textContent = fmt(initiated['User'] || 0) + ' mentions';
  $('#da-stat-counsellor').textContent = fmt(initiated['Counsellor'] || 0) + ' mentions';

  // Keyword chart
  const kwBreakdown = daData.keyword_breakdown || {};
  const kwLabels = Object.keys(kwBreakdown);
  const kwCounts = Object.values(kwBreakdown);
  chartHBar('chart-da-keywords', kwLabels, kwCounts, 'Keyword Frequency Across Calls');

  // Initiated-by chart
  const initLabels = Object.keys(initiated);
  const initCounts = Object.values(initiated);
  chartDonut('chart-da-initiated', initiated, 'Who Brings It Up?');

  // Render cards
  renderDACards(daCalls);

  // Search
  $('#da-search').addEventListener('input', () => {
    const q = ($('#da-search').value || '').toLowerCase();
    const filtered = daCalls.filter(c =>
      c.counsellor.toLowerCase().includes(q) ||
      c.course.toLowerCase().includes(q) ||
      c.summary.toLowerCase().includes(q) ||
      c.keywords_found.some(k => k.includes(q)) ||
      c.colleges_discussed.some(col => col.toLowerCase().includes(q))
    );
    renderDACards(filtered);
  });
}

function renderDACards(calls) {
  const container = $('#da-cards');
  container.innerHTML = '';
  $('#da-call-count').textContent = calls.length;

  calls.forEach((call, i) => {
    const card = document.createElement('div');
    card.className = 'insight-card';
    card.style.borderLeft = '4px solid #EF4444';

    const outcomeBadge = call.outcome === 'application_started' ? 'badge-green' :
                         call.outcome.includes('interested') ? 'badge-indigo' :
                         call.outcome.includes('callback') ? 'badge-amber' : 'badge-slate';

    // Header
    let html = `
      <div class="flex flex-col md:flex-row md:items-center justify-between mb-3">
        <div>
          <h4 class="font-semibold text-slate-800">${h(call.counsellor)}</h4>
          <div class="flex flex-wrap gap-1 mt-1">
            <span class="badge badge-slate">${h(call.course)}</span>
            <span class="badge ${outcomeBadge}">${h((call.outcome || '').replace(/_/g, ' '))}</span>
            <span class="badge badge-slate">${mins(call.duration)}</span>
          </div>
        </div>
        <div class="flex flex-wrap gap-1 mt-2 md:mt-0">
          ${call.keywords_found.map(kw => `<span class="badge" style="background:#FEE2E2;color:#991B1B">${h(kw)}</span>`).join('')}
        </div>
      </div>`;

    // Summary
    if (call.summary) {
      html += `<div class="text-sm text-slate-600 mb-3 bg-slate-50 rounded p-3">${h(call.summary)}</div>`;
    }

    // Colleges discussed
    if (call.colleges_discussed.length) {
      html += `<div class="mb-3">
        <span class="text-xs font-semibold text-slate-500 uppercase">Colleges discussed:</span>
        <div class="flex flex-wrap gap-1 mt-1">${call.colleges_discussed.map(c => `<span class="badge badge-indigo">${h(c)}</span>`).join('')}</div>
      </div>`;
    }

    // Analysis mentions (structured insights from GPT analysis)
    if (call.analysis_mentions?.length) {
      html += `<div class="mb-3">
        <span class="text-xs font-semibold text-slate-500 uppercase">Analysis Insights</span>`;
      call.analysis_mentions.forEach(am => {
        if (am.source === 'student_query') {
          html += `<div class="pl-3 border-l-2 border-blue-300 mt-2">
            <span class="badge badge-indigo text-xs">Student Query</span>
            <div class="text-sm text-slate-700 mt-1">${h(am.text)}</div>
            ${am.quote ? `<div class="quote">"${h(am.quote)}"</div>` : ''}
          </div>`;
        } else if (am.source === 'objection') {
          html += `<div class="pl-3 border-l-2 border-amber-300 mt-2">
            <span class="badge badge-amber text-xs">Objection</span>
            <div class="text-sm text-slate-700 mt-1"><strong>Issue:</strong> ${h(am.text)}</div>
            ${am.handling ? `<div class="text-sm text-slate-600"><strong>Handling:</strong> ${h(am.handling)}</div>` : ''}
            ${am.student_quote ? `<div class="quote text-red-700">"${h(am.student_quote)}"</div>` : ''}
            ${am.counsellor_quote ? `<div class="quote text-indigo-700">"${h(am.counsellor_quote)}"</div>` : ''}
          </div>`;
        } else if (am.source === 'summary') {
          html += `<div class="pl-3 border-l-2 border-slate-300 mt-2">
            <span class="badge badge-slate text-xs">Summary</span>
            <div class="text-sm text-slate-600 mt-1">${h(am.text)}</div>
          </div>`;
        }
      });
      html += `</div>`;
    }

    // Matched turns with context (conversation snippets)
    const INITIAL = 2;
    const uid = `da-${i}`;
    const turnsToShow = call.matched_turns.slice(0, INITIAL);
    const hasMore = call.matched_turns.length > INITIAL;

    html += `<div>
      <span class="text-xs font-semibold text-slate-500 uppercase">Relevant Conversation Snippets</span>
      <div class="space-y-3 mt-2" id="${uid}-turns">
        ${turnsToShow.map(mt => renderDATurn(mt)).join('')}
      </div>
      ${hasMore ? `<div id="${uid}-toggle"><button class="text-sm text-red-600 hover:text-red-800 font-medium mt-2 cursor-pointer" onclick="toggleDATurns('${uid}', ${i})">▼ Show ${call.matched_turns.length - INITIAL} more snippets</button></div>` : ''}
    </div>`;

    // View full transcript link
    html += `<div class="mt-3 pt-3 border-t border-slate-100">
      <a href="#" onclick="event.preventDefault();openTranscript('${call.id.replace(/'/g, "\\'")}')" class="text-indigo-600 hover:text-indigo-800 font-medium text-sm">📞 View full transcript &amp; analysis →</a>
    </div>`;

    card.innerHTML = html;
    container.appendChild(card);
  });
}

function renderDATurn(mt) {
  return `<div class="bg-slate-50 rounded-lg p-3">
    <div class="space-y-1">
      ${mt.context.map(t => `
        <div class="text-sm ${t.is_match ? 'bg-red-50 border-l-2 border-red-400 pl-2 py-0.5 rounded' : ''}">
          <span class="text-xs text-slate-400">[${h(t.time)}]</span>
          <span class="font-semibold ${t.speaker === 'Counsellor' ? 'text-indigo-700' : 'text-green-700'}">${h(t.speaker)}:</span>
          <span class="text-slate-700">${highlightDAKeywords(t.text)}</span>
        </div>
      `).join('')}
    </div>
  </div>`;
}

function highlightDAKeywords(text) {
  const keywords = [
    'direct admission', 'direct entry', 'management quota',
    'management seat', 'mgmt quota', 'donation seat',
    'capitation', 'without entrance', 'bina entrance',
    'bina exam', 'donation se', 'sidha admission',
    'seedha admission', 'management se', 'quota se admission'
  ];
  let safe = h(text);
  keywords.forEach(kw => {
    const regex = new RegExp(`(${kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    safe = safe.replace(regex, '<mark class="bg-red-200 text-red-900 px-0.5 rounded">$1</mark>');
  });
  return safe;
}

function toggleDATurns(uid, idx) {
  const listEl = document.getElementById(`${uid}-turns`);
  const toggleEl = document.getElementById(`${uid}-toggle`);
  const isExpanded = toggleEl.dataset.expanded === '1';
  const call = daCalls[idx];
  const INITIAL = 2;

  if (isExpanded) {
    listEl.innerHTML = call.matched_turns.slice(0, INITIAL).map(mt => renderDATurn(mt)).join('');
    toggleEl.innerHTML = `<button class="text-sm text-red-600 hover:text-red-800 font-medium mt-2 cursor-pointer" onclick="toggleDATurns('${uid}', ${idx})">▼ Show ${call.matched_turns.length - INITIAL} more snippets</button>`;
    toggleEl.dataset.expanded = '0';
  } else {
    listEl.innerHTML = call.matched_turns.map(mt => renderDATurn(mt)).join('');
    toggleEl.innerHTML = `<button class="text-sm text-red-600 hover:text-red-800 font-medium mt-2 cursor-pointer" onclick="toggleDATurns('${uid}', ${idx})">▲ Collapse (${call.matched_turns.length} shown)</button>`;
    toggleEl.dataset.expanded = '1';
  }
}

/* ==================================================================== */
/*  INSTITUTE USPs TAB                                                   */
/* ==================================================================== */
let uspData = {};
let uspEntries = [];

function initInstitutes() {
  uspData = D.institute_usps || {};
  uspEntries = Object.entries(uspData).map(([name, data]) => ({ name, ...data }));

  // Stats
  const totalInstitutes = uspEntries.length;
  const totalUSPs = uspEntries.reduce((s, e) => s + e.pitch_points.length, 0);
  const totalFees = uspEntries.reduce((s, e) => s + e.fee_details.length, 0);
  const avgUSPs = totalInstitutes ? (totalUSPs / totalInstitutes).toFixed(1) : 0;

  $('#usp-stat-total').textContent = fmt(totalInstitutes);
  $('#usp-stat-usps').textContent = fmt(totalUSPs);
  $('#usp-stat-fees').textContent = fmt(totalFees);
  $('#usp-stat-avg').textContent = avgUSPs;

  // Chart: Top 15 by mentions
  const top15 = uspEntries.slice(0, 15);
  chartHBar('chart-usp-mentions',
    top15.map(e => e.name.length > 30 ? e.name.slice(0, 28) + '…' : e.name),
    top15.map(e => e.mention_count),
    'Top 15 Institutes by Mentions in Calls'
  );

  // Chart: USP categories distribution
  const catCounts = {};
  uspEntries.forEach(e => {
    e.pitch_points.forEach(pp => {
      const cat = pp.category || 'other';
      catCounts[cat] = (catCounts[cat] || 0) + 1;
    });
  });
  const catSorted = Object.entries(catCounts).sort((a, b) => b[1] - a[1]);
  // Grow the inner wrapper so each bar gets ~26px; the outer card scrolls.
  const catWrap = document.getElementById('chart-usp-categories-wrap');
  if (catWrap) {
    catWrap.style.height = Math.max(400, catSorted.length * 26) + 'px';
  }
  chartHBar('chart-usp-categories',
    catSorted.map(([c]) => c.replace(/_/g, ' ')),
    catSorted.map(([, v]) => v),
    'USP Categories Across All Institutes'
  );

  // Build course pills
  buildCoursePills();

  // Render cards
  renderUSPCards(uspEntries);

  // Search
  $('#usp-search').addEventListener('input', () => filterAndRenderUSPs());
  $('#usp-sort').addEventListener('change', () => filterAndRenderUSPs());
}

let activeCoursePill = null;

function buildCoursePills() {
  const courseCounts = {};
  uspEntries.forEach(e => {
    (e.courses_discussed || []).forEach(c => {
      // Normalize to base course (strip specialization)
      const base = normalizeBaseCourse(c);
      courseCounts[base] = (courseCounts[base] || 0) + 1;
    });
  });
  const sorted = Object.entries(courseCounts).sort((a, b) => b[1] - a[1]);
  const container = $('#usp-course-pills');
  container.innerHTML = '';

  // "All" pill
  const allPill = document.createElement('button');
  allPill.className = 'course-pill active';
  allPill.textContent = `All (${uspEntries.length})`;
  allPill.addEventListener('click', () => {
    activeCoursePill = null;
    $$('.course-pill').forEach(p => p.classList.remove('active'));
    allPill.classList.add('active');
    filterAndRenderUSPs();
  });
  container.appendChild(allPill);

  sorted.forEach(([course, count]) => {
    const pill = document.createElement('button');
    pill.className = 'course-pill';
    pill.textContent = `${course} (${count})`;
    pill.addEventListener('click', () => {
      activeCoursePill = course;
      $$('.course-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      filterAndRenderUSPs();
    });
    container.appendChild(pill);
  });

  // Collapse pills past INITIAL_VISIBLE; show toggle to expand/collapse.
  const INITIAL_VISIBLE = 12; // not counting the "All" pill
  const toggleBtn = document.getElementById('usp-course-pills-toggle');
  const allPills = Array.from(container.querySelectorAll('.course-pill'));
  // index 0 is the "All" pill; hide everything past INITIAL_VISIBLE+1
  if (allPills.length > INITIAL_VISIBLE + 1 && toggleBtn) {
    const applyCollapsed = () => {
      allPills.forEach((p, i) => {
        if (i > INITIAL_VISIBLE) p.style.display = 'none';
      });
      toggleBtn.textContent = `Show all (${allPills.length - 1 - INITIAL_VISIBLE} more)`;
    };
    const applyExpanded = () => {
      allPills.forEach(p => { p.style.display = ''; });
      toggleBtn.textContent = 'Show less';
    };
    let expanded = false;
    applyCollapsed();
    toggleBtn.classList.remove('hidden');
    toggleBtn.onclick = () => {
      expanded = !expanded;
      if (expanded) applyExpanded(); else applyCollapsed();
    };
  } else if (toggleBtn) {
    toggleBtn.classList.add('hidden');
  }
}

function normalizeBaseCourse(course) {
  const c = course.trim();
  // Match common base courses
  if (/^B\.?\s*Tech/i.test(c)) return 'B.Tech';
  if (/^M\.?\s*Tech/i.test(c)) return 'M.Tech';
  if (/^B\.?\s*Pharma/i.test(c)) return 'B.Pharma';
  if (/^D\.?\s*Pharma/i.test(c)) return 'D.Pharma';
  if (/^M\.?\s*Pharma/i.test(c)) return 'M.Pharma';
  if (/^BBA/i.test(c)) return 'BBA';
  if (/^MBA/i.test(c)) return 'MBA';
  if (/^BCA/i.test(c)) return 'BCA';
  if (/^MCA/i.test(c)) return 'MCA';
  if (/^B\.?\s*D\.?\s*S/i.test(c)) return 'BDS';
  if (/^MBBS/i.test(c)) return 'MBBS';
  if (/^B\.?\s*Sc/i.test(c)) return 'B.Sc';
  if (/^M\.?\s*Sc/i.test(c)) return 'M.Sc';
  if (/^B\.?\s*Com/i.test(c)) return 'B.Com';
  if (/^BA\b/i.test(c)) return 'BA';
  if (/^MA\b/i.test(c)) return 'MA';
  if (/^B\.?\s*Des/i.test(c)) return 'B.Des';
  if (/^LLB/i.test(c)) return 'LLB';
  if (/^LLM/i.test(c)) return 'LLM';
  if (/^PGDM/i.test(c)) return 'PGDM';
  if (/^B\.?\s*Ed/i.test(c)) return 'B.Ed';
  if (/^BMLT/i.test(c)) return 'BMLT';
  if (/^DMLT/i.test(c)) return 'DMLT';
  if (/^GNM/i.test(c)) return 'GNM';
  if (/^B\.?\s*Sc.*Nurs/i.test(c)) return 'B.Sc Nursing';
  return c;
}

function filterAndRenderUSPs() {
  const q = ($('#usp-search').value || '').toLowerCase();
  const sort = $('#usp-sort').value;

  let filtered = uspEntries;

  // Course pill filter
  if (activeCoursePill) {
    filtered = filtered.filter(e =>
      (e.courses_discussed || []).some(c => normalizeBaseCourse(c) === activeCoursePill)
    );
  }

  if (q) {
    filtered = filtered.filter(e =>
      e.name.toLowerCase().includes(q) ||
      (e.aliases || []).some(a => a.toLowerCase().includes(q)) ||
      (e.location || '').toLowerCase().includes(q) ||
      (e.courses_discussed || []).some(c => c.toLowerCase().includes(q)) ||
      e.pitch_points.some(pp => pp.claim.toLowerCase().includes(q))
    );
  }

  if (sort === 'usps') filtered = [...filtered].sort((a, b) => b.pitch_points.length - a.pitch_points.length);
  else if (sort === 'name') filtered = [...filtered].sort((a, b) => a.name.localeCompare(b.name));
  // default is mentions (already sorted)

  renderUSPCards(filtered);
}

function renderUSPCards(entries) {
  const container = $('#usp-cards');
  container.innerHTML = '';
  $('#usp-institute-count').textContent = entries.length;

  entries.forEach((inst, i) => {
    const card = document.createElement('div');
    card.className = 'insight-card usp-card-collapsible';
    card.style.borderLeftColor = COLORS[i % COLORS.length];

    // Filter internals by active course pill
    const courseFilter = activeCoursePill;
    const matchingCourses = courseFilter
      ? (inst.courses_discussed || []).filter(c => normalizeBaseCourse(c) === courseFilter)
      : (inst.courses_discussed || []);
    const filteredFees = courseFilter
      ? inst.fee_details.filter(f => matchingCourses.some(mc => (f.course || '').toLowerCase().includes(mc.toLowerCase()) || mc.toLowerCase().includes((f.course || '').toLowerCase())) || !f.course)
      : inst.fee_details;
    const filteredPP = courseFilter
      ? inst.pitch_points.filter(pp => {
          const claim = (pp.claim || '').toLowerCase();
          const quote = (pp.counsellor_quote_hindi || '').toLowerCase();
          return matchingCourses.some(mc => claim.includes(mc.toLowerCase()) || quote.includes(mc.toLowerCase())) ||
                 !matchingCourses.length ||
                 !(pp.category === 'fee' || pp.category === 'admission_process' || pp.category === 'eligibility' || pp.category === 'exam_cutoff') ||
                 matchingCourses.length === (inst.courses_discussed || []).length;
        })
      : inst.pitch_points;

    // Header — always visible, acts as toggle
    let headerHTML = `
      <div class="usp-card-header" onclick="toggleUSPCard(this)">
        <div class="flex flex-col md:flex-row md:items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="usp-chevron text-slate-400">▶</span>
            <div>
              <h4 class="font-bold text-lg text-slate-800">${h(inst.name)}</h4>
              <div class="flex flex-wrap gap-1 mt-1">
                ${inst.location && inst.location !== 'not_mentioned' ? `<span class="badge badge-slate">📍 ${h(inst.location.length > 60 ? inst.location.slice(0, 57) + '…' : inst.location)}</span>` : ''}
                ${(inst.aliases || []).map(a => `<span class="badge badge-slate">${h(a)}</span>`).join('')}
              </div>
            </div>
          </div>
          <div class="flex gap-2 mt-2 md:mt-0">
            <span class="badge badge-indigo">${inst.mention_count} mentions</span>
            <span class="badge badge-green">${filteredPP.length} USPs</span>
            ${filteredFees.length ? `<span class="badge badge-amber">${filteredFees.length} fee entries</span>` : ''}
          </div>
        </div>
      </div>`;

    // Body — collapsed by default
    let bodyParts = [];

    // Recommendation context (moved higher)
    if (inst.recommendation_contexts?.length) {
      const uniqueCtx = [...new Set(inst.recommendation_contexts)].slice(0, 3);
      bodyParts.push(`<div class="mb-3">
        <span class="text-xs font-semibold text-slate-500 uppercase">Why Counsellors Recommend This</span>
        <div class="mt-1">${uniqueCtx.map(ctx => `<div class="text-sm text-slate-600 mb-1">→ ${h(ctx)}</div>`).join('')}</div>
      </div>`);
    }

    // Courses
    if (matchingCourses.length) {
      bodyParts.push(`<div class="mb-3">
        <span class="text-xs font-semibold text-slate-500 uppercase">Courses discussed:</span>
        <div class="flex flex-wrap gap-1 mt-1">${matchingCourses.map(c => `<span class="badge badge-indigo">${h(c)}</span>`).join('')}</div>
      </div>`);
    }

    // Fee details table
    if (filteredFees.length) {
      bodyParts.push(`<div class="mb-3">
        <span class="text-xs font-semibold text-slate-500 uppercase">Fee Information</span>
        <table class="data-table mt-1"><thead><tr><th>Course</th><th>Amount</th><th>Type</th><th>Notes</th></tr></thead><tbody>
        ${filteredFees.map(f => `<tr>
          <td>${h(f.course || '-')}</td>
          <td class="font-semibold">${h(f.amount || '-')}</td>
          <td><span class="badge badge-slate">${h((f.fee_type || 'not_specified').replace(/_/g, ' '))}</span></td>
          <td class="text-xs text-slate-500">${h(f.additional_info || '-')}</td>
        </tr>`).join('')}
        </tbody></table>
      </div>`);
    }

    // Placement details
    const pd = inst.placement_details || {};
    const hasPlacement = pd.highest_package !== 'not_mentioned' || pd.average_package !== 'not_mentioned' ||
                         pd.placement_percentage !== 'not_mentioned' || (pd.top_recruiters?.length) || (pd.sectors?.length);
    if (hasPlacement) {
      bodyParts.push(`<div class="mb-3">
        <span class="text-xs font-semibold text-slate-500 uppercase">Placement Data</span>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-2 mt-1">
          ${pd.highest_package !== 'not_mentioned' ? `<div class="card-sm bg-green-50"><div class="text-xs text-slate-500">Highest Package</div><div class="text-sm font-bold text-green-700">${h(pd.highest_package)}</div></div>` : ''}
          ${pd.average_package !== 'not_mentioned' ? `<div class="card-sm bg-blue-50"><div class="text-xs text-slate-500">Average Package</div><div class="text-sm font-bold text-blue-700">${h(pd.average_package)}</div></div>` : ''}
          ${pd.placement_percentage !== 'not_mentioned' ? `<div class="card-sm bg-purple-50"><div class="text-xs text-slate-500">Placement %</div><div class="text-sm font-bold text-purple-700">${h(pd.placement_percentage)}</div></div>` : ''}
          ${pd.top_recruiters?.length ? `<div class="card-sm bg-amber-50"><div class="text-xs text-slate-500">Top Recruiters</div><div class="text-sm font-semibold text-amber-700">${pd.top_recruiters.map(h).join(', ')}</div></div>` : ''}
        </div>
      </div>`);
    }

    // Pitch points
    const INITIAL_PP = 3;
    const ppToShow = filteredPP.slice(0, INITIAL_PP);
    const hasMorePP = filteredPP.length > INITIAL_PP;
    const uid = `usp-${i}`;

    if (filteredPP.length) {
      bodyParts.push(`<div class="mb-2">
        <span class="text-xs font-semibold text-slate-500 uppercase">Pitch Points from Counsellors</span>
        <div class="space-y-2 mt-1" id="${uid}-pp-list">
          ${ppToShow.map(pp => renderPitchPoint(pp)).join('')}
        </div>
        ${hasMorePP ? `<div id="${uid}-pp-toggle"><button class="text-sm text-emerald-600 hover:text-emerald-800 font-medium mt-2 cursor-pointer" onclick="event.stopPropagation();toggleUSPPitchPoints('${uid}', ${i})">▼ Show ${filteredPP.length - INITIAL_PP} more pitch points</button></div>` : ''}
      </div>`);
    }

    card.innerHTML = headerHTML + `<div class="usp-card-body hidden">${bodyParts.join('')}</div>`;
    container.appendChild(card);
  });
}

function toggleUSPCard(headerEl) {
  const card = headerEl.closest('.usp-card-collapsible');
  const body = card.querySelector('.usp-card-body');
  const chevron = card.querySelector('.usp-chevron');
  body.classList.toggle('hidden');
  chevron.textContent = body.classList.contains('hidden') ? '▶' : '▼';
}

function renderPitchPoint(pp) {
  const catColors = {
    placement: 'badge-green', fee: 'badge-amber', scholarship: 'badge-amber',
    infrastructure: 'badge-indigo', ranking: 'badge-indigo', accreditation: 'badge-indigo',
    admission_process: 'badge-slate', hostel: 'badge-slate', location_advantage: 'badge-slate',
    industry_tie_up: 'badge-green', faculty: 'badge-indigo', alumni: 'badge-indigo',
  };
  const badgeClass = catColors[pp.category] || 'badge-slate';
  const transcriptLink = pp.source_call
    ? `<a href="#" onclick="event.preventDefault();event.stopPropagation();openTranscript('${(pp.source_call || '').replace(/'/g, "\\'")}')" class="text-indigo-500 hover:text-indigo-700 ml-1" title="Listen to source call">🎧</a>`
    : '';
  return `<div class="pl-3 border-l-2 border-emerald-200">
    <div class="flex items-start gap-2">
      <span class="badge ${badgeClass} mt-0.5">${h((pp.category || 'other').replace(/_/g, ' '))}</span>
      <div class="text-sm text-slate-700 font-medium flex-1">${h(pp.claim)}${transcriptLink}</div>
    </div>
    ${pp.counsellor_quote_hindi ? `<div class="quote text-xs mt-1">"${h(pp.counsellor_quote_hindi)}"</div>` : ''}
    ${pp.translation ? `<div class="translation text-xs">→ ${h(pp.translation)}</div>` : ''}
  </div>`;
}

function toggleUSPPitchPoints(uid, idx) {
  const listEl = document.getElementById(`${uid}-pp-list`);
  const toggleEl = document.getElementById(`${uid}-pp-toggle`);
  const isExpanded = toggleEl.dataset.expanded === '1';
  const inst = uspEntries[idx];
  const pp = inst.pitch_points;
  const INITIAL_PP = 3;

  if (isExpanded) {
    listEl.innerHTML = pp.slice(0, INITIAL_PP).map(p => renderPitchPoint(p)).join('');
    toggleEl.innerHTML = `<button class="text-sm text-emerald-600 hover:text-emerald-800 font-medium mt-2 cursor-pointer" onclick="event.stopPropagation();toggleUSPPitchPoints('${uid}', ${idx})">▼ Show ${pp.length - INITIAL_PP} more pitch points</button>`;
    toggleEl.dataset.expanded = '0';
  } else {
    listEl.innerHTML = pp.map(p => renderPitchPoint(p)).join('');
    toggleEl.innerHTML = `<button class="text-sm text-emerald-600 hover:text-emerald-800 font-medium mt-2 cursor-pointer" onclick="event.stopPropagation();toggleUSPPitchPoints('${uid}', ${idx})">▲ Collapse (${pp.length} shown)</button>`;
    toggleEl.dataset.expanded = '1';
  }
}

/* ==================================================================== */
/*  DEEP DIVE INSIGHTS TAB                                               */
/* ==================================================================== */
function initDeepDive() {
  const dd = D.deep_dive || {};
  const urg = dd.urgency_analysis || {};

  // Urgency types donut
  const urgTypes = urg.urgency_types || {};
  if (Object.keys(urgTypes).length) {
    chartDonut('chart-urg-types', urgTypes, 'Urgency Type Breakdown');
  }

  // Key finding + stats summary
  const uw = urg.with_urgency || {};
  const un = urg.without_urgency || {};
  const findingEl = $('#dd-urg-finding');
  let findingHTML = '';
  if (urg.key_finding) {
    findingHTML += `<div class="text-sm text-orange-800 bg-orange-50 border border-orange-100 rounded-lg px-4 py-3 mb-3">
      <strong>🔑 Key Finding:</strong> ${h(urg.key_finding)}</div>`;
  }
  findingHTML += `<div class="grid grid-cols-2 gap-3">
    <div class="card-sm bg-orange-50 text-center"><div class="text-xs text-slate-500">App Rate (With Urgency)</div><div class="text-lg font-bold text-orange-600">${uw.application_rate || 0}%</div><div class="text-xs text-slate-400">${uw.count || 0} calls</div></div>
    <div class="card-sm bg-slate-50 text-center"><div class="text-xs text-slate-500">App Rate (No Urgency)</div><div class="text-lg font-bold text-slate-500">${un.application_rate || 0}%</div><div class="text-xs text-slate-400">${un.count || 0} calls</div></div>
    <div class="card-sm bg-blue-50 text-center"><div class="text-xs text-slate-500">WhatsApp (With Urgency)</div><div class="text-lg font-bold text-blue-600">${uw.whatsapp_rate || 0}%</div></div>
    <div class="card-sm bg-slate-50 text-center"><div class="text-xs text-slate-500">WhatsApp (No Urgency)</div><div class="text-lg font-bold text-slate-500">${un.whatsapp_rate || 0}%</div></div>
  </div>`;
  findingEl.innerHTML = findingHTML;

  // Urgency examples with filter pills
  const allExamples = urg.urgency_examples || [];
  window._urgExamples = allExamples;
  window._activeUrgType = null;

  // Classify each example
  allExamples.forEach(ex => {
    const desc = ((ex.description || '') + ' ' + (ex.translation || '')).toLowerCase();
    if (['deadline','last date','closing','expire','ending','last day'].some(w => desc.includes(w))) ex._type = 'deadline';
    else if (['seat','limited','few left','filling','slot'].some(w => desc.includes(w))) ex._type = 'limited_seats';
    else if (['waive','free','discount','offer','scholarship','coupon'].some(w => desc.includes(w))) ex._type = 'fee_waiver_expiring';
    else if (['competition','demand','popular','rush','many student'].some(w => desc.includes(w))) ex._type = 'competition';
    else ex._type = 'other';
  });

  // Build pills
  const pillContainer = $('#dd-urg-pills');
  const typeLabels = { deadline: '📅 Deadline', limited_seats: '💺 Limited Seats', fee_waiver_expiring: '🎁 Fee Waiver/Offer', competition: '🏃 Competition', other: '📌 Other' };
  const typeCounts = {};
  allExamples.forEach(ex => { typeCounts[ex._type] = (typeCounts[ex._type] || 0) + 1; });

  // All pill
  const allPill = document.createElement('button');
  allPill.className = 'course-pill active';
  allPill.textContent = `All (${allExamples.length})`;
  allPill.addEventListener('click', () => { window._activeUrgType = null; $$('.urg-pill').forEach(p => p.classList.remove('active')); allPill.classList.add('active'); renderUrgExamples(); });
  allPill.classList.add('urg-pill');
  pillContainer.appendChild(allPill);

  Object.entries(typeLabels).forEach(([type, label]) => {
    const count = typeCounts[type] || 0;
    if (!count) return;
    const pill = document.createElement('button');
    pill.className = 'course-pill urg-pill';
    pill.textContent = `${label} (${count})`;
    pill.addEventListener('click', () => { window._activeUrgType = type; $$('.urg-pill').forEach(p => p.classList.remove('active')); pill.classList.add('active'); renderUrgExamples(); });
    pillContainer.appendChild(pill);
  });

  renderUrgExamples();
}

function renderUrgExamples() {
  const examples = window._urgExamples || [];
  const filter = window._activeUrgType;
  const filtered = filter ? examples.filter(ex => ex._type === filter) : examples;
  const exEl = $('#dd-urg-examples');

  exEl.innerHTML = filtered.map(ex => {
    const outcomeColor = ex.app_started ? 'badge-green' : 'badge-slate';
    return `<div class="pl-3 border-l-2 border-orange-200">
      <div class="text-sm text-slate-700 font-medium">${h(ex.description)}</div>
      <div class="quote text-xs mt-1">"${h(ex.quote)}"</div>
      <div class="translation text-xs">→ ${h(ex.translation)}</div>
      <div class="flex gap-2 mt-1">
        <span class="badge ${outcomeColor}">${h(ex.outcome.replace(/_/g, ' '))}</span>
        <span class="text-xs text-slate-400">— ${h(ex.counsellor)}</span>
        <a href="#" onclick="event.preventDefault();openTranscript('${ex.call_id.replace(/'/g, "\\'")}')" class="text-indigo-500 hover:text-indigo-700 text-xs">🎧 Listen</a>
      </div>
    </div>`;
  }).join('');
}

/* ==================================================================== */
/*  BOT PLAYBOOK TAB                                                     */
/* ==================================================================== */
function initPlaybook() {
  // Recommended call flow
  const flowContainer = $('#playbook-flow');
  const flow = D.call_flow || {};
  const phases = Object.keys(flow);
  flowContainer.innerHTML = phases.map((phase, i) => `
    <div class="flex items-start gap-3 mb-4">
      <div class="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm" style="background:${COLORS[i]}">${i+1}</div>
      <div>
        <h4 class="font-semibold text-slate-800">${h(phase)}</h4>
        <p class="text-sm text-slate-500">${flow[phase].pct}% of human calls include this phase</p>
      </div>
    </div>
  `).join('');

  // Top queries to handle
  const queryContainer = $('#playbook-queries');
  const buckets = D.query_buckets || {};
  queryContainer.innerHTML = Object.entries(buckets).slice(0, 8).map(([bucket, data]) => `
    <div class="card-sm bg-white border border-slate-100 mb-2">
      <div class="flex justify-between items-center">
        <span class="font-medium text-slate-800">${h(bucket)}</span>
        <span class="badge badge-indigo">${data.count} queries</span>
      </div>
      ${data.examples[0] ? `<div class="text-sm text-slate-500 mt-1">Example: "${h(data.examples[0].translation)}"</div>` : ''}
    </div>
  `).join('');

  // Top colleges
  const collegeContainer = $('#playbook-colleges');
  const colleges = D.colleges || {};
  collegeContainer.innerHTML = `<table class="data-table"><thead><tr><th>College</th><th>Mentions</th><th>Fee Range</th><th>Placements</th></tr></thead><tbody>
    ${Object.entries(colleges).slice(0, 15).map(([name, data]) => `<tr>
      <td class="font-medium">${h(name)}</td>
      <td>${data.count}</td>
      <td class="text-xs">${data.fees.slice(0,2).map(h).join(', ') || '-'}</td>
      <td class="text-xs">${data.placements.slice(0,2).map(h).join(', ') || '-'}</td>
    </tr>`).join('')}
  </tbody></table>`;

  // Bot learnings
  const learnings = D.bot_learnings || [];
  const learnContainer = $('#playbook-learnings');
  // Deduplicate & show top 20
  const unique = [...new Set(learnings)].slice(0, 25);
  learnContainer.innerHTML = unique.map(l => `
    <div class="flex items-start gap-2 mb-2">
      <span class="text-indigo-500 mt-0.5">→</span>
      <span class="text-sm text-slate-700">${h(l)}</span>
    </div>
  `).join('');
}

/* ==================================================================== */
/*  CHART HELPERS                                                        */
/* ==================================================================== */
function chartDonut(id, data, title) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const labels = Object.keys(data || {});
  const values = Object.values(data || {});
  new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: COLORS.slice(0, labels.length), borderWidth: 0 }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: { display: true, text: title, font: { size: 14, weight: '600' }, color: '#334155' },
        legend: { position: 'bottom', labels: { padding: 12, usePointStyle: true, font: { size: 11 } } }
      }
    }
  });
}

function chartBar(id, data, title) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const labels = Object.keys(data || {});
  const values = Object.values(data || {});
  new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: COLORS.slice(0, labels.length), borderRadius: 6, barPercentage: 0.7 }]
    },
    plugins: [ChartDataLabels],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: { display: true, text: title, font: { size: 14, weight: '600' }, color: '#334155' },
        legend: { display: false },
        datalabels: { anchor: 'end', align: 'end', font: { size: 11, weight: '600' }, color: '#475569' }
      },
      scales: {
        y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 11 } } },
        x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 45, minRotation: 0 } }
      }
    }
  });
}

function chartHBar(id, labels, values, title) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  const maxVal = Math.max(0, ...values);
  // Suggested max gives the datalabels at end-of-bar room to render.
  const suggestedMax = maxVal > 0 ? Math.ceil(maxVal * 1.12) : 1;
  new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: COLORS.slice(0, labels.length), borderRadius: 6, barPercentage: 0.7 }]
    },
    plugins: [ChartDataLabels],
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      layout: { padding: { right: 40, left: 4 } },
      plugins: {
        title: { display: true, text: title, font: { size: 14, weight: '600' }, color: '#334155' },
        legend: { display: false },
        datalabels: {
          anchor: 'end', align: 'end', clamp: true, clip: false,
          font: { size: 11, weight: '600' }, color: '#475569'
        }
      },
      scales: {
        x: { beginAtZero: true, suggestedMax, grid: { color: '#f1f5f9' }, ticks: { font: { size: 11 } } },
        y: { grid: { display: false }, ticks: { font: { size: 11 }, autoSkip: false } }
      }
    }
  });
}

/* ---- Render helpers for example items (with transcript link) ---- */
function callLink(callId) {
  return `<a href="#" onclick="event.preventDefault();openTranscript('${callId.replace(/'/g, "\\'") }')" class="text-indigo-500 hover:text-indigo-700 text-xs font-medium ml-2">📞 View call transcript</a>`;
}

function renderBucketExample(ex) {
  return `<div class="pl-2">
    <div class="text-sm text-slate-700">📌 ${h(ex.query)}</div>
    <div class="quote">"${h(ex.quote)}"</div>
    <div class="translation">→ ${h(ex.translation)}</div>
    <div class="text-xs text-slate-400 mt-1">— ${h(ex.counsellor)} ${callLink(ex.call_id)}</div>
  </div>`;
}

function renderTacticExample(ex) {
  return `<div class="pl-2">
    <div class="text-sm text-slate-600">${h(ex.description)}</div>
    <div class="quote">"${h(ex.quote)}"</div>
    <div class="translation">→ ${h(ex.translation)}</div>
    <div class="text-xs text-slate-400 mt-1">— ${h(ex.counsellor)} ${callLink(ex.call_id)}</div>
  </div>`;
}

function renderObjExample(ex) {
  return `<div class="pl-2 border-l-2 ${ex.resolved ? 'border-green-300' : 'border-red-300'}">
    <div class="text-sm text-slate-600 mb-1"><strong>Objection:</strong> ${h(ex.objection)}</div>
    <div class="text-sm text-slate-600 mb-1"><strong>Handling:</strong> ${h(ex.handling)}</div>
    <div class="quote text-red-700">"${h(ex.student_quote)}"</div>
    <div class="quote text-indigo-700">"${h(ex.counsellor_quote)}"</div>
    <div class="text-xs text-slate-400 mt-1">${ex.resolved ? '✅ Resolved' : '❌ Unresolved'} — ${h(ex.counsellor)} ${callLink(ex.call_id)}</div>
  </div>`;
}

function renderToggleBtn(uid, type, idx, moreCount) {
  return `<div class="toggle-wrap" id="${uid}-toggle"><button class="text-sm text-indigo-600 hover:text-indigo-800 font-medium mt-2 cursor-pointer" onclick="toggleExamples('${uid}', '${type}', ${idx})">▼ Show ${moreCount} more examples</button></div>`;
}

/* ---- Toggle "Show more / Show less" for example cards ---- */
function toggleExamples(uid, type, idx) {
  const listEl = document.getElementById(`${uid}-list`);
  const toggleWrap = document.getElementById(`${uid}-toggle`);
  const cardEl = document.getElementById(`${uid}-card`);
  const isExpanded = toggleWrap.dataset.expanded === '1';
  const INITIAL = 3;

  const renderers = {
    bucket:    () => Object.values(D.query_buckets)[idx],
    tactic:    () => Object.values(D.tactics)[idx],
    objection: () => Object.values(D.objections)[idx],
  };
  const renderFns = {
    bucket:    renderBucketExample,
    tactic:    renderTacticExample,
    objection: renderObjExample,
  };

  const data = renderers[type]();
  const renderFn = renderFns[type];
  const moreCount = data.examples.length - INITIAL;

  if (isExpanded) {
    // Collapse — remove top collapse button if present
    const topCollapse = document.getElementById(`${uid}-top-collapse`);
    if (topCollapse) topCollapse.remove();
    listEl.innerHTML = data.examples.slice(0, INITIAL).map(renderFn).join('');
    toggleWrap.innerHTML = `<button class="text-sm text-indigo-600 hover:text-indigo-800 font-medium mt-2 cursor-pointer" onclick="toggleExamples('${uid}', '${type}', ${idx})">▼ Show ${moreCount} more examples</button>`;
    toggleWrap.dataset.expanded = '0';
    // Scroll card into view so user isn't stranded at bottom
    cardEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } else {
    // Expand — show all + collapse buttons at top AND bottom
    listEl.innerHTML = data.examples.map(renderFn).join('');
    const collapseBtn = `<button class="text-sm text-indigo-600 hover:text-indigo-800 font-medium cursor-pointer" onclick="toggleExamples('${uid}', '${type}', ${idx})">▲ Collapse (${data.examples.length} shown)</button>`;
    toggleWrap.innerHTML = `<div class="flex justify-between items-center mt-2">${collapseBtn}</div>`;
    // Also add a collapse button at the top of the list
    listEl.insertAdjacentHTML('beforebegin',
      `<div id="${uid}-top-collapse" class="mb-2">${collapseBtn}</div>`);
    toggleWrap.dataset.expanded = '1';
  }
}

/* ==================================================================== */
/*  USERS TAB                                                            */
/* ==================================================================== */
let usersData = [];
let usersExpanded = new Set();

function initUsers() {
  usersData = (D.users || []).slice();

  // Top stats
  const total = usersData.length;
  const multi = usersData.filter(u => u.call_count >= 2).length;
  const totalCalls = usersData.reduce((s, u) => s + u.call_count, 0);
  const maxCalls = usersData.reduce((m, u) => Math.max(m, u.call_count), 0);
  $('#users-stat-total').textContent = fmt(total);
  $('#users-stat-multi').textContent = fmt(multi);
  $('#users-stat-avg').textContent = total ? (totalCalls / total).toFixed(1) : '0';
  $('#users-stat-max').textContent = fmt(maxCalls);

  // Stage filter dropdown — populate from all stages seen
  const stageSet = new Set();
  usersData.forEach(u => (u.stages || []).forEach(s => stageSet.add(s)));
  const stageSel = $('#users-stage-filter');
  [...stageSet].sort().forEach(s => {
    const opt = document.createElement('option');
    opt.value = s; opt.textContent = s;
    stageSel.appendChild(opt);
  });

  // Sort state (default: most calls desc)
  let sortField = 'call_count', sortDir = 'desc';
  document.querySelectorAll('th[data-usort]').forEach(th => {
    th.addEventListener('click', () => {
      const f = th.dataset.usort;
      if (sortField === f) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
      else { sortField = f; sortDir = 'desc'; }
      render();
    });
  });

  $('#users-stage-filter').addEventListener('change', render);
  $('#users-mincalls-filter').addEventListener('change', render);
  $('#users-search').addEventListener('input', render);

  function render() {
    const stage = $('#users-stage-filter').value;
    const minCalls = parseInt($('#users-mincalls-filter').value) || 1;
    const q = ($('#users-search').value || '').toLowerCase();

    let filtered = usersData.filter(u => {
      if (u.call_count < minCalls) return false;
      if (stage) {
        // Match latest_stage OR any stage in the user's history
        if (u.latest_stage !== stage && !(u.stages || []).includes(stage)) return false;
      }
      if (q) {
        const blob = [
          u.user_id, u.mobile, ...(u.counsellors || []), ...(u.courses || []),
          ...(u.outcomes || []), u.latest_stage,
        ].join(' ').toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });

    // Sort
    filtered = [...filtered].sort((a, b) => {
      const va = a[sortField] ?? '', vb = b[sortField] ?? '';
      if (typeof va === 'number' && typeof vb === 'number') {
        return sortDir === 'asc' ? va - vb : vb - va;
      }
      const sa = String(va), sb = String(vb);
      if (sa < sb) return sortDir === 'asc' ? -1 : 1;
      if (sa > sb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    $('#users-count').textContent = `${filtered.length} users`;

    const tbody = $('#users-tbody');
    tbody.innerHTML = '';

    // Build a quick lookup of call objects by id from D.call_list
    const callMap = {};
    (D.call_list || []).forEach(c => { callMap[c.id] = c; });

    filtered.forEach(u => {
      const key = u.user_id || ('mob:' + u.mobile);
      const isOpen = usersExpanded.has(key);

      const stagesPills = (u.stages || []).slice(0, 4).map(s =>
        `<span class="badge badge-slate text-xs">${h(s)}</span>`).join(' ');
      const stageBadge = u.latest_stage && u.latest_stage !== 'Unknown'
        ? `<span class="badge badge-cyan">${h(u.latest_stage)}</span>` : '<span class="text-slate-400 text-xs">—</span>';

      const tr = document.createElement('tr');
      tr.className = 'cursor-pointer hover:bg-cyan-50';
      tr.onclick = () => {
        if (usersExpanded.has(key)) usersExpanded.delete(key);
        else usersExpanded.add(key);
        render();
      };
      tr.innerHTML = `
        <td class="font-bold text-cyan-700">${isOpen ? '▼' : '▶'} ${u.call_count}</td>
        <td class="text-xs font-mono">${h(u.user_id || '—')}</td>
        <td class="text-xs">${h(u.mobile || '—')}</td>
        <td>${mins(u.total_duration)}</td>
        <td>${stageBadge} <div class="mt-1 flex flex-wrap gap-1">${stagesPills}</div></td>
        <td class="text-xs">${(u.counsellors || []).slice(0,3).map(h).join(', ')}${u.counsellors.length>3?'…':''}</td>
        <td class="text-xs whitespace-nowrap">${h(u.latest_date || '—')}<div class="text-slate-400">${h(u.earliest_date || '')}</div></td>
        <td class="text-xs">${(u.outcomes || []).slice(0,2).map(o => `<span class="badge badge-slate">${h(o.replace(/_/g,' '))}</span>`).join(' ')}</td>`;
      tbody.appendChild(tr);

      if (isOpen) {
        const detail = document.createElement('tr');
        detail.className = 'bg-cyan-50/50';
        const sortedCalls = (u.call_ids || []).map(id => callMap[id]).filter(Boolean)
          .sort((a, b) => (a.created_on || '').localeCompare(b.created_on || ''));
        detail.innerHTML = `<td colspan="8" class="p-3">
          <div class="text-xs font-semibold text-cyan-900 mb-2 uppercase">All ${sortedCalls.length} transcripts (oldest first) — click to open</div>
          <div class="overflow-x-auto"><table class="data-table">
            <thead><tr>
              <th>Date · Time</th><th>Counsellor</th><th>Stage</th><th>Duration</th>
              <th>Course</th><th>Outcome</th><th>Summary</th>
            </tr></thead>
            <tbody>${sortedCalls.map(c => `
              <tr class="cursor-pointer related-call-row" data-call-id="${h(c.id)}">
                <td class="text-xs whitespace-nowrap">${h(fmtDateTime(c.created_on) || c.created_date || '—')}</td>
                <td class="text-xs">${h(c.counsellor)}</td>
                <td><span class="badge badge-slate">${h(c.stage)}</span></td>
                <td>${mins(c.duration)}</td>
                <td class="text-xs">${h(c.course)}</td>
                <td class="text-xs"><span class="badge badge-indigo">${h((c.outcome||'').replace(/_/g,' '))}</span></td>
                <td class="text-xs text-slate-600 max-w-md truncate">${h(c.summary || '')}</td>
              </tr>`).join('')}
            </tbody>
          </table></div>
        </td>`;
        tbody.appendChild(detail);
        detail.querySelectorAll('.related-call-row').forEach(row => {
          row.addEventListener('click', (e) => {
            e.stopPropagation();
            openTranscript(row.dataset.callId);
          });
        });
      }
    });
  }

  render();
}

/* ---- Init on load ---- */
document.addEventListener('DOMContentLoaded', initTabs);
