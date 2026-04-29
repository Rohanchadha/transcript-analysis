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

/* ---- tab switching ---- */
function initTabs() {
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
      if (target === 'institutes' && !window._institutesInit) { initInstitutes(); window._institutesInit = true; }
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

  const container = $('#bucket-cards');
  container.innerHTML = '';
  labels.forEach((bucket, i) => {
    const data = buckets[bucket];
    const INITIAL = 3;
    const hasMore = data.examples.length > INITIAL;
    const uid = `bucket-${i}`;
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
      ${hasMore ? renderToggleBtn(uid, 'bucket', i, data.examples.length - INITIAL) : ''}`;
    container.appendChild(card);
  });
}

/* ==================================================================== */
/*  TACTICS TAB                                                          */
/* ==================================================================== */
function initTactics() {
  const tactics = D.tactics || {};
  const labels = Object.keys(tactics);
  const counts = labels.map(l => tactics[l].count);

  chartHBar('chart-tactics', labels, counts, 'Tactic Usage (# of calls)');

  const container = $('#tactic-cards');
  container.innerHTML = '';

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

  labels.forEach((tactic, i) => {
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

  // Example cards
  const container = $('#objection-cards');
  container.innerHTML = '';

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

  labels.forEach((objType, i) => {
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
  renderExplorerTable(explorerData);

  // search
  $('#explorer-search').addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    const filtered = explorerData.filter(c =>
      c.counsellor.toLowerCase().includes(q) ||
      c.course.toLowerCase().includes(q) ||
      c.summary.toLowerCase().includes(q) ||
      c.team.toLowerCase().includes(q) ||
      c.stage.toLowerCase().includes(q) ||
      (c.buckets || []).join(' ').toLowerCase().includes(q)
    );
    renderExplorerTable(filtered);
  });
}

function renderExplorerTable(data) {
  const tbody = $('#explorer-tbody');
  tbody.innerHTML = '';
  $('#explorer-count').textContent = `${data.length} calls`;

  data.forEach(c => {
    const outcomeBadge = c.outcome === 'application_started' ? 'badge-green' :
                         c.outcome.includes('interested') ? 'badge-indigo' :
                         c.outcome.includes('callback') ? 'badge-amber' : 'badge-slate';
    const tr = document.createElement('tr');
    tr.className = 'cursor-pointer';
    tr.onclick = () => openTranscript(c.id);
    tr.innerHTML = `
      <td class="font-medium">${h(c.counsellor)}</td>
      <td>${h(c.course)}</td>
      <td>${mins(c.duration)}</td>
      <td>${c.total_turns}</td>
      <td><span class="badge badge-slate">${h(c.stage)}</span></td>
      <td><span class="badge ${outcomeBadge}">${h(c.outcome.replace(/_/g,' '))}</span></td>
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

    let html = '';

    // Meta header
    if (meta) {
      html += `<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div class="card-sm bg-slate-50"><div class="stat-label">Counsellor</div><div class="text-sm font-semibold">${h(meta.counsellor_name)}</div></div>
        <div class="card-sm bg-slate-50"><div class="stat-label">Duration</div><div class="text-sm font-semibold">${mins(meta.duration)}</div></div>
        <div class="card-sm bg-slate-50"><div class="stat-label">Stage</div><div class="text-sm font-semibold">${h(meta.stage_name)}</div></div>
        <div class="card-sm bg-slate-50"><div class="stat-label">Team</div><div class="text-sm font-semibold">${h(meta.team_name)}</div></div>
      </div>`;
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

      // Tactics used
      html += `<div class="mb-4"><h4 class="font-semibold text-slate-800 mb-2">Tactics Used</h4>
        <div class="flex flex-wrap gap-1">${an.counsellor_tactics.map(t => `<span class="badge badge-indigo">${h(t.tactic)}</span>`).join('')}</div>
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

    // Full transcript
    if (t?.turns) {
      html += `<div class="card"><h4 class="font-semibold text-slate-800 mb-3">Full Transcript</h4>
        <div class="space-y-1">
        ${t.turns.map(turn => `
          <div class="turn turn-${turn.speaker.toLowerCase()}">
            <span class="turn-time">[${turn.start_time}]</span>
            <span class="turn-speaker">${turn.speaker}:</span>
            <span class="turn-text">${h(turn.text)}</span>
          </div>
        `).join('')}
        </div></div>`;
    }

    body.innerHTML = html;
  } catch (err) {
    body.innerHTML = `<p class="text-red-500">Error loading transcript: ${h(err.message)}</p>`;
  }
}

function closeModal() {
  $('#transcript-modal').classList.add('hidden');
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
      plugins: {
        title: { display: true, text: title, font: { size: 14, weight: '600' }, color: '#334155' },
        legend: { display: false },
        datalabels: { anchor: 'end', align: 'end', font: { size: 11, weight: '600' }, color: '#475569' }
      },
      scales: {
        x: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 11 } } },
        y: { grid: { display: false }, ticks: { font: { size: 11 } } }
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

/* ---- Init on load ---- */
document.addEventListener('DOMContentLoaded', initTabs);
