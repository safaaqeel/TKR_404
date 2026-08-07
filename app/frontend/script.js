/* ==========================================================================
   VigilAI — Application Script
   Modular vanilla JS. Sections:
   1. State & config          5. Widgets: check-in form
   2. Utilities                6. Widgets: simulator
   3. API layer (fetch)        7. Charts
   4. Navigation & shell UI    8. Init
   ========================================================================== */

(() => {
  'use strict';

  /* ------------------------------------------------------------------ *
   * 1. STATE & CONFIG
   * ------------------------------------------------------------------ */
  const API_BASE = '/api';

  const ENDPOINTS = {
    dashboard: `${API_BASE}/dashboard`,
    checkin: `${API_BASE}/checkin`,
    recommendations: `${API_BASE}/recommendations`,
    reports: `${API_BASE}/reports`,
    agents: `${API_BASE}/agents`,
    risk: `${API_BASE}/risk`,
    simulator: `${API_BASE}/simulator`,
    documents: `${API_BASE}/documents`,
    upload: `${API_BASE}/upload`,
    history: `${API_BASE}/history`,
    profile: `${API_BASE}/profile`,
  };

  const state = {
    theme: localStorage.getItem('vigilai-theme') || 'light',
    sidebarCollapsed: false,
    checkinDraft: {},
  };

  /* ------------------------------------------------------------------ *
   * 2. UTILITIES
   * ------------------------------------------------------------------ */
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  function formatCurrency(n) {
    if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`;
    if (n >= 1000) return `₹${(n / 1000).toFixed(1)}K`;
    return `₹${n}`;
  }

  function showToast(message, duration = 2600) {
    const toast = $('#toast');
    toast.textContent = message;
    toast.hidden = false;
    requestAnimationFrame(() => toast.classList.add('is-visible'));
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { toast.hidden = true; }, duration);
  }

  function openModal(title, bodyHtml) {
    $('#modalTitle').textContent = title;
    $('#modalBody').innerHTML = bodyHtml;
    $('#modalBackdrop').hidden = false;
    $('#modalCloseBtn').focus();
  }
  function closeModal() { $('#modalBackdrop').hidden = true; }

  /* ------------------------------------------------------------------ *
   * 3. API LAYER
   * Every call gracefully falls back to bundled sample data if the
   * FastAPI backend is unreachable, so the UI stays fully demoable.
   * ------------------------------------------------------------------ */
  async function apiGet(url, fallback) {
    try {
      const res = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn(`[VigilAI] Falling back to sample data for ${url}`, err.message);
      return fallback;
    }
  }

  async function apiPost(url, payload) {
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn(`[VigilAI] POST to ${url} failed, treated as offline demo`, err.message);
      return { ok: true, offline: true };
    }
  }

  /* ------------------------------------------------------------------ *
   * SAMPLE / DEMO DATA (stand-in for FastAPI JSON responses)
   * ------------------------------------------------------------------ */
  const SAMPLE = {
    notifications: [
      { id: 1, type: 'risk', icon: '⚠', title: 'Cash flow risk rising', body: 'Distress risk moved from 27% to 31% this week.', time: '12m ago', tone: 'red' },
      { id: 2, type: 'scheme', icon: '🏛', title: 'New scheme available', body: 'MSME Credit Guarantee Scheme match found.', time: '1h ago', tone: 'green' },
      { id: 3, type: 'supplier', icon: '🚚', title: 'Supplier delay flagged', body: 'Vendor "Anand Fabrics" reported a 3-day delay.', time: '3h ago', tone: 'amber' },
      { id: 4, type: 'inventory', icon: '📦', title: 'Inventory warning', body: '2 SKUs projected to stock out within 9 days.', time: 'Yesterday', tone: 'amber' },
    ],
    recommendations: [
      { id: 1, priority: 'High', problem: 'Receivables aging past 45 days', cause: 'Two key clients delayed payment cycles', action: 'Introduce a 2% early-payment discount and automate reminders', improvement: '+₹1.8L liquidity', time: '2 weeks' },
      { id: 2, priority: 'High', problem: 'Inventory concentration risk', cause: '68% of stock value sits in 3 SKUs', action: 'Diversify purchasing across 2 additional suppliers', improvement: '−22% stockout risk', time: '1 month' },
      { id: 3, priority: 'Medium', problem: 'Rising customer acquisition cost', cause: 'Ad spend up 30% with flat conversion', action: 'Reallocate budget toward referral incentives', improvement: '−15% CAC', time: '3 weeks' },
      { id: 4, priority: 'Medium', problem: 'Thin cash buffer', cause: 'Average 9 days of operating expenses on hand', action: 'Set aside 5% of weekly revenue into a reserve account', improvement: '+18 days runway', time: '6 weeks' },
      { id: 5, priority: 'Low', problem: 'Manual attendance tracking', cause: 'Paper registers slow payroll processing', action: 'Adopt a low-cost biometric or app-based tracker', improvement: '4 hrs/week saved', time: '1 week' },
      { id: 6, priority: 'Low', problem: 'Underused loyalty program', cause: 'Only 12% of repeat customers enrolled', action: 'Prompt enrollment at checkout with a small incentive', improvement: '+8% repeat rate', time: '2 weeks' },
    ],
    agents: [
      { name: 'CEO Agent', color: '#2952E3', icon: '◆', status: 'Active', confidence: 88, recommendation: 'Prioritize receivables recovery before new hiring', reasoning: 'Cash runway is the binding constraint this quarter; growth moves should wait 6–8 weeks.', risk: 'Moderate' },
      { name: 'CFO Agent', color: '#1FAE6E', icon: '₹', status: 'Active', confidence: 91, recommendation: 'Delay machinery purchase by one quarter', reasoning: 'Current debt-service ratio leaves limited buffer for new fixed costs.', risk: 'Moderate' },
      { name: 'Marketing Agent', color: '#E68A1C', icon: '◎', status: 'Active', confidence: 74, recommendation: 'Shift 20% of ad spend to referral program', reasoning: 'Referral-driven customers show 1.6x higher lifetime value in your segment.', risk: 'Low' },
      { name: 'Operations Agent', color: '#3DDCEE', icon: '⚙', status: 'Active', confidence: 82, recommendation: 'Diversify supplier base for top 3 SKUs', reasoning: 'Single-supplier dependency has caused 2 delays in the last 30 days.', risk: 'Moderate' },
      { name: 'Risk Agent', color: '#E14B4B', icon: '⚠', status: 'Active', confidence: 95, recommendation: 'Escalate distress risk monitoring to daily', reasoning: 'Risk score crossed the 30% moderate threshold this week.', risk: 'High' },
      { name: 'Compliance Agent', color: '#7C5CE0', icon: '⚖', status: 'Active', confidence: 97, recommendation: 'File GST return before the 3-day deadline', reasoning: 'Filing history shows two near-miss late filings this year.', risk: 'Low' },
      { name: 'Strategy Agent', color: '#0EA5A0', icon: '♟', status: 'Active', confidence: 68, recommendation: 'Evaluate entry into the wholesale export segment', reasoning: 'Market opportunity score for exports rose 14 points this month.', risk: 'Low' },
      { name: 'Government Policy Agent', color: '#B45309', icon: '🏛', status: 'Active', confidence: 85, recommendation: 'Apply for the MSME Credit Guarantee Scheme', reasoning: 'Business profile matches 4 of 5 eligibility criteria.', risk: 'Low' },
    ],
    recovery: [
      { title: 'Stabilize receivables', body: 'Recover ₹1.8L in outstanding payments from top 4 clients within 3 weeks.' },
      { title: 'Trim discretionary spend', body: 'Pause non-essential purchases for 30 days to preserve cash buffer.' },
      { title: 'Renegotiate supplier terms', body: 'Extend payment terms from 15 to 30 days with two key suppliers.' },
      { title: 'Build a 30-day reserve', body: 'Allocate 5% of weekly revenue automatically into a reserve account.' },
      { title: 'Re-forecast monthly', body: 'Review recovery progress against target every 30 days with the CFO Agent.' },
    ],
    growth: [
      { id: 1, priority: 'High', problem: 'Untapped export demand', cause: 'Regional buyers sourcing similar goods from overseas', action: 'Pilot a small export shipment via an MSME trade facilitator', improvement: 'Est. +12% revenue', time: '2 months' },
      { id: 2, priority: 'Medium', problem: 'Underused e-commerce channel', cause: 'Only 6% of sales come from online storefronts', action: 'List top 10 SKUs on a regional marketplace', improvement: 'Est. +9% revenue', time: '3 weeks' },
      { id: 3, priority: 'Medium', problem: 'Idle weekday production capacity', cause: 'Machinery utilization at 58% on Tue–Thu', action: 'Offer contract manufacturing slots to nearby businesses', improvement: 'Est. +₹40K/mo', time: '1 month' },
    ],
    schemes: [
      { id: 1, priority: 'High', problem: 'Working capital shortage', cause: 'Eligible under MSME Credit Guarantee Scheme', action: 'Apply for collateral-free credit up to ₹2 Cr', improvement: 'Lower borrowing cost', time: '2–4 weeks' },
      { id: 2, priority: 'Medium', problem: 'Technology upgrade needed', cause: 'Eligible under CLCSS subsidy', action: 'Claim 15% capital subsidy on new machinery', improvement: '15% cost offset', time: '1–2 months' },
      { id: 3, priority: 'Low', problem: 'Export readiness', cause: 'Eligible under MSME export promotion scheme', action: 'Register for subsidized trade fair participation', improvement: 'Market access', time: '3 weeks' },
    ],
    kbRecent: [
      { title: 'Understanding your Business Pulse Score', meta: 'Guide · 4 min read' },
      { title: 'Q2 compliance checklist for MSMEs', meta: 'Checklist · Updated last week' },
    ],
    kbPolicy: [
      { title: 'MSME Credit Guarantee Scheme — overview', meta: 'Government policy' },
      { title: 'GST filing deadlines for FY 2026–27', meta: 'Government policy' },
    ],
    kbGuides: [
      { title: 'How to build a 90-day cash reserve', meta: 'Finance guide' },
      { title: 'Reducing supplier concentration risk', meta: 'Business guide' },
    ],
    faq: [
      { q: 'How often does VigilAI refresh my health score?', a: 'Your Business Health Score recalculates hourly using your latest check-ins, transactions and connected data sources.' },
      { q: 'Can I export data for my accountant?', a: 'Yes — visit Reports and download any report as PDF or Excel.' },
      { q: 'What happens if I miss a daily check-in?', a: 'Nothing breaks — VigilAI simply relies more heavily on connected transaction data until your next check-in.' },
    ],
    reports: [
      { title: 'Monthly Report', desc: 'Full operational and financial summary for the current month.', icon: '▤' },
      { title: 'Quarterly Report', desc: 'Trend analysis and distress indicators across the quarter.', icon: '▦' },
      { title: 'Risk Report', desc: 'Deep dive into financial distress drivers and mitigations.', icon: '⚠' },
      { title: 'Growth Report', desc: 'Opportunities, market signals and expansion readiness.', icon: '↗' },
    ],
  };

  /* ------------------------------------------------------------------ *
   * 4. NAVIGATION & SHELL UI
   * ------------------------------------------------------------------ */
  function navigateTo(pageId) {
    $$('.page').forEach(p => p.classList.toggle('is-active', p.dataset.page === pageId));
    $$('.nav-item[data-page]').forEach(n => n.classList.toggle('is-active', n.dataset.page === pageId));
    $('.app-shell').classList.remove('is-mobile-open');
    $('#sidebarOverlay').hidden = true;
    const heading = $(`#page-${pageId} h1`);
    if (heading) heading.setAttribute('tabindex', '-1'), heading.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function initNavigation() {
    $$('[data-page]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        navigateTo(el.dataset.page);
      });
    });
  }

  function initSidebarCollapse() {
    $('#sidebarCollapseBtn').addEventListener('click', () => {
      state.sidebarCollapsed = !state.sidebarCollapsed;
      $('#app-shell').classList.toggle('is-collapsed', state.sidebarCollapsed);
    });
    $('#mobileMenuBtn').addEventListener('click', () => {
      $('#app-shell').classList.add('is-mobile-open');
      $('#sidebarOverlay').hidden = false;
    });
    $('#sidebarOverlay').addEventListener('click', () => {
      $('#app-shell').classList.remove('is-mobile-open');
      $('#sidebarOverlay').hidden = true;
    });
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    $('#darkModeToggle').setAttribute('aria-pressed', String(theme === 'dark'));
    const settingsToggle = $('#settingsDarkToggle');
    if (settingsToggle) settingsToggle.checked = theme === 'dark';
    localStorage.setItem('vigilai-theme', theme);
    // Re-render charts so Chart.js grid/text colors match the new theme.
    renderAllCharts();
  }

  function initDarkMode() {
    applyTheme(state.theme);
    $('#darkModeToggle').addEventListener('click', () => {
      state.theme = state.theme === 'dark' ? 'light' : 'dark';
      applyTheme(state.theme);
    });
    $('#settingsDarkToggle')?.addEventListener('change', (e) => {
      state.theme = e.target.checked ? 'dark' : 'light';
      applyTheme(state.theme);
    });
  }

  function initDropdowns() {
    const pairs = [
      ['#notifBtn', '#notifPanel'],
      ['#profileBtn', '#profilePanel'],
    ];
    pairs.forEach(([btnSel, panelSel]) => {
      const btn = $(btnSel), panel = $(panelSel);
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = !panel.hidden;
        $$('.dropdown-panel').forEach(p => p.hidden = true);
        panel.hidden = isOpen;
        btn.setAttribute('aria-expanded', String(!isOpen));
      });
    });
    document.addEventListener('click', () => $$('.dropdown-panel').forEach(p => p.hidden = true));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { $$('.dropdown-panel').forEach(p => p.hidden = true); closeModal(); } });
  }

  function initModal() {
    $('#modalCloseBtn').addEventListener('click', closeModal);
    $('#modalBackdrop').addEventListener('click', (e) => { if (e.target === $('#modalBackdrop')) closeModal(); });
  }

  function initLogout() {
    ['#logoutBtn', '#logoutBtn2'].forEach(sel => {
      $(sel)?.addEventListener('click', (e) => {
        e.preventDefault();
        showToast('Logged out — redirecting to sign in…');
      });
    });
  }

  function initGlobalSearch() {
    const input = $('#globalSearch');
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement !== input) { e.preventDefault(); input.focus(); }
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && input.value.trim()) {
        showToast(`Searching for "${input.value.trim()}"…`);
      }
    });
  }

  /* ------------------------------------------------------------------ *
   * RENDER: notifications
   * ------------------------------------------------------------------ */
  function renderNotifications(list) {
    const html = list.map(n => `
      <li class="notif-item" role="menuitem" tabindex="0">
        <span class="notif-item__icon" style="background:var(--bg-surface-2)">${n.icon}</span>
        <span class="notif-item__body">
          <h4>${n.title}</h4>
          <p>${n.body}</p>
          <time>${n.time}</time>
        </span>
      </li>`).join('');
    $('#notifList').innerHTML = html;
    $('#dashNotifList').innerHTML = list.slice(0, 3).map(n => `
      <li><span class="dot dot--${n.tone}"></span><div><strong>${n.title}</strong><br><span class="meta">${n.time}</span></div></li>
    `).join('');
    $('#notifCount').textContent = list.length;
  }

  /* ------------------------------------------------------------------ *
   * RENDER: dashboard extras
   * ------------------------------------------------------------------ */
  function renderDashboardRecoSummary(recs) {
    $('#dashRecoList').innerHTML = recs.slice(0, 4).map(r => `
      <li><span class="dot dot--${r.priority === 'High' ? 'red' : r.priority === 'Medium' ? 'amber' : 'green'}"></span>
      <div><strong>${r.problem}</strong><br><span class="meta">${r.action}</span></div></li>
    `).join('');
  }

  function renderAiInsights() {
    const insights = [
      'Receivables recovery this week could add up to 18 days of runway.',
      'Inventory for SKU "Cotton Weave 210" projected to stock out in 9 days.',
      'A referral-focused campaign may lower acquisition cost by 15%.',
      'Compliance Agent flags a GST filing due in 3 days.',
    ];
    $('#aiInsightsList').innerHTML = insights.map(i => `<li><span class="dot dot--amber"></span><div>${i}</div></li>`).join('');
  }

  function renderHealthDetail() {
    const metrics = [
      ['Revenue Momentum', 74, 'green'], ['Cash Conversion Cycle', 58, 'amber'],
      ['Debt Service Coverage', 81, 'green'], ['Customer Concentration', 46, 'amber'],
      ['Working Capital Ratio', 69, 'green'], ['Expense Volatility', 33, 'red'],
    ];
    $('#healthDetailGrid').innerHTML = metrics.map(([name, score, tone]) => `
      <article class="card card--metric">
        <header class="card__header"><h3>${name}</h3><span class="badge badge--${tone}">${tone === 'green' ? 'Healthy' : tone === 'amber' ? 'Watch' : 'Action needed'}</span></header>
        <p class="metric-value">${score}<span>/100</span></p>
        <div class="mini-bar"><span style="width:${score}%"></span></div>
      </article>`).join('');
  }

  /* ------------------------------------------------------------------ *
   * RENDER: recommendations / growth / schemes (shared)
   * ------------------------------------------------------------------ */
  function recoCardHtml(r) {
    const tone = r.priority === 'High' ? 'red' : r.priority === 'Medium' ? 'amber' : 'green';
    return `
      <article class="reco-card" data-priority="${r.priority}">
        <div class="reco-card__top"><h4>${r.problem}</h4><span class="badge badge--${tone}">${r.priority}</span></div>
        <dl>
          <dt>Root cause</dt><dd>${r.cause}</dd>
          <dt>Action</dt><dd>${r.action}</dd>
        </dl>
        <div class="reco-card__footer"><span>${r.improvement}</span><span>${r.time}</span></div>
      </article>`;
  }

  function renderRecommendations(list, filter = 'all') {
    const filtered = filter === 'all' ? list : list.filter(r => r.priority === filter);
    $('#recoGrid').innerHTML = filtered.map(recoCardHtml).join('') || '<p class="metric-caption">No recommendations at this priority.</p>';
  }

  function initRecoFilters(list) {
    $$('.filter-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        $$('.filter-tab').forEach(t => { t.classList.remove('is-active'); t.setAttribute('aria-selected', 'false'); });
        tab.classList.add('is-active'); tab.setAttribute('aria-selected', 'true');
        renderRecommendations(list, tab.dataset.priority);
      });
    });
  }

  /* ------------------------------------------------------------------ *
   * RENDER: AI Decision Board
   * ------------------------------------------------------------------ */
  function renderAgents(agents) {
    $('#agentGrid').innerHTML = agents.map(a => `
      <article class="agent-card" style="--agent-color:${a.color}">
        <div class="agent-card__head">
          <span class="agent-card__avatar">${a.icon}</span>
          <div><div class="agent-card__name">${a.name}</div><div class="agent-card__status">● ${a.status}</div></div>
        </div>
        <div class="confidence-row"><span>Confidence</span><span class="confidence-track"><span class="confidence-fill" style="width:${a.confidence}%"></span></span><span>${a.confidence}%</span></div>
        <p class="agent-card__reco">${a.recommendation}</p>
        <p class="agent-card__reason">${a.reasoning}</p>
        <span class="badge badge--outline">Risk: ${a.risk}</span>
      </article>`).join('');
  }

  /* ------------------------------------------------------------------ *
   * RENDER: recovery, reports, knowledge base
   * ------------------------------------------------------------------ */
  function renderRecovery(steps) {
    $('#recoverySteps').innerHTML = steps.map(s => `<li><div><h4>${s.title}</h4><p>${s.body}</p></div></li>`).join('');
  }

  function renderReports(reports) {
    $('#reportsGrid').innerHTML = reports.map(r => `
      <article class="report-card">
        <span class="report-card__icon">${r.icon}</span>
        <h4>${r.title}</h4>
        <p>${r.desc}</p>
        <div class="report-card__actions">
          <button class="btn btn--ghost" data-export="pdf" data-title="${r.title}">PDF</button>
          <button class="btn btn--ghost" data-export="xlsx" data-title="${r.title}">Excel</button>
        </div>
      </article>`).join('');
    $$('#reportsGrid [data-export]').forEach(btn => {
      btn.addEventListener('click', () => showToast(`Preparing "${btn.dataset.title}" as ${btn.dataset.export.toUpperCase()}…`));
    });
  }

  function renderKnowledgeBase() {
    const docItem = (d) => `<li class="kb-doc-item" tabindex="0" data-title="${d.title}"><span class="kb-doc-item__icon">📄</span><div><h5>${d.title}</h5><span>${d.meta}</span></div></li>`;
    $('#kbRecentList').innerHTML = SAMPLE.kbRecent.map(docItem).join('');
    $('#kbPolicyList').innerHTML = SAMPLE.kbPolicy.map(docItem).join('');
    $('#kbGuideList').innerHTML = SAMPLE.kbGuides.map(docItem).join('');
    $('#faqList').innerHTML = SAMPLE.faq.map(f => `<details class="faq-item"><summary>${f.q}</summary><p>${f.a}</p></details>`).join('');

    $$('.kb-doc-item').forEach(item => {
      const open = () => {
        $('#kbPreview').innerHTML = `<h3>${item.dataset.title}</h3><p style="margin-top:10px;color:var(--text-secondary);font-size:.85rem;line-height:1.6;">Preview content for “${item.dataset.title}” would load here from <code>/api/documents</code>.</p>`;
      };
      item.addEventListener('click', open);
      item.addEventListener('keydown', (e) => { if (e.key === 'Enter') open(); });
    });

    $('#kbSearch').addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      $$('.kb-doc-item').forEach(item => {
        item.style.display = item.dataset.title.toLowerCase().includes(q) ? '' : 'none';
      });
    });
  }

  /* ------------------------------------------------------------------ *
   * 5. DAILY CHECK-IN FORM
   * ------------------------------------------------------------------ */
  function initCheckinForm() {
    const form = $('#checkinForm');
    const fields = $$('input, select, textarea', form);
    const requiredFields = fields.filter(f => f.hasAttribute('required'));

    function updateProgress() {
      const filled = requiredFields.filter(f => f.value.trim() !== '').length;
      $('#checkinProgressText').textContent = filled;
      $('#checkinTotal').textContent = requiredFields.length;
      $('#checkinProgressFill').style.width = `${(filled / requiredFields.length) * 100}%`;
    }

    fields.forEach(f => f.addEventListener('input', updateProgress));
    updateProgress();

    $('#checkinSaveBtn').addEventListener('click', async () => {
      const data = Object.fromEntries(new FormData(form).entries());
      await apiPost(ENDPOINTS.checkin, { ...data, status: 'draft' });
      $('#checkinStatus').textContent = 'Draft saved.';
      showToast('Draft saved');
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const missing = requiredFields.filter(f => f.value.trim() === '');
      if (missing.length) {
        $('#checkinStatus').textContent = `Please complete ${missing.length} more field(s) before submitting.`;
        missing[0].focus();
        return;
      }
      const data = Object.fromEntries(new FormData(form).entries());
      await apiPost(ENDPOINTS.checkin, { ...data, status: 'submitted' });
      $('#checkinStatus').textContent = 'Check-in submitted — thank you!';
      showToast('Check-in submitted');
      form.reset();
      updateProgress();
    });
  }

  /* ------------------------------------------------------------------ *
   * 6. WHAT-IF SIMULATOR
   * ------------------------------------------------------------------ */
  let simulatorChart;

  function initSimulator() {
    const hire = $('#sim-hire'), machinery = $('#sim-machinery'), loan = $('#sim-loan'), price = $('#sim-price');
    const sync = () => {
      $('#sim-hire-out').textContent = `${hire.value} people`;
      $('#sim-machinery-out').textContent = formatCurrency(Number(machinery.value));
      $('#sim-loan-out').textContent = formatCurrency(Number(loan.value));
      $('#sim-price-out').textContent = `${price.value}%`;
    };
    [hire, machinery, loan, price].forEach(el => el.addEventListener('input', sync));
    sync();

    $('#simRunBtn').addEventListener('click', async () => {
      const payload = {
        hire: Number(hire.value),
        machinery: Number(machinery.value),
        loan: Number(loan.value),
        price_increase: Number(price.value),
        new_product: $('#sim-newproduct').checked,
        new_branch: $('#sim-newbranch').checked,
      };
      const result = await apiGet(
        `${ENDPOINTS.simulator}?${new URLSearchParams(payload)}`,
        computeSampleSimulation(payload)
      );
      renderSimResult(result);
    });
  }

  function computeSampleSimulation({ hire, machinery, loan, price_increase, new_product, new_branch }) {
    const baseProfit = 180000;
    const profit = Math.round(
      baseProfit - hire * 14000 - machinery * 0.04 + price_increase * 4200 +
      (new_product ? 22000 : 0) + (new_branch ? -35000 : 0) - loan * 0.015
    );
    const riskScore = Math.min(95, Math.max(5, Math.round(
      20 + hire * 2.5 + (machinery / 50000) + (loan / 40000) - price_increase * 0.6 +
      (new_branch ? 14 : 0) + (new_product ? 6 : 0)
    )));
    const risk = riskScore < 35 ? 'Low' : riskScore < 65 ? 'Moderate' : 'High';
    const cashflow = Math.round(profit * 0.7 - loan * 0.02);
    const months = Array.from({ length: 12 }, (_, i) => Math.round(cashflow / 12 * (i + 1) + Math.sin(i) * 8000));

    let recommendation;
    if (risk === 'High') recommendation = 'This combination raises distress risk substantially. Consider phasing the loan or machinery purchase over two quarters.';
    else if (risk === 'Moderate') recommendation = 'A workable path, but keep a cash buffer of at least 30 days before committing to all levers at once.';
    else recommendation = 'This scenario looks financially sound. Proceeding should maintain a healthy risk profile.';

    return { profit, risk, riskScore, cashflow, months, recommendation };
  }

  function renderSimResult(result) {
    $('#simProfit').innerHTML = `${formatCurrency(result.profit)}`;
    $('#simRisk').innerHTML = `${result.risk}<span> (${result.riskScore}/100)</span>`;
    $('#simCashflow').innerHTML = `${formatCurrency(result.cashflow)}`;
    $('#simRecoText').textContent = result.recommendation;

    const ctx = $('#chartSimulator');
    const styles = getChartStyles();
    if (simulatorChart) simulatorChart.destroy();
    simulatorChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: Array.from({ length: 12 }, (_, i) => `M${i + 1}`),
        datasets: [{
          label: 'Projected cash flow',
          data: result.months,
          borderColor: styles.accentCyan,
          backgroundColor: hexToRgba(styles.accentCyan, 0.12),
          tension: 0.35, fill: true, pointRadius: 0, borderWidth: 2.5,
        }],
      },
      options: baseChartOptions(styles),
    });
  }

  /* ------------------------------------------------------------------ *
   * 7. CHARTS (Chart.js)
   * ------------------------------------------------------------------ */
  let charts = {};

  function getChartStyles() {
    const cs = getComputedStyle(document.documentElement);
    return {
      text: cs.getPropertyValue('--text-secondary').trim(),
      grid: cs.getPropertyValue('--border-subtle').trim(),
      accent: cs.getPropertyValue('--blue-600').trim(),
      accentCyan: cs.getPropertyValue('--cyan-400').trim(),
      green: cs.getPropertyValue('--green-500').trim(),
      red: cs.getPropertyValue('--red-500').trim(),
    };
  }

  function hexToRgba(hex, alpha) {
    const h = hex.replace('#', '');
    const bigint = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16);
    const r = (bigint >> 16) & 255, g = (bigint >> 8) & 255, b = bigint & 255;
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function baseChartOptions(styles) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { backgroundColor: styles.text, titleFont: { family: 'Inter' }, bodyFont: { family: 'JetBrains Mono' } } },
      scales: {
        x: { grid: { display: false }, ticks: { color: styles.text, font: { size: 10, family: 'Inter' } } },
        y: { grid: { color: styles.grid }, ticks: { color: styles.text, font: { size: 10, family: 'JetBrains Mono' } } },
      },
    };
  }

  function renderAllCharts() {
    const styles = getChartStyles();

    Object.values(charts).forEach(c => c && c.destroy());

    const revenueEl = $('#chartRevenue');
    if (revenueEl) {
      charts.revenue = new Chart(revenueEl, {
        type: 'line',
        data: {
          labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'],
          datasets: [{
            data: [412000, 398000, 445000, 431000, 467000, 452000, 489000],
            borderColor: styles.accent, backgroundColor: hexToRgba(styles.accent, 0.1),
            tension: 0.35, fill: true, pointRadius: 0, borderWidth: 2.5,
          }],
        },
        options: baseChartOptions(styles),
      });
    }

    const cashflowEl = $('#chartCashflow');
    if (cashflowEl) {
      charts.cashflow = new Chart(cashflowEl, {
        type: 'bar',
        data: {
          labels: ['W1', 'W2', 'W3', 'W4', 'W5', 'W6'],
          datasets: [{
            data: [42000, -8000, 31000, 15000, -12000, 26000],
            backgroundColor: [42000, -8000, 31000, 15000, -12000, 26000].map(v => v >= 0 ? styles.green : styles.red),
            borderRadius: 6, maxBarThickness: 28,
          }],
        },
        options: baseChartOptions(styles),
      });
    }

    if (simulatorChart) {
      simulatorChart.destroy();
      simulatorChart = null;
    }
  }

  function initGauge(score) {
    const circumference = 2 * Math.PI * 68;
    const fill = $('#gaugeFill');
    fill.style.strokeDasharray = String(circumference);
    requestAnimationFrame(() => {
      fill.style.strokeDashoffset = String(circumference * (1 - score / 100));
    });
    $('#gaugeScore').textContent = score;
  }

  /* ------------------------------------------------------------------ *
   * 8. INIT
   * ------------------------------------------------------------------ */
  async function init() {
    initNavigation();
    initSidebarCollapse();
    initDarkMode();
    initDropdowns();
    initModal();
    initLogout();
    initGlobalSearch();
    initCheckinForm();
    initSimulator();

    renderNotifications(await apiGet(`${ENDPOINTS.history}/notifications`, SAMPLE.notifications));

    const recos = (await apiGet(ENDPOINTS.recommendations, { items: SAMPLE.recommendations })).items || SAMPLE.recommendations;
    renderRecommendations(recos);
    initRecoFilters(recos);
    renderDashboardRecoSummary(recos);
    renderAiInsights();
    renderHealthDetail();

    const agents = (await apiGet(ENDPOINTS.agents, { items: SAMPLE.agents })).items || SAMPLE.agents;
    renderAgents(agents);

    renderRecovery(SAMPLE.recovery);
    $('#growthGrid').innerHTML = SAMPLE.growth.map(recoCardHtml).join('');
    $('#schemesGrid').innerHTML = SAMPLE.schemes.map(recoCardHtml).join('');
    renderReports(SAMPLE.reports);
    renderKnowledgeBase();

    initGauge(78);
    renderAllCharts();

    $('#markAllReadBtn').addEventListener('click', () => {
      $('#notifCount').textContent = '0';
      showToast('All notifications marked as read');
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();