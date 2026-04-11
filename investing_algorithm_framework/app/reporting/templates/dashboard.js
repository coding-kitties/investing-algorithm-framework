function saveReport() {
  const name = prompt('Save report as:', 'backtest_report.html');
  if (!name) return;
  const filename = name.endsWith('.html') ? name : name + '.html';
  const blob = new Blob(['\ufeff' + document.documentElement.outerHTML], { type: 'text/html;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

const SYM_COLORS = {
  BTC:'#f7931a', ETH:'#627eea', XRP:'#00aae4', SOL:'#9945ff',
  ADA:'#0033ad', DOT:'#e6007a', LTC:'#bfbbbb', BCH:'#8dc351',
};

const COMP_COLS = [
  ['CAGR','cagr','pct','max'],
  ['Sharpe','sharpe_ratio','ratio','max'],
  ['Sortino','sortino_ratio','ratio','max'],
  ['Calmar','calmar_ratio','ratio','max'],
  ['Max DD','max_drawdown','pct_abs','min'],
  ['Volatility','annual_volatility','pct_abs','min'],
  ['Recovery','recovery_factor','ratio','max'],
  ['Net Gain %','total_net_gain_percentage','pct','max'],
  ['VaR 95%','var_95','pct','min'],
  ['CVaR 95%','cvar_95','pct','min'],
];

const TRADING_COLS = [
  ['Profit Factor','profit_factor','ratio','max'],
  ['Win Rate','win_rate','pct_abs','max'],
  ['Trades/yr','trades_per_year','ratio','neutral'],
  ['Trades/mo','trades_per_month','ratio','neutral'],
  ['Trades/wk','trades_per_week','ratio','neutral'],
  ['# Trades','number_of_trades','int','neutral'],
  ['Avg Return','average_trade_return_percentage','pct','max'],
  ['Median Return','median_trade_return_percentage','pct','max'],
  ['Avg Duration','average_trade_duration','ratio','neutral'],
  ['Win Streak','max_consecutive_wins','int','max'],
  ['Loss Streak','max_consecutive_losses','int','min'],
  ['% Win Months','percentage_winning_months','pct_abs','max'],
];

// Windows column offset removed – window info now in its own component

let selectedRunView = 'summary';

// Populate dropdowns (multi mode only)
(function() {
  const selectors = [document.getElementById('overview-window-select'), document.getElementById('compare-window-select')];
  selectors.forEach(sel => {
    if (!sel) return;
    RUN_LABELS.forEach(([name, label]) => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = label;
      sel.appendChild(opt);
    });
  });
})();

function onOverviewWindowChange(value) {
  onRunViewChange(value);
}

function onCompareWindowChange(value) {
  onRunViewChange(value);
}

function getViewMetrics(stratIdx) {
  const s = STRATEGIES[stratIdx];
  var m;
  if (selectedRunView === 'summary') m = s.summary;
  else {
    const rid = s.runNameMap[selectedRunView];
    m = (rid && RUN_DATA[rid]) ? RUN_DATA[rid].metrics : s.summary;
  }
  // Derive trades_per_month/week from trades_per_year if missing
  if (m.trades_per_month == null && m.trades_per_year != null) m.trades_per_month = m.trades_per_year / 12;
  if (m.trades_per_week == null && m.trades_per_year != null) m.trades_per_week = m.trades_per_year / 52;
  // Derive recovery factor: net gain / abs(max drawdown)
  if (m.recovery_factor == null && m.total_net_gain_percentage != null && m.max_drawdown != null && Math.abs(m.max_drawdown) > 0) {
    m.recovery_factor = m.total_net_gain_percentage / Math.abs(m.max_drawdown);
  }
  return m;
}

function getViewEquity(stratIdx) {
  const s = STRATEGIES[stratIdx];
  if (selectedRunView === 'summary') return s.repEQ;
  const rid = s.runNameMap[selectedRunView];
  if (rid && RUN_DATA[rid] && RUN_DATA[rid].EQ.length > 0) {
    const eq = RUN_DATA[rid].EQ;
    const start = eq[0][0];
    if (start && start !== 0) return eq.map(d => [(d[0]/start-1)*100, d[1]]);
    return eq;
  }
  return s.repEQ;
}

function getViewRunData(stratIdx) {
  const s = STRATEGIES[stratIdx];
  if (selectedRunView !== 'summary') {
    const rid = s.runNameMap[selectedRunView];
    if (rid && RUN_DATA[rid]) return RUN_DATA[rid];
  }
  let targetRid = s.runIds[0], bestLen = 0;
  s.runIds.forEach(r => { const d = RUN_DATA[r]; if (d && d.EQ && d.EQ.length > bestLen) { bestLen = d.EQ.length; targetRid = r; } });
  return RUN_DATA[targetRid];
}

function fmtVal(v, kind) {
  if (v == null) return '—';
  if (kind === 'pct') return (v*100 >= 0 ? '+' : '') + (v*100).toFixed(1) + '%';
  if (kind === 'pct_abs') return (Math.abs(v)*100).toFixed(1) + '%';
  if (kind === 'ratio') return v.toFixed(2);
  if (kind === 'int') return String(Math.round(v));
  if (kind === 'days') return v.toFixed(1) + 'd';
  return String(v);
}

function fmtDuration(hours) {
  if (hours == null || hours === 0) return '—';
  const d = Math.floor(hours / 24);
  const h = Math.round(hours % 24);
  if (d > 0 && h > 0) return d + 'd ' + h + 'h';
  if (d > 0) return d + 'd';
  if (h > 0) return h + 'h';
  return '<1h';
}

function buildTradingActivity(containerId, metricsGetter) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const m = metricsGetter();
  if (!m) { el.innerHTML = ''; return; }
  const items = [
    ['Avg Duration', fmtDuration(m.average_trade_duration)],
    ['Trades / Week', m.trades_per_week != null ? m.trades_per_week.toFixed(1) : '—'],
    ['Trades / Month', m.trades_per_month != null ? m.trades_per_month.toFixed(1) : '—'],
    ['Win Rate', m.win_rate != null ? (m.win_rate * 100).toFixed(1) + '%' : '—', m.win_rate != null && m.win_rate < 0.5 ? 'var(--red)' : null],
    ['Profit Factor', m.profit_factor != null ? m.profit_factor.toFixed(2) : '—'],
    ['Avg Win Duration', fmtDuration(m.average_win_duration)],
    ['Avg Loss Duration', fmtDuration(m.average_loss_duration)],
  ];
  let html = '<div class="chart-card"><div class="chart-title">Trading Activity</div><div class="kpi-row">';
  items.forEach(function(it) {
    const color = it[2] ? ' style="color:' + it[2] + '"' : '';
    html += '<div class="kpi-card"><div class="kpi-value"' + color + '>' + it[1] + '</div><div class="kpi-label">' + it[0] + '</div></div>';
  });
  html += '</div></div>';
  el.innerHTML = html;
}

// ===== WINDOW COVERAGE COMPONENT =====
function rebuildWindowCoverage() {
  var el = document.getElementById('overview-window-coverage');
  var el2 = document.getElementById('windows-page-coverage');
  if (!el && !el2) return;

  var totalWindows = RUN_LABELS.length;
  if (totalWindows === 0) { if (el) el.innerHTML = ''; if (el2) el2.innerHTML = ''; return; }

  // Determine which strategies to show
  var indices = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort(function(a,b){return a-b;})
    : STRATEGIES.map(function(_,i){return i;});

  // Build coverage data per strategy
  var coverageData = indices.map(function(i) {
    var s = STRATEGIES[i];
    var present = 0;
    var windows = RUN_LABELS.map(function(rl) {
      var wname = rl[0];
      var has = !!(s.runNameMap && s.runNameMap[wname]);
      if (has) present++;
      return has;
    });
    return { idx: i, name: s.name, color: s.color, windows: windows, present: present, pct: Math.round(present / totalWindows * 100) };
  });

  // Find shared windows (all selected strategies have this window)
  var sharedCount = 0;
  for (var w = 0; w < totalWindows; w++) {
    var allHave = true;
    for (var ci = 0; ci < coverageData.length; ci++) {
      if (!coverageData[ci].windows[w]) { allHave = false; break; }
    }
    if (allHave) sharedCount++;
  }
  var comparableByAll = indices.length > 1 ? sharedCount : totalWindows;

  // Build HTML
  var html = '<div class="chart-card collapsed">';
  html += '<div class="chart-title">Window Coverage';
  html += '<span style="font-size:0.7rem;font-weight:normal;color:var(--text-secondary)">' + indices.length + ' strategies \xB7 ' + totalWindows + ' windows</span>';
  html += '</div>';

  // Summary stats
  html += '<div class="wc-summary">';
  html += '<div class="wc-summary-item">Total windows: <strong>' + totalWindows + '</strong></div>';
  html += '<div class="wc-summary-item">Shared by all: <strong>' + comparableByAll + '/' + totalWindows + '</strong></div>';
  if (indices.length > 1) {
    var pctComparable = Math.round(comparableByAll / totalWindows * 100);
    var comparableColor = pctComparable === 100 ? 'var(--green)' : pctComparable >= 50 ? 'var(--amber)' : 'var(--red)';
    html += '<div class="wc-summary-item">Comparability: <strong style="color:' + comparableColor + '">' + pctComparable + '%</strong></div>';
  }
  html += '</div>';

  // Coverage bars
  html += '<div style="margin-bottom:1rem">';
  coverageData.forEach(function(d) {
    var barColor = d.pct === 100 ? 'var(--green)' : d.pct >= 50 ? 'var(--amber)' : 'var(--red)';
    html += '<div class="wc-bar-wrap">';
    html += '<div class="wc-bar-label"><span class="sb-dot" style="background:'+d.color+'"></span> '+d.name+'</div>';
    html += '<div class="wc-bar"><div class="wc-bar-fill" style="width:'+d.pct+'%;background:'+barColor+'"></div>';
    html += '<div class="wc-bar-text">'+d.present+'/'+totalWindows+' ('+d.pct+'%)</div></div>';
    html += '</div>';
  });
  html += '</div>';

  // Heatmap grid: strategies (rows) × windows (cols)
  var cols = totalWindows + 1; // +1 for strategy name column
  html += '<div class="wc-grid" style="grid-template-columns:minmax(80px,auto) repeat('+totalWindows+',1fr)">';

  // Header row
  html += '<div class="wc-cell wc-header"></div>'; // empty top-left
  RUN_LABELS.forEach(function(rl) {
    // Extract short label: e.g. "2022-01-01" from the window name or label
    var label = rl[1];
    var shortLabel = label;
    // Try to extract the start date
    var parts = label.split(' \u2192 ');
    if (parts.length === 2) {
      var startPart = parts[0].replace(/^[A-Z]+ /, '');
      shortLabel = startPart;
    }
    html += '<div class="wc-cell wc-header" title="'+label+'">'+shortLabel+'</div>';
  });

  // Data rows
  coverageData.forEach(function(d) {
    html += '<div class="wc-cell wc-strat" title="'+d.name+'"><span class="sb-dot" style="background:'+d.color+'"></span> '+d.name+'</div>';
    d.windows.forEach(function(has, wi) {
      var cls = has ? 'present' : 'missing';
      var title = d.name + ' \u2013 ' + RUN_LABELS[wi][1] + ': ' + (has ? 'Run' : 'Missing');
      html += '<div class="wc-cell" title="'+title+'"><div class="wc-dot '+cls+'"></div></div>';
    });
  });

  html += '</div>'; // end grid
  html += '</div>'; // end chart-card
  if (el) el.innerHTML = html;

  // Windows page gets the same content but expanded by default
  if (el2) {
    el2.innerHTML = html.replace('chart-card collapsed', 'chart-card');
  }
  initCollapseButtons();
}

function rebuildOverviewTradingActivity() {
  const el = document.getElementById('overview-trading-activity');
  if (!el) return;

  // Build sorted index array (filter to selected strategies if any)
  let indices = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);
  if (tradingSortCol) {
    indices.sort((a,b) => {
      const ma = getViewMetrics(a), mb = getViewMetrics(b);
      let va = ma[tradingSortCol], vb = mb[tradingSortCol];
      if (va == null) va = tradingSortAsc ? Infinity : -Infinity;
      if (vb == null) vb = tradingSortAsc ? Infinity : -Infinity;
      return tradingSortAsc ? va - vb : vb - va;
    });
  }

  // Best values
  const bestVals = {};
  TRADING_COLS.forEach(([label,key,ftype,direction]) => {
    let bestIdx=-1, bestVal=direction==='min'?Infinity:-Infinity;
    indices.forEach(i => {
      const m=getViewMetrics(i); const v=m[key];
      if (v==null) return;
      if (direction==='max' && v>bestVal) { bestVal=v; bestIdx=i; }
      if (direction==='min' && Math.abs(v)<bestVal) { bestVal=Math.abs(v); bestIdx=i; }
    });
    if (bestIdx>=0) bestVals[key]=bestIdx;
  });

  let html = '<div class="chart-card">';
  html += '<div class="chart-title">Trading Activity Ranking</div>';
  html += '<div class="table-wrap"><table class="comp-table" id="trading-table"><thead><tr>';
  html += '<th class="sticky-col">Strategy</th>';
  TRADING_COLS.forEach(([label,key]) => {
    html += '<th data-col="'+key+'">'+label+' <span class="sort-arrow">&#9650;</span></th>';
  });
  html += '</tr></thead><tbody>';

  indices.forEach(i => {
    const s = STRATEGIES[i];
    const m = getViewMetrics(i);
    html += '<tr class="comp-row' + (challengerIdx === i ? ' challenger-row' : '') + '" onclick="showPage(\'strat-'+i+'\')">';
    html += '<td class="sticky-col"><span class="sb-dot" style="background:'+s.color+'"></span>'+s.name+'</td>';
    TRADING_COLS.forEach(([label,key,ftype,direction]) => {
      const v = m[key];
      const isBest = bestVals[key]===i;
      const cls = (isBest && indices.length>1) ? ' class="best-cell"' : '';
      if (key==='average_trade_duration' && v!=null) html += '<td'+cls+'>'+v.toFixed(1)+'d</td>';
      else html += '<td'+cls+'>' + fmtVal(v,ftype) + '</td>';
    });
    html += '</tr>';
  });

  html += '</tbody></table></div></div>';
  el.innerHTML = html;
  initCollapseButtons();

  // Attach sort handlers to trading table headers
  const tradingTable = document.getElementById('trading-table');
  if (tradingTable) {
    tradingTable.querySelectorAll('th[data-col]').forEach(th => {
      th.style.cursor = 'pointer';
      th.addEventListener('click', function() {
        const col = this.dataset.col;
        if (tradingSortCol === col) tradingSortAsc = !tradingSortAsc;
        else { tradingSortCol = col; tradingSortAsc = false; }
        rebuildOverviewTradingActivity();
      });
    });
  }
}

var tradingSortCol = null, tradingSortAsc = false;

function rebuildReturnScenarios() {
  const el = document.getElementById('overview-return-scenarios');
  if (!el) return;

  let indices = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);

  // Compute total backtest days across all windows
  var totalDays = 0;
  if (typeof WINDOWS_META !== 'undefined' && WINDOWS_META) {
    WINDOWS_META.forEach(function(w) { totalDays += (w.days || 0); });
  }
  var nWindows = WINDOWS_META ? WINDOWS_META.length : 0;
  var totalYears = totalDays / 365;

  // Warning logic
  var warnings = [];
  if (nWindows < 3) warnings.push('few backtest windows (' + nWindows + ')');
  if (totalYears < 2) warnings.push('short combined backtest period (' + totalDays + ' days / ' + totalYears.toFixed(1) + ' years)');

  let html = '<div class="chart-card">';
  html += '<div class="chart-title">Return Scenarios (Annual)</div>';

  if (warnings.length > 0) {
    html += '<div style="padding:0.5rem 0.75rem;margin-bottom:0.75rem;border-radius:6px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);font-size:0.75rem;color:var(--amber);display:flex;align-items:center;gap:0.4rem">';
    html += '<span style="font-size:1rem">\u26A0</span> These projections are less reliable due to ' + warnings.join(' and ') + '. More data improves accuracy.';
    html += '</div>';
  }

  html += '<div class="table-wrap"><table class="comp-table"><thead><tr>';
  html += '<th class="sticky-col">Strategy</th>';
  html += '<th>CAGR</th>';
  html += '<th>Volatility</th>';
  html += '<th style="color:var(--green)">Good Year</th>';
  html += '<th>Average Year</th>';
  html += '<th style="color:var(--amber)">Bad Year</th>';
  html += '<th style="color:var(--red)">Very Bad Year (2\u03C3)</th>';
  html += '</tr></thead><tbody>';

  indices.forEach(i => {
    const s = STRATEGIES[i];
    const m = s.summary; // Always use summary metrics for annual scenarios
    const cagr = m.cagr;
    const vol = m.annual_volatility;
    const hasBoth = cagr != null && vol != null;
    const good = hasBoth ? (cagr + vol) * 100 : null;
    const avg = cagr != null ? cagr * 100 : null;
    const bad = hasBoth ? (cagr - vol) * 100 : null;
    const vbad = hasBoth ? (cagr - 2 * vol) * 100 : null;

    function fmtScenario(v) {
      if (v == null) return '\u2014';
      var color = v >= 0 ? 'var(--green)' : 'var(--red)';
      return '<span style="color:' + color + '">' + (v >= 0 ? '+' : '') + v.toFixed(1) + '%</span>';
    }

    html += '<tr class="comp-row' + (challengerIdx === i ? ' challenger-row' : '') + '" onclick="showPage(\'strat-'+i+'\')">';
    html += '<td class="sticky-col"><span class="sb-dot" style="background:'+s.color+'"></span>'+s.name+'</td>';
    html += '<td>' + fmtVal(cagr, 'pct') + '</td>';
    html += '<td>' + fmtVal(vol, 'pct_abs') + '</td>';
    html += '<td>' + fmtScenario(good) + '</td>';
    html += '<td>' + fmtScenario(avg) + '</td>';
    html += '<td>' + fmtScenario(bad) + '</td>';
    html += '<td>' + fmtScenario(vbad) + '</td>';
    html += '</tr>';
  });

  html += '</tbody></table></div></div>';
  el.innerHTML = html;
  initCollapseButtons();
}

// ===== NAVIGATION =====
let currentPage = 'overview';

function showPage(pageId) {
  document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
  const target = document.getElementById('page-' + pageId);
  if (target) target.style.display = 'block';
  document.querySelectorAll('.sb-item').forEach(s => s.classList.remove('active'));
  const sbItem = document.querySelector('.sb-item[data-page="' + pageId + '"]');
  if (sbItem) sbItem.classList.add('active');
  const fTab = document.querySelector('.finterion-tab');
  if (fTab) fTab.classList.toggle('active', pageId === 'finterion');
  currentPage = pageId;
  window.scrollTo(0, 0);
  requestAnimationFrame(() => drawPageCharts(pageId));
}

function switchTab(entityId, tabId) {
  const page = document.getElementById('page-' + entityId);
  if (!page) return;
  page.querySelectorAll('.tab-panel').forEach(p => { p.style.display = 'none'; p.classList.remove('active'); });
  page.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const panel = document.getElementById(entityId + '-' + tabId);
  if (panel) { panel.style.display = 'block'; panel.classList.add('active'); }
  const tabs = page.querySelectorAll('.tab');
  const tabNames = IS_SINGLE ? ['overview','performance','trades','risk'] : ['summary','runs','performance'];
  const idx = tabNames.indexOf(tabId);
  if (idx >= 0 && tabs[idx]) tabs[idx].classList.add('active');
  requestAnimationFrame(() => drawPageCharts(entityId));
}

// ===== THEME =====
const DARK_COL = { bg:'#0a0a0b', surface:'#111113', border:'#23232a', text:'#eaeaf0', dim:'#606070', accent:'#22d3ee', green:'#10b981', red:'#ef4444', amber:'#f59e0b', purple:'#a78bfa' };
const LIGHT_COL = { bg:'#f5f5f7', surface:'#ffffff', border:'#e0e0e4', text:'#1a1a2e', dim:'#a0a0b0', accent:'#22d3ee', green:'#10b981', red:'#ef4444', amber:'#f59e0b', purple:'#a78bfa' };
let COL = LIGHT_COL;
(function initTheme() {
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = prefersDark ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
  COL = theme === 'dark' ? DARK_COL : LIGHT_COL;
})();
function toggleTheme() {
  const html = document.documentElement;
  const next = html.dataset.theme === 'dark' ? 'light' : 'dark';
  html.dataset.theme = next;
  COL = next === 'dark' ? DARK_COL : LIGHT_COL;
  drawPageCharts(currentPage);
}

// ===== CANVAS =====
const dpr = window.devicePixelRatio || 1;
function resizeCanvas(id) {
  const c = document.getElementById(id);
  if (!c || !c.parentElement) return null;
  const rect = c.parentElement.getBoundingClientRect();
  if (rect.width < 10) return null;
  c.width = rect.width * dpr; c.height = rect.height * dpr;
  c.style.width = rect.width + 'px'; c.style.height = rect.height + 'px';
  const ctx = c.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, rect.height);
  return { ctx, w: rect.width, h: rect.height };
}

// ===== LINE CHART =====
function drawLineChart(id, data, color, opts) {
  if (!data || data.length < 2) return;
  opts = opts || {};
  const r = resizeCanvas(id);
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  const vals = data.map(d => d[0]);
  let mn = opts.minY != null ? opts.minY : Math.min(...vals.filter(v => v!=null && !isNaN(v)));
  let mx = opts.maxY != null ? opts.maxY : Math.max(...vals.filter(v => v!=null && !isNaN(v)));
  if (mn === mx) { mn -= 1; mx += 1; }
  const range = mx - mn;

  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i = 0; i <= 5; i++) {
    const y = pad.t + ch - (i/5)*ch;
    const val = mn + (i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
    let label = val.toFixed(opts.decimals || 1);
    if (opts.prefix) label = opts.prefix + label;
    if (opts.suffix) label += opts.suffix;
    ctx.fillText(label, w-pad.r+55, y+3.5);
  }
  ctx.textAlign = 'center';
  const li = Math.max(1, Math.floor(data.length/6));
  for (let i = 0; i < data.length; i += li) {
    const x = pad.l + (i/(data.length-1))*cw;
    ctx.fillText(data[i][1], x, h-5);
  }
  ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.lineJoin = 'round';
  let started = false;
  for (let i = 0; i < data.length; i++) {
    if (data[i][0] == null || isNaN(data[i][0])) continue;
    const x = pad.l + (i/(data.length-1))*cw;
    const y = pad.t + ch - ((data[i][0]-mn)/range)*ch;
    if (!started) { ctx.moveTo(x,y); started=true; } else ctx.lineTo(x,y);
  }
  ctx.stroke();

  if (opts.fill) {
    ctx.lineTo(pad.l+cw, pad.t+ch); ctx.lineTo(pad.l, pad.t+ch); ctx.closePath();
    ctx.fillStyle = opts.fillColor || (color+'15'); ctx.fill();
  }
  const canvas = document.getElementById(id);
  canvas._chartData = { data, pad, cw, ch, mn, range, color, opts, type:'line' };
}

// ===== AREA CHART (drawdown) =====
function drawAreaChart(id, data, color) {
  if (!data || data.length < 2) return;
  const r = resizeCanvas(id);
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  const vals = data.map(d => d[0]);
  let mn = Math.min(...vals); let mx = 0;
  if (mn === mx) mn = -1;
  const range = mx - mn;

  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + (i/4)*ch;
    const val = mx - (i/4)*range;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
    ctx.fillText(val.toFixed(1)+'%', w-pad.r+55, y+3.5);
  }
  ctx.textAlign = 'center';
  const li = Math.max(1, Math.floor(data.length/6));
  for (let i = 0; i < data.length; i += li) {
    const x = pad.l + (i/(data.length-1))*cw;
    ctx.fillText(data[i][1], x, h-5);
  }
  ctx.beginPath();
  for (let i = 0; i < data.length; i++) {
    const x = pad.l + (i/(data.length-1))*cw;
    const y = pad.t + ((mx-data[i][0])/range)*ch;
    i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
  }
  ctx.lineTo(pad.l+cw, pad.t); ctx.lineTo(pad.l, pad.t); ctx.closePath();
  const grad = ctx.createLinearGradient(0, pad.t+ch, 0, pad.t);
  grad.addColorStop(0, color+'40'); grad.addColorStop(1, 'transparent');
  ctx.fillStyle = grad; ctx.fill();
  ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = 1.5;
  for (let i = 0; i < data.length; i++) {
    const x = pad.l + (i/(data.length-1))*cw;
    const y = pad.t + ((mx-data[i][0])/range)*ch;
    i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
  }
  ctx.stroke();
  const canvas = document.getElementById(id);
  canvas._chartData = { data, pad, cw, ch, mn, range, mx, color, type:'area' };
}

// ===== BAR CHART =====
function drawBarChart(id, data) {
  if (!data || data.length === 0) return;
  const r = resizeCanvas(id);
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:10, b:35, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  const vals = data.map(d => d[0]);
  const mx = Math.max(...vals.map(Math.abs)) * 1.15 || 1;
  const zeroY = pad.t + ch/2;
  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad.l, zeroY); ctx.lineTo(w-pad.r, zeroY); ctx.stroke();
  const barW = Math.min(80, cw/data.length*0.6);
  const gap = cw/data.length;
  ctx.font = '11px JetBrains Mono, monospace'; ctx.textAlign = 'center';
  data.forEach((d, i) => {
    const x = pad.l + gap*i + gap/2 - barW/2;
    const barH = (Math.abs(d[0])/mx)*(ch/2);
    const color = d[0] >= 0 ? COL.green : COL.red;
    const y = d[0] >= 0 ? zeroY - barH : zeroY;
    ctx.fillStyle = color+'60'; ctx.strokeStyle = color; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.roundRect(x, y, barW, barH, [4,4,0,0]); ctx.fill(); ctx.stroke();
    ctx.fillStyle = color; ctx.fillText((d[0]>=0?'+':'')+d[0].toFixed(1)+'%', x+barW/2, d[0]>=0?y-6:y+barH+14);
    ctx.fillStyle = COL.dim; ctx.fillText(d[1].slice(0,4), x+barW/2, h-8);
  });
}

// ===== HORIZONTAL BARS (comparison) =====
// Zone thresholds for metric quality indicators
// Each zone: [min, max, color_key, label]  — min inclusive, max exclusive (null = unbounded)
// color_key: 'great' (teal), 'good' (green), 'moderate' (amber), 'poor' (red)
const METRIC_ZONES = {
  cagr:    [[null,0,'poor','Poor'],[0,10,'moderate','Low'],[10,25,'good','Good'],[25,null,'great','Great']],
  sharpe:  [[null,0,'poor','Poor'],[0,1,'moderate','Low'],[1,2,'good','Good'],[2,null,'great','Great']],
  sortino: [[null,0,'poor','Poor'],[0,1,'moderate','Low'],[1,2,'good','Good'],[2,null,'great','Great']],
  calmar:  [[null,0,'poor','Poor'],[0,1,'moderate','Low'],[1,3,'good','Good'],[3,null,'great','Great']],
  dd:      [[null,10,'great','Low'],[10,20,'good','Moderate'],[20,35,'moderate','High'],[35,null,'poor','Severe']],
  wr:      [[null,35,'poor','Poor'],[35,45,'moderate','Low'],[45,55,'good','Average'],[55,null,'great','Good']],
  pf:      [[null,0.8,'poor','Poor'],[0.8,1.2,'moderate','Low'],[1.2,2,'good','Good'],[2,null,'great','Great']],
};

const ZONE_PALETTE = {
  great:    { col: '#06b6d4', bg: '#06b6d40F' },  // cyan/teal
  good:     { col: '#10b981', bg: '#10b9810F' },  // green
  moderate: { col: '#f59e0b', bg: '#f59e0b0F' },  // amber
  poor:     { col: '#ef4444', bg: '#ef44440F' },  // red
};

function _zoneStyle(key) {
  return ZONE_PALETTE[key] || ZONE_PALETTE.moderate;
}

function _zoneColor(zones, value) {
  if (!zones) return null;
  for (const [lo, hi, col] of zones) {
    const above = lo === null || value >= lo;
    const below = hi === null || value < hi;
    if (above && below) return col;
  }
  return null;
}

function drawHorizontalBars(id, items, zones) {
  if (!items || items.length === 0) return;
  const r = resizeCanvas(id);
  if (!r) return;
  const { ctx, w, h } = r;
  const hasZones = zones && zones.length > 0;
  const pad = { t:8, r:75, b: hasZones ? 28 : 8, l:90 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  const maxVal = Math.max(...items.map(d => Math.abs(d.value))) || 1;
  const barH = Math.min(28, ch/items.length-4);
  const gap = ch/items.length;

  // Draw zone background bands if provided
  if (hasZones && cw > 0) {
    const axisMax = maxVal * 1.05;
    for (const [lo, hi, col] of zones) {
      const x0 = lo === null ? 0 : Math.max(0, Math.min((lo / axisMax) * cw, cw));
      const x1 = hi === null ? cw : Math.max(0, Math.min((hi / axisMax) * cw, cw));
      if (x1 <= x0) continue;
      const zs = _zoneStyle(col);
      ctx.fillStyle = zs.bg;
      ctx.fillRect(pad.l + x0, pad.t, x1 - x0, ch);
    }
    // Draw zone boundary lines with threshold labels
    const axisMaxLine = maxVal * 1.05;
    for (const [lo, hi] of zones) {
      for (const bv of [lo, hi]) {
        if (bv === null || bv <= 0) continue;
        const x = pad.l + Math.min((bv / axisMaxLine) * cw, cw);
        if (x > pad.l && x < pad.l + cw) {
          ctx.save();
          ctx.setLineDash([3, 3]);
          ctx.strokeStyle = COL.dim + '50';
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ch); ctx.stroke();
          ctx.setLineDash([]);
          ctx.restore();
        }
      }
    }

    // Draw scale legend strip below chart area
    const legendY = pad.t + ch + 5;
    const legendH = 14;
    ctx.font = '9px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const axisMaxLeg = maxVal * 1.05;
    for (const [lo, hi, col, label] of zones) {
      const x0 = lo === null ? 0 : Math.max(0, Math.min((lo / axisMaxLeg) * cw, cw));
      const x1 = hi === null ? cw : Math.max(0, Math.min((hi / axisMaxLeg) * cw, cw));
      if (x1 <= x0) continue;
      const zs = _zoneStyle(col);
      // Colored strip
      ctx.fillStyle = zs.col + '35';
      ctx.beginPath();
      ctx.roundRect(pad.l + x0 + 1, legendY, x1 - x0 - 2, legendH, 3);
      ctx.fill();
      // Label text centered in the strip
      const segW = x1 - x0;
      if (segW > 24) {
        ctx.fillStyle = zs.col;
        ctx.fillText(label, pad.l + x0 + segW / 2, legendY + 2);
      }
    }
  }

  ctx.font = '11px Inter, sans-serif'; ctx.textBaseline = 'middle';
  items.forEach((d, i) => {
    const y = pad.t + gap*i + gap/2;
    const barW = (Math.abs(d.value)/maxVal)*cw;
    const isChal = d.isChallenger === true;

    // Color bar by zone quality if zones are provided
    const zc = _zoneColor(zones, d.value);
    const barColor = zc ? _zoneStyle(zc).col : d.color;

    // Challenger gets a thicker border and hatched pattern
    if (isChal) {
      ctx.fillStyle = barColor+'45'; ctx.strokeStyle = barColor; ctx.lineWidth = 2.5;
      ctx.beginPath(); ctx.roundRect(pad.l, y-barH/2, barW, barH, [0,4,4,0]); ctx.fill(); ctx.stroke();
      // Draw diagonal hatch lines inside bar
      ctx.save();
      ctx.beginPath(); ctx.roundRect(pad.l, y-barH/2, barW, barH, [0,4,4,0]); ctx.clip();
      ctx.strokeStyle = barColor+'30'; ctx.lineWidth = 1;
      for (let hx = -barH; hx < barW + barH; hx += 6) {
        ctx.beginPath();
        ctx.moveTo(pad.l + hx, y - barH/2);
        ctx.lineTo(pad.l + hx + barH, y + barH/2);
        ctx.stroke();
      }
      ctx.restore();
    } else {
      ctx.fillStyle = barColor+'30'; ctx.strokeStyle = barColor; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.roundRect(pad.l, y-barH/2, barW, barH, [0,4,4,0]); ctx.fill(); ctx.stroke();
    }

    ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
    // Challenger gets a flag marker on the name
    const nameLabel = (isChal ? '\u2691 ' : '') + d.name.slice(0,12);
    ctx.fillText(nameLabel, pad.l-8, y);
    ctx.fillStyle = barColor; ctx.textAlign = 'left';
    ctx.font = '11px JetBrains Mono, monospace';
    ctx.fillText(d.formatted, pad.l+barW+8, y);
    ctx.font = '11px Inter, sans-serif';
  });
}

// ===== DONUT =====
function drawDonut(id, legendId, symStats) {
  const r = resizeCanvas(id);
  if (!r) return;
  const { ctx, w, h } = r;
  const cx = w/2, cy = h/2;
  const R = Math.min(cx, cy)-10, inner = R*0.55;
  const syms = Object.keys(symStats).sort((a,b) => symStats[b].count - symStats[a].count);
  const total = syms.reduce((s,k) => s+symStats[k].count, 0);
  if (total === 0) return;
  let angle = -Math.PI/2;
  syms.forEach(sym => {
    const frac = symStats[sym].count/total;
    const sweep = frac*Math.PI*2;
    ctx.beginPath(); ctx.arc(cx,cy,R,angle,angle+sweep); ctx.arc(cx,cy,inner,angle+sweep,angle,true); ctx.closePath();
    ctx.fillStyle = SYM_COLORS[sym] || COL.accent; ctx.fill();
    angle += sweep;
  });
  ctx.fillStyle = COL.text; ctx.font = '600 22px Inter, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(total, cx, cy-8);
  ctx.fillStyle = COL.dim; ctx.font = '500 10px Inter, sans-serif';
  ctx.fillText('TRADES', cx, cy+10);
  const leg = document.getElementById(legendId);
  if (leg) leg.innerHTML = syms.map(s => '<span><span class="swatch" style="background:'+(SYM_COLORS[s]||COL.accent)+'"></span>'+s+' ('+symStats[s].count+')</span>').join('');
}

// ===== P&L BAR =====
function drawPnlBar(id, symStats) {
  const r = resizeCanvas(id);
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:10, r:10, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  const syms = Object.keys(symStats).sort((a,b) => symStats[b].gain - symStats[a].gain);
  if (syms.length === 0) return;
  const vals = syms.map(s => symStats[s].gain);
  const mx = Math.max(...vals.map(Math.abs))*1.15 || 1;
  const zeroY = pad.t + ch*(mx/(2*mx));
  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad.l, zeroY); ctx.lineTo(w-pad.r, zeroY); ctx.stroke();
  const barW = Math.min(50, cw/syms.length*0.65);
  const gap = cw/syms.length;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.textAlign = 'center';
  syms.forEach((sym, i) => {
    const g = symStats[sym].gain;
    const x = pad.l + gap*i + gap/2 - barW/2;
    const barH = (Math.abs(g)/mx)*(ch/2);
    const color = SYM_COLORS[sym] || COL.accent;
    const y = g >= 0 ? zeroY - barH : zeroY;
    ctx.fillStyle = color+'70'; ctx.strokeStyle = color; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.roundRect(x, y, barW, barH, [3,3,0,0]); ctx.fill(); ctx.stroke();
    ctx.fillStyle = COL.dim; ctx.fillText(sym, x+barW/2, h-8);
    ctx.fillStyle = g>=0 ? COL.green : COL.red; ctx.font = '9px JetBrains Mono, monospace';
    ctx.fillText((g>=0?'+':'')+g.toFixed(0), x+barW/2, g>=0?y-4:y+barH+11);
  });
}

// ===== HEATMAP =====
function buildHeatmap(containerId, heatmapData) {
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const years = Object.keys(heatmapData).sort();
  if (years.length === 0) return;
  let html = '<table class="heatmap-table"><thead><tr><th></th>';
  months.forEach(m => html += '<th>'+m+'</th>');
  html += '<th>Year</th></tr></thead><tbody>';
  years.forEach(y => {
    html += '<tr><th>'+y+'</th>';
    let yTotal = 0;
    months.forEach((_, mi) => {
      const v = heatmapData[y]?.[mi+1];
      if (v !== undefined) {
        yTotal += v;
        let cls = 'hm-zero';
        if (v > 10) cls = 'hm-strong-pos';
        else if (v > 0) cls = 'hm-pos';
        else if (v < -3) cls = 'hm-strong-neg';
        else if (v < 0) cls = 'hm-neg';
        html += '<td class="'+cls+'">'+(v>0?'+':'')+v.toFixed(1)+'%</td>';
      } else html += '<td class="hm-zero">&mdash;</td>';
    });
    const ycls = yTotal > 0 ? 'hm-pos' : yTotal < 0 ? 'hm-neg' : 'hm-zero';
    html += '<td class="'+ycls+'" style="font-weight:600">'+(yTotal>0?'+':'')+yTotal.toFixed(1)+'%</td></tr>';
  });
  html += '</tbody></table>';
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = html;
}

// ===== TRADE TABLE =====
const sortState = {};
function renderTrades(runId, trades) {
  if (!sortState[runId]) sortState[runId] = { col:'id', asc:true };
  const st = sortState[runId];
  const sorted = [...trades].sort((a,b) => {
    let va=a[st.col], vb=b[st.col];
    if (typeof va === 'string') return st.asc ? va.localeCompare(vb) : vb.localeCompare(va);
    return st.asc ? va-vb : vb-va;
  });
  const body = document.getElementById('tbody-'+runId);
  if (!body) return;
  body.innerHTML = sorted.map(t => {
    const color = t.net_gain>=0 ? 'var(--green)' : 'var(--red)';
    return '<tr><td>'+t.id+'</td><td>'+t.sym+'</td><td>'+t.opened+'</td><td>'+t.closed+'</td><td>'+t.open_price+'</td><td>'+t.close_price+'</td><td>\u20AC'+t.cost.toFixed(0)+'</td><td style="color:'+color+'">'+(t.net_gain>=0?'+':'')+'\u20AC'+t.net_gain.toFixed(2)+'</td><td style="color:'+color+'">'+(t.pct>=0?'+':'')+t.pct.toFixed(1)+'%</td></tr>';
  }).join('');
}

// Sort handlers
document.querySelectorAll('.comp-table th[data-run]').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.dataset.col, runId = th.dataset.run;
    const data = RUN_DATA[runId];
    if (!data) return;
    if (!sortState[runId]) sortState[runId] = {col:'id',asc:true};
    const st = sortState[runId];
    if (st.col === col) st.asc = !st.asc;
    else { st.col = col; st.asc = true; }
    th.closest('thead').querySelectorAll('th').forEach(h => h.classList.remove('sorted'));
    th.classList.add('sorted');
    const arrow = th.querySelector('.sort-arrow');
    if (arrow) arrow.textContent = st.asc ? '\u25B2' : '\u25BC';
    renderTrades(runId, data.TRADES);
  });
});

// ===== TOOLTIP =====
function setupTooltip(canvasId, tooltipId) {
  const canvas = document.getElementById(canvasId);
  const tooltip = document.getElementById(tooltipId);
  if (!canvas || !tooltip) return;
  canvas.addEventListener('mousemove', (e) => {
    const cd = canvas._chartData;
    if (!cd) return;
    const rect = canvas.getBoundingClientRect();
    const mx2 = e.clientX - rect.left;
    if (mx2 < cd.pad.l || mx2 > cd.pad.l + cd.cw) { tooltip.classList.remove('visible'); return; }
    const idx = Math.round(((mx2-cd.pad.l)/cd.cw)*(cd.data.length-1));
    if (idx < 0 || idx >= cd.data.length) { tooltip.classList.remove('visible'); return; }
    const d = cd.data[idx];
    let text = d[1]+': ';
    if (cd.type === 'area') text += d[0].toFixed(2)+'%';
    else { if (cd.opts?.prefix) text += cd.opts.prefix; text += (d[0]!=null?d[0]:'?').toFixed?.(cd.opts?.decimals||2) || d[0]; if (cd.opts?.suffix) text += cd.opts.suffix; }
    tooltip.textContent = text;
    tooltip.classList.add('visible');
    tooltip.style.left = (mx2+12)+'px';
    tooltip.style.top = (e.clientY-rect.top-20)+'px';
  });
  canvas.addEventListener('mouseleave', () => tooltip.classList.remove('visible'));
}

// ===== OVERVIEW: SINGLE EQUITY OVERLAY =====
function drawSingleOverviewEquity() {
  const strat = STRATEGIES[0];
  const r = resizeCanvas('c-overview-eq');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  const colors = [COL.accent, COL.green, COL.amber, COL.purple, COL.red];

  let gMin = Infinity, gMax = -Infinity;
  strat.runIds.forEach(rid => {
    const eq = RUN_DATA[rid]?.EQ;
    if (!eq) return;
    eq.forEach(d => { if(d[0]<gMin) gMin=d[0]; if(d[0]>gMax) gMax=d[0]; });
  });
  if (!isFinite(gMin)) return;
  if (gMin === gMax) { gMin-=1; gMax+=1; }
  const range = gMax-gMin;

  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i=0;i<=5;i++) {
    const y = pad.t+ch-(i/5)*ch;
    const val = gMin+(i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    ctx.fillText('\u20AC'+val.toFixed(0), w-pad.r+55, y+3.5);
  }
  strat.runIds.forEach((rid, ci) => {
    const rd = RUN_DATA[rid]; if (!rd || !rd.EQ || rd.EQ.length<2) return;
    const eq = rd.EQ; const color = colors[ci%colors.length];
    if (ci===0) {
      ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
      const li = Math.max(1, Math.floor(eq.length/6));
      for (let i=0;i<eq.length;i+=li) { const x=pad.l+(i/(eq.length-1))*cw; ctx.fillText(eq[i][1], x, h-5); }
    }
    ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.lineJoin = 'round';
    for (let i=0;i<eq.length;i++) {
      const x=pad.l+(i/(eq.length-1))*cw;
      const y=pad.t+ch-((eq[i][0]-gMin)/range)*ch;
      i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
    }
    ctx.stroke();
  });
  const canvas = document.getElementById('c-overview-eq');
  if (strat.runIds.length>0 && RUN_DATA[strat.runIds[0]]) {
    const eq = RUN_DATA[strat.runIds[0]].EQ;
    canvas._chartData = { data:eq, pad, cw, ch, mn:gMin, range, color:COL.accent, opts:{prefix:'\u20AC',decimals:0}, type:'line' };
  }
}

// ===== OVERVIEW: MULTI EQUITY OVERLAY =====
function drawMultiOverviewEquity() {
  const canvas = document.getElementById('c-overview-eq');
  if (!canvas) return;
  const wrap = canvas.parentElement;

  // Show placeholder when "All Windows" (summary) is selected
  let placeholder = wrap.querySelector('.eq-placeholder');
  if (selectedRunView === 'summary') {
    const r = resizeCanvas('c-overview-eq');
    if (r) { r.ctx.clearRect(0, 0, r.w, r.h); }
    if (!placeholder) {
      placeholder = document.createElement('div');
      placeholder.className = 'eq-placeholder';
      placeholder.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:13px;pointer-events:none;';
      wrap.style.position = 'relative';
      wrap.appendChild(placeholder);
    }
    placeholder.textContent = 'No equity curve available when no backtest window is selected';
    placeholder.style.display = 'flex';
    wrap.style.height = '80px';
    return;
  }
  if (placeholder) placeholder.style.display = 'none';
  wrap.style.height = '';

  const r = resizeCanvas('c-overview-eq');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;

  const visibleIndices = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);

  let gMin=0, gMax=0;
  visibleIndices.forEach(i => {
    const eq = getViewEquity(i);
    eq.forEach(d => { if(d[0]<gMin) gMin=d[0]; if(d[0]>gMax) gMax=d[0]; });
  });
  // Include visible benchmarks in the y-range
  if (typeof BENCHMARKS !== 'undefined') {
    benchmarkVisible.forEach(bi => {
      const beq = getBenchmarkEquity(bi);
      beq.forEach(d => { if(d[0]<gMin) gMin=d[0]; if(d[0]>gMax) gMax=d[0]; });
    });
  }
  if (gMin===gMax) { gMin-=1; gMax+=1; }
  const range = gMax-gMin;

  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i=0;i<=5;i++) {
    const y = pad.t+ch-(i/5)*ch;
    const val = gMin+(i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    ctx.fillText(val.toFixed(0)+'%', w-pad.r+50, y+3.5);
  }
  if (gMin<0 && gMax>0) {
    const zeroY = pad.t+ch-((0-gMin)/range)*ch;
    ctx.strokeStyle = COL.dim; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l,zeroY); ctx.lineTo(w-pad.r,zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }
  const equities = visibleIndices.map(i => ({ eq:getViewEquity(i), color:STRATEGIES[i].color, isChal: challengerIdx === i, stratIdx: i }));
  // Draw non-challenger lines first, then challenger on top
  const sortedEquities = [...equities].sort((a,b) => (a.isChal?1:0)-(b.isChal?1:0));
  sortedEquities.forEach((item, ci) => {
    const eq = item.eq; if (!eq || eq.length<2) return;
    if (ci===0) {
      ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
      const li = Math.max(1,Math.floor(eq.length/6));
      for (let i=0;i<eq.length;i+=li) { const x=pad.l+(i/(eq.length-1))*cw; ctx.fillText(eq[i][1], x, h-5); }
    }
    ctx.beginPath(); ctx.strokeStyle = item.color;
    ctx.lineWidth = item.isChal ? 3.5 : 2;
    ctx.lineJoin = 'round';
    if (!item.isChal) { ctx.setLineDash([]); }
    for (let i=0;i<eq.length;i++) {
      const x=pad.l+(i/(eq.length-1))*cw;
      const y=pad.t+ch-((eq[i][0]-gMin)/range)*ch;
      i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
    }
    ctx.stroke();
    // Challenger: draw a glow effect underneath
    if (item.isChal) {
      ctx.save();
      ctx.beginPath(); ctx.strokeStyle = item.color+'40'; ctx.lineWidth = 8; ctx.lineJoin = 'round';
      for (let i=0;i<eq.length;i++) {
        const x=pad.l+(i/(eq.length-1))*cw;
        const y=pad.t+ch-((eq[i][0]-gMin)/range)*ch;
        i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
      }
      ctx.stroke();
      ctx.restore();
      // Label the challenger at the end of the line
      const lastX = pad.l + cw;
      const lastY = pad.t+ch-((eq[eq.length-1][0]-gMin)/range)*ch;
      ctx.fillStyle = item.color; ctx.font = '12px Inter, sans-serif'; ctx.textAlign = 'left';
      ctx.fillText('\u2691', lastX + 4, lastY + 1);
      ctx.font = '10px JetBrains Mono, monospace';
    }
    ctx.setLineDash([]);
  });

  // ---- Draw benchmark lines (dashed) ----
  if (typeof BENCHMARKS !== 'undefined') {
    benchmarkVisible.forEach(bi => {
      const b = BENCHMARKS[bi];
      const beq = getBenchmarkEquity(bi);
      if (!beq || beq.length < 2) return;
      ctx.beginPath();
      ctx.strokeStyle = b.color;
      ctx.lineWidth = 2;
      ctx.setLineDash(b.lineStyle === 'dotted' ? [2, 4] : [6, 4]);
      ctx.lineJoin = 'round';
      for (let i = 0; i < beq.length; i++) {
        const x = pad.l + (i / (beq.length - 1)) * cw;
        const y = pad.t + ch - ((beq[i][0] - gMin) / range) * ch;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
      // Label at end of line
      const lastX = pad.l + cw;
      const lastY = pad.t + ch - ((beq[beq.length - 1][0] - gMin) / range) * ch;
      ctx.fillStyle = b.color;
      ctx.font = '9px Inter, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(b.name, lastX + 4, lastY + 3);
      ctx.font = '10px JetBrains Mono, monospace';
    });
  }

  if (equities.length>0 && equities[0].eq.length>0) {
    canvas._chartData = { data:equities[0].eq, pad, cw, ch, mn:gMin, range, color:equities[0].color, opts:{suffix:'%',decimals:1}, type:'line' };
  }
}

// ===== METRIC COMPARISON BARS (multi mode) =====
function drawMetricComparison() {
  const vis = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);
  const _chal = (i) => challengerIdx === i;
  drawHorizontalBars('c-cmp-cagr', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:(m.cagr||0)*100, color:s.color, formatted:((m.cagr||0)*100).toFixed(1)+'%', isChallenger:_chal(i) }; }), METRIC_ZONES.cagr);
  drawHorizontalBars('c-cmp-sharpe', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:m.sharpe_ratio||0, color:s.color, formatted:(m.sharpe_ratio||0).toFixed(2), isChallenger:_chal(i) }; }), METRIC_ZONES.sharpe);
  drawHorizontalBars('c-cmp-sortino', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:m.sortino_ratio||0, color:s.color, formatted:(m.sortino_ratio||0).toFixed(2), isChallenger:_chal(i) }; }), METRIC_ZONES.sortino);
  drawHorizontalBars('c-cmp-calmar', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:m.calmar_ratio||0, color:s.color, formatted:(m.calmar_ratio||0).toFixed(2), isChallenger:_chal(i) }; }), METRIC_ZONES.calmar);
  drawHorizontalBars('c-cmp-dd', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:Math.abs(m.max_drawdown||0)*100, color:s.color, formatted:(Math.abs(m.max_drawdown||0)*100).toFixed(1)+'%', isChallenger:_chal(i) }; }), METRIC_ZONES.dd);
  drawHorizontalBars('c-cmp-wr', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:(m.win_rate||0)*100, color:s.color, formatted:((m.win_rate||0)*100).toFixed(1)+'%', isChallenger:_chal(i) }; }), METRIC_ZONES.wr);
  drawHorizontalBars('c-cmp-pf', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:m.profit_factor||0, color:s.color, formatted:(m.profit_factor||0).toFixed(2), isChallenger:_chal(i) }; }), METRIC_ZONES.pf);
}

// ===== BENCHMARK INSIGHTS =====
function rebuildBenchmarkInsights() {
  const container = document.getElementById('bench-insights');
  if (!container || typeof BENCHMARKS === 'undefined' || !BENCHMARKS.length) return;

  const vis = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);

  // Use CAGR for the headline comparison (time-normalized, apples-to-apples)
  function stratCagr(i) {
    const m = STRATEGIES[i].summary;
    return (m && m.cagr != null) ? m.cagr * 100 : 0; // convert to %
  }

  // Per-window returns for a strategy (equity-based, same time span as benchmark window)
  function stratWindowReturns(stratIdx) {
    const s = STRATEGIES[stratIdx];
    const returns = {};
    for (const [wname] of RUN_LABELS) {
      const rid = s.runNameMap[wname];
      if (rid && RUN_DATA[rid] && RUN_DATA[rid].EQ.length >= 2) {
        const eq = RUN_DATA[rid].EQ;
        const start = eq[0][0];
        const end = eq[eq.length - 1][0];
        returns[wname] = start !== 0 ? (end / start - 1) * 100 : end;
      }
    }
    return returns;
  }

  // Per-window returns for a benchmark
  function benchWindowReturns(bi) {
    const b = BENCHMARKS[bi];
    if (!b || !b.windowEQ) return {};
    const returns = {};
    for (const wname in b.windowEQ) {
      const weq = b.windowEQ[wname];
      if (weq && weq.length >= 2) returns[wname] = weq[weq.length - 1][0];
    }
    return returns;
  }

  let html = '<div class="bi-grid">';

  BENCHMARKS.forEach((b, bi) => {
    if (!benchmarkVisible.has(bi)) return;
    const bCagr = (b.cagr || 0) * 100; // benchmark CAGR in %

    // Count strategies that beat this benchmark by CAGR
    let beatCount = 0;
    let totalAlpha = 0;
    let bestAlpha = -Infinity;
    let bestAlphaName = '';
    let worstAlpha = Infinity;
    let worstAlphaName = '';

    vis.forEach(i => {
      const sc = stratCagr(i);
      const alpha = sc - bCagr;
      totalAlpha += alpha;
      if (sc > bCagr) beatCount++;
      if (alpha > bestAlpha) { bestAlpha = alpha; bestAlphaName = STRATEGIES[i].name; }
      if (alpha < worstAlpha) { worstAlpha = alpha; worstAlphaName = STRATEGIES[i].name; }
    });

    const beatPct = vis.length > 0 ? (beatCount / vis.length * 100) : 0;
    const avgAlpha = vis.length > 0 ? totalAlpha / vis.length : 0;

    // Per-window consistency: what % of windows did each strategy beat this benchmark?
    const bwRet = benchWindowReturns(bi);
    const windowNames = Object.keys(bwRet);
    let consistentCount = 0; // strategies that beat benchmark in ALL windows
    let totalWindowBeats = 0;
    let totalWindowPairs = 0;

    vis.forEach(i => {
      const swRet = stratWindowReturns(i);
      let wins = 0, total = 0;
      windowNames.forEach(wn => {
        if (swRet[wn] !== undefined) {
          total++;
          if (swRet[wn] > (bwRet[wn] || 0)) { wins++; totalWindowBeats++; }
          totalWindowPairs++;
        }
      });
      if (total > 0 && wins === total) consistentCount++;
    });

    const windowBeatPct = totalWindowPairs > 0 ? (totalWindowBeats / totalWindowPairs * 100) : 0;

    // Determine color for beat percentage
    const beatColor = beatPct >= 75 ? 'var(--green)' : beatPct >= 50 ? 'var(--amber)' : 'var(--red)';

    html += '<div class="bi-card">';
    html += '<div class="bi-header"><span class="bench-dot" style="background:' + b.color + '"></span>' + b.name + ' <span class="bi-pct">CAGR ' + (bCagr >= 0 ? '+' : '') + bCagr.toFixed(1) + '%</span></div>';
    html += '<div class="bi-stats">';

    // Row 1: Beat rate (by CAGR)
    html += '<div class="bi-stat"><span class="bi-label">Strategies beating (CAGR)</span>';
    html += '<span class="bi-value" style="color:' + beatColor + '">' + beatCount + '/' + vis.length + ' <span class="bi-pct">(' + beatPct.toFixed(0) + '%)</span></span></div>';

    // Row 2: Window beat rate (with counts)
    if (windowNames.length > 0) {
      const wColor = windowBeatPct >= 60 ? 'var(--green)' : windowBeatPct >= 40 ? 'var(--amber)' : 'var(--red)';
      html += '<div class="bi-stat"><span class="bi-label">Windows won</span>';
      html += '<span class="bi-value" style="color:' + wColor + '">' + totalWindowBeats + '/' + totalWindowPairs + ' <span class="bi-pct">(' + windowBeatPct.toFixed(0) + '%)</span></span></div>';
    }

    // Row 3: Avg alpha (CAGR difference)
    const aColor = avgAlpha >= 0 ? 'var(--green)' : 'var(--red)';
    html += '<div class="bi-stat"><span class="bi-label">Avg. alpha (CAGR excess)</span>';
    html += '<span class="bi-value" style="color:' + aColor + '">' + (avgAlpha >= 0 ? '+' : '') + avgAlpha.toFixed(1) + 'pp</span></div>';

    // Row 4: Best alpha
    if (bestAlpha > -Infinity) {
      const baColor = bestAlpha >= 0 ? 'var(--green)' : 'var(--red)';
      html += '<div class="bi-stat"><span class="bi-label">Best alpha</span>';
      html += '<span class="bi-value" style="color:' + baColor + '">' + (bestAlpha >= 0 ? '+' : '') + bestAlpha.toFixed(1) + 'pp <span class="bi-pct">' + bestAlphaName.slice(0, 20) + '</span></span></div>';
    }

    // Row 5: Worst alpha
    if (worstAlpha < Infinity) {
      const waColor = worstAlpha >= 0 ? 'var(--green)' : 'var(--red)';
      html += '<div class="bi-stat"><span class="bi-label">Worst alpha</span>';
      html += '<span class="bi-value" style="color:' + waColor + '">' + (worstAlpha >= 0 ? '+' : '') + worstAlpha.toFixed(1) + 'pp <span class="bi-pct">' + worstAlphaName.slice(0, 20) + '</span></span></div>';
    }

    // Row 6: Consistency
    if (windowNames.length > 0) {
      const conPct = vis.length > 0 ? (consistentCount / vis.length * 100) : 0;
      const cColor = conPct >= 50 ? 'var(--green)' : conPct > 0 ? 'var(--amber)' : 'var(--red)';
      html += '<div class="bi-stat"><span class="bi-label">Always-beat consistency</span>';
      html += '<span class="bi-value" style="color:' + cColor + '">' + consistentCount + '/' + vis.length + ' <span class="bi-pct">beat in all ' + windowNames.length + ' windows</span></span></div>';
    }

    html += '</div></div>';
  });

  html += '</div>';
  container.innerHTML = html;
}

// ===== MULTI STRATEGY PER-PAGE (runs equity overlay) =====
function drawStrategyEquity(stratIdx) {
  const strat = STRATEGIES[stratIdx];
  if (!strat) return;
  const id = 'c-strat-'+stratIdx+'-eq';
  const r = resizeCanvas(id);
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  const colors = [strat.color, COL.green, COL.amber, COL.purple, COL.red, COL.accent];

  // Determine which runs to draw
  const selRun = stratSelectedRun[stratIdx];
  let runIds;
  if (selRun && selRun !== 'summary') {
    runIds = [selRun];
  } else {
    runIds = strat.runIds;
  }

  // Update equity title
  const eqTitle = document.getElementById('eq-title-strat-'+stratIdx);
  if (eqTitle) {
    if (selRun && selRun !== 'summary' && RUN_DATA[selRun]) {
      eqTitle.textContent = 'Equity Curve \u2013 Normalized % (' + (RUN_DATA[selRun].label || selRun) + ')';
    } else {
      eqTitle.textContent = 'Equity Curves \u2013 Normalized % (All Runs)';
    }
  }

  // Normalize equity to percentage growth from start
  const normSeries = [];
  runIds.forEach((rid, ci) => {
    const rd = RUN_DATA[rid]; if (!rd || !rd.EQ || rd.EQ.length<2) return;
    const eq = rd.EQ;
    const start = eq[0][0];
    const norm = (start && start !== 0)
      ? eq.map(d => [(d[0]/start - 1)*100, d[1]])
      : eq;
    normSeries.push({ data: norm, color: colors[ci%colors.length], rid: rid });
  });

  if (normSeries.length === 0) return;

  let gMin=0, gMax=0;
  normSeries.forEach(s => s.data.forEach(d => { if(d[0]<gMin) gMin=d[0]; if(d[0]>gMax) gMax=d[0]; }));
  if (gMin===gMax) { gMin-=1; gMax+=1; }
  const range = gMax-gMin;
  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i=0;i<=5;i++) {
    const y = pad.t+ch-(i/5)*ch; const val = gMin+(i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    ctx.fillText(val.toFixed(1)+'%', w-pad.r+55, y+3.5);
  }
  const showDates = normSeries.length === 1;
  normSeries.forEach((s, ci) => {
    const eq = s.data;
    if (showDates && ci===0) {
      ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
      const li = Math.max(1,Math.floor(eq.length/6));
      for (let i=0;i<eq.length;i+=li) { const x=pad.l+(i/(eq.length-1))*cw; ctx.fillText(eq[i][1], x, h-5); }
    }
    ctx.beginPath(); ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.lineJoin = 'round';
    for (let i=0;i<eq.length;i++) {
      const x=pad.l+(i/(eq.length-1))*cw;
      const y=pad.t+ch-((eq[i][0]-gMin)/range)*ch;
      i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
    }
    ctx.stroke();
  });
}

// ===== STRATEGY ROLLING SHARPE (per-page, multi-run overlay) =====
function drawStrategyRollingSharpe(stratIdx) {
  const strat = STRATEGIES[stratIdx];
  if (!strat) return;
  const id = 'c-strat-'+stratIdx+'-rsharpe';
  const r = resizeCanvas(id);
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  const colors = [strat.color, COL.green, COL.amber, COL.purple, COL.red, COL.accent];

  const selRun = stratSelectedRun[stratIdx];
  let runIds = (selRun && selRun !== 'summary') ? [selRun] : strat.runIds;

  const rsTitle = document.getElementById('rs-title-strat-'+stratIdx);
  if (rsTitle) {
    if (selRun && selRun !== 'summary' && RUN_DATA[selRun]) {
      rsTitle.textContent = 'Rolling Sharpe Ratio (' + (RUN_DATA[selRun].label || selRun) + ')';
    } else {
      rsTitle.textContent = 'Rolling Sharpe Ratio (All Runs)';
    }
  }

  const rsSeries = [];
  runIds.forEach((rid, ci) => {
    const rd = RUN_DATA[rid]; if (!rd || !rd.RS || rd.RS.length < 2) return;
    rsSeries.push({ data: rd.RS, color: colors[ci % colors.length], rid: rid });
  });
  if (rsSeries.length === 0) return;

  let gMin = Infinity, gMax = -Infinity;
  rsSeries.forEach(s => s.data.forEach(d => {
    if (d[0] != null && !isNaN(d[0])) { if (d[0] < gMin) gMin = d[0]; if (d[0] > gMax) gMax = d[0]; }
  }));
  if (!isFinite(gMin)) return;
  if (gMin === gMax) { gMin -= 1; gMax += 1; }
  const range = gMax - gMin;

  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i = 0; i <= 5; i++) {
    const y = pad.t + ch - (i/5)*ch; const val = gMin + (i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
    ctx.fillText(val.toFixed(2), w-pad.r+50, y+3.5);
  }
  if (gMin < 0 && gMax > 0) {
    const zeroY = pad.t + ch - ((0 - gMin)/range)*ch;
    ctx.strokeStyle = COL.dim; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l, zeroY); ctx.lineTo(w-pad.r, zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }

  const showDates = rsSeries.length === 1;
  rsSeries.forEach((s, ci) => {
    const rs = s.data;
    if (showDates && ci === 0) {
      ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
      const li = Math.max(1, Math.floor(rs.length/6));
      for (let i = 0; i < rs.length; i += li) { const x = pad.l+(i/(rs.length-1))*cw; ctx.fillText(rs[i][1], x, h-5); }
    }
    ctx.beginPath(); ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.lineJoin = 'round';
    let started = false;
    for (let i = 0; i < rs.length; i++) {
      if (rs[i][0] == null || isNaN(rs[i][0])) continue;
      const x = pad.l+(i/(rs.length-1))*cw;
      const y = pad.t+ch-((rs[i][0]-gMin)/range)*ch;
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
  });

  const canvas = document.getElementById(id);
  if (canvas) {
    let longestRS = rsSeries[0].data;
    rsSeries.forEach(s => { if (s.data.length > longestRS.length) longestRS = s.data; });
    canvas._chartData = { data: longestRS, pad, cw, ch, mn: gMin, range, color: COL.amber, opts: { decimals: 2 }, type: 'line' };
  }
}

// ===== STRATEGY DRAWDOWN (per-page, multi-run overlay) =====
function drawStrategyDrawdown(stratIdx) {
  const strat = STRATEGIES[stratIdx];
  if (!strat) return;
  const id = 'c-strat-'+stratIdx+'-dd';
  const r = resizeCanvas(id);
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  const colors = [strat.color, COL.green, COL.amber, COL.purple, COL.red, COL.accent];

  const selRun = stratSelectedRun[stratIdx];
  let runIds = (selRun && selRun !== 'summary') ? [selRun] : strat.runIds;

  const ddTitle = document.getElementById('dd-title-strat-'+stratIdx);
  if (ddTitle) {
    if (selRun && selRun !== 'summary' && RUN_DATA[selRun]) {
      ddTitle.textContent = 'Drawdown (' + (RUN_DATA[selRun].label || selRun) + ')';
    } else {
      ddTitle.textContent = 'Drawdown (All Runs)';
    }
  }

  const ddSeries = [];
  runIds.forEach((rid, ci) => {
    const rd = RUN_DATA[rid]; if (!rd || !rd.DD || rd.DD.length < 2) return;
    ddSeries.push({ data: rd.DD, color: colors[ci % colors.length], rid: rid });
  });
  if (ddSeries.length === 0) return;

  let gMin = 0;
  ddSeries.forEach(s => s.data.forEach(d => { if (d[0] < gMin) gMin = d[0]; }));
  if (gMin >= 0) gMin = -1;
  const range = 0 - gMin;

  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + (i/4)*ch; const val = 0 - (i/4)*range;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
    ctx.fillText(val.toFixed(1)+'%', w-pad.r+50, y+3.5);
  }

  const showDates = ddSeries.length === 1;
  ddSeries.forEach((s, ci) => {
    const dd = s.data;
    if (showDates && ci === 0) {
      let longestDD = dd;
      ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
      const li = Math.max(1, Math.floor(longestDD.length/6));
      for (let i = 0; i < longestDD.length; i += li) { const x = pad.l+(i/(longestDD.length-1))*cw; ctx.fillText(longestDD[i][1], x, h-5); }
    }
    // Fill area
    ctx.beginPath();
    for (let i = 0; i < dd.length; i++) {
      const x = pad.l+(i/(dd.length-1))*cw;
      const y = pad.t+((0-dd[i][0])/range)*ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.lineTo(pad.l+cw, pad.t); ctx.lineTo(pad.l, pad.t); ctx.closePath();
    ctx.fillStyle = s.color + '15'; ctx.fill();
    // Stroke line
    ctx.beginPath(); ctx.strokeStyle = s.color; ctx.lineWidth = 1.5; ctx.lineJoin = 'round';
    for (let i = 0; i < dd.length; i++) {
      const x = pad.l+(i/(dd.length-1))*cw;
      const y = pad.t+((0-dd[i][0])/range)*ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
  });

  const canvas = document.getElementById(id);
  if (canvas) {
    let longestDD = ddSeries[0].data;
    ddSeries.forEach(s => { if (s.data.length > longestDD.length) longestDD = s.data; });
    canvas._chartData = { data: longestDD, pad, cw, ch, mn: gMin, range, mx: 0, color: COL.red, type: 'area' };
  }
}

// ===== REBUILD (multi mode dynamic) =====
function rebuildOverviewKPIs() {
  var kpiRow = document.getElementById('overview-kpi-row');
  if (!kpiRow) return;

  var isWindowView = selectedRunView !== 'summary';

  // Collect best values from summary metrics
  var sumBest = { cagr:{v:-Infinity,n:''}, sharpe:{v:-Infinity,n:''}, sortino:{v:-Infinity,n:''}, calmar:{v:-Infinity,n:''}, wr:{v:-Infinity,n:''}, dd:{v:Infinity,n:''}, vol:{v:Infinity,n:''}, recovery:{v:-Infinity,n:''} };
  STRATEGIES.forEach(function(s) {
    var m = s.summary;
    if ((m.cagr||0) > sumBest.cagr.v) sumBest.cagr = {v:m.cagr, n:s.name};
    if ((m.sharpe_ratio||0) > sumBest.sharpe.v) sumBest.sharpe = {v:m.sharpe_ratio, n:s.name};
    if ((m.sortino_ratio||0) > sumBest.sortino.v) sumBest.sortino = {v:m.sortino_ratio, n:s.name};
    if ((m.calmar_ratio||0) > sumBest.calmar.v) sumBest.calmar = {v:m.calmar_ratio, n:s.name};
    if ((m.win_rate||0) > sumBest.wr.v) sumBest.wr = {v:m.win_rate, n:s.name};
    if (Math.abs(m.max_drawdown||1) < sumBest.dd.v) sumBest.dd = {v:Math.abs(m.max_drawdown||1), n:s.name};
    if (Math.abs(m.annual_volatility||1) < sumBest.vol.v) sumBest.vol = {v:Math.abs(m.annual_volatility||1), n:s.name};
    var rf = m.recovery_factor;
    if (rf == null && m.total_net_gain_percentage != null && m.max_drawdown != null && Math.abs(m.max_drawdown) > 0) rf = m.total_net_gain_percentage / Math.abs(m.max_drawdown);
    if ((rf||0) > sumBest.recovery.v) sumBest.recovery = {v:rf, n:s.name};
  });

  // Collect best values from selected window (if applicable)
  var winBest = null;
  if (isWindowView) {
    winBest = { cagr:{v:-Infinity,n:''}, sharpe:{v:-Infinity,n:''}, sortino:{v:-Infinity,n:''}, calmar:{v:-Infinity,n:''}, wr:{v:-Infinity,n:''}, dd:{v:Infinity,n:''}, vol:{v:Infinity,n:''}, recovery:{v:-Infinity,n:''} };
    STRATEGIES.forEach(function(s, i) {
      var m = getViewMetrics(i);
      if ((m.cagr||0) > winBest.cagr.v) winBest.cagr = {v:m.cagr, n:s.name};
      if ((m.sharpe_ratio||0) > winBest.sharpe.v) winBest.sharpe = {v:m.sharpe_ratio, n:s.name};
      if ((m.sortino_ratio||0) > winBest.sortino.v) winBest.sortino = {v:m.sortino_ratio, n:s.name};
      if ((m.calmar_ratio||0) > winBest.calmar.v) winBest.calmar = {v:m.calmar_ratio, n:s.name};
      if ((m.win_rate||0) > winBest.wr.v) winBest.wr = {v:m.win_rate, n:s.name};
      if (Math.abs(m.max_drawdown||1) < winBest.dd.v) winBest.dd = {v:Math.abs(m.max_drawdown||1), n:s.name};
      if (Math.abs(m.annual_volatility||1) < winBest.vol.v) winBest.vol = {v:Math.abs(m.annual_volatility||1), n:s.name};
      var rf = m.recovery_factor;
      if (rf == null && m.total_net_gain_percentage != null && m.max_drawdown != null && Math.abs(m.max_drawdown) > 0) rf = m.total_net_gain_percentage / Math.abs(m.max_drawdown);
      if ((rf||0) > winBest.recovery.v) winBest.recovery = {v:rf, n:s.name};
    });
  }

  // Challenger data
  var chal = null;
  if (challengerIdx !== null) {
    var cm = getViewMetrics(challengerIdx);
    var cms = STRATEGIES[challengerIdx].summary;
    var crf = cms.recovery_factor;
    if (crf == null && cms.total_net_gain_percentage != null && cms.max_drawdown != null && Math.abs(cms.max_drawdown) > 0) crf = cms.total_net_gain_percentage / Math.abs(cms.max_drawdown);
    chal = { name: STRATEGIES[challengerIdx].name };
    chal.summary = { cagr:cms.cagr||0, sharpe:cms.sharpe_ratio||0, sortino:cms.sortino_ratio||0, calmar:cms.calmar_ratio||0, wr:cms.win_rate||0, dd:Math.abs(cms.max_drawdown||0), vol:Math.abs(cms.annual_volatility||0), recovery:crf||0 };
    if (isWindowView) {
      var wrf = cm.recovery_factor;
      if (wrf == null && cm.total_net_gain_percentage != null && cm.max_drawdown != null && Math.abs(cm.max_drawdown) > 0) wrf = cm.total_net_gain_percentage / Math.abs(cm.max_drawdown);
      chal.window = { cagr:cm.cagr||0, sharpe:cm.sharpe_ratio||0, sortino:cm.sortino_ratio||0, calmar:cm.calmar_ratio||0, wr:cm.win_rate||0, dd:Math.abs(cm.max_drawdown||0), vol:Math.abs(cm.annual_volatility||0), recovery:wrf||0 };
    }
  }

  function chalLine(chalVal, bestVal, fmt, higherIsBetter) {
    if (!chal) return '';
    var diff = chalVal - bestVal;
    var isEqual = Math.abs(diff) < 0.0001;
    if (isEqual) return '<div class="kpi-chal">\u2691 ' + fmtVal(chalVal, fmt) + ' <span style="color:var(--accent)">= best</span></div>';
    var better = higherIsBetter ? diff > 0 : diff < 0;
    var arrow = better ? '\u25B2' : '\u25BC';
    var color = better ? 'var(--green)' : 'var(--red)';
    var absDiff = Math.abs(diff);
    var diffStr;
    if (fmt === 'pct') diffStr = (diff>0?'+':'') + (diff*1).toFixed(1) + '%';
    else if (fmt === 'pct_abs') diffStr = (better?'\u2212':'+') + (absDiff*1).toFixed(1) + '%';
    else diffStr = (diff>0?'+':'') + diff.toFixed(2);
    return '<div class="kpi-chal">\u2691 ' + fmtVal(chalVal, fmt) + ' <span style="color:'+color+'">' + arrow + ' ' + diffStr + '</span></div>';
  }

  // Get window label
  var windowLabel = '';
  if (isWindowView) {
    for (var li = 0; li < RUN_LABELS.length; li++) {
      if (RUN_LABELS[li][0] === selectedRunView) { windowLabel = RUN_LABELS[li][1]; break; }
    }
    if (windowLabel.length > 25) windowLabel = windowLabel.slice(0, 25) + '\u2026';
  }

  // Define metric KPI cards
  var metrics = [
    { label:'Best CAGR',     sumKey:'cagr',     sumColor:'var(--green)',  fmt:'pct',     hib:true },
    { label:'Best Sharpe',   sumKey:'sharpe',   sumColor:'var(--accent)', fmt:'ratio',   hib:true },
    { label:'Best Sortino',  sumKey:'sortino',  sumColor:'var(--accent)', fmt:'ratio',   hib:true },
    { label:'Best Calmar',   sumKey:'calmar',   sumColor:'var(--accent)', fmt:'ratio',   hib:true },
    { label:'Best Win Rate', sumKey:'wr',       sumColor:'var(--green)',  fmt:'pct_abs', hib:true },
    { label:'Lowest Max DD', sumKey:'dd',       sumColor:'var(--amber)',  fmt:'pct_abs', hib:false },
    { label:'Lowest Vol.',   sumKey:'vol',      sumColor:'var(--amber)',  fmt:'pct_abs', hib:false },
    { label:'Best Recovery',  sumKey:'recovery', sumColor:'var(--accent)', fmt:'ratio',   hib:true },
  ];

  // Remove existing dynamic cards (keep first 2 static cards)
  var existingCards = kpiRow.querySelectorAll('.kpi-card');
  for (var i = existingCards.length - 1; i >= 2; i--) existingCards[i].remove();

  // Build and append metric cards
  metrics.forEach(function(def) {
    var sv = sumBest[def.sumKey];
    var card = document.createElement('div');
    card.className = 'kpi-card';
    var html = '';

    if (isWindowView) {
      // Summary line (smaller, labeled)
      html += '<div class="kpi-label">' + def.label + '</div>';
      html += '<div class="kpi-summary-tag">Summary (All Windows)</div>';
      html += '<div class="kpi-value" style="color:' + def.sumColor + '">' + fmtVal(sv.v, def.fmt) + '</div>';
      html += '<div class="kpi-sub">' + sv.n.slice(0,25) + '</div>';
      // Challenger for summary
      if (chal) html += chalLine(chal.summary[def.sumKey], sv.v, def.fmt, def.hib);
      // Window line
      var wv = winBest[def.sumKey];
      html += '<div class="kpi-window">';
      html += '<div class="kpi-window-label">' + windowLabel + '</div>';
      html += '<div class="kpi-window-value" style="color:' + def.sumColor + '">' + fmtVal(wv.v, def.fmt) + '</div>';
      html += '<div class="kpi-window-sub">' + wv.n.slice(0,25) + '</div>';
      if (chal && chal.window) html += chalLine(chal.window[def.sumKey], wv.v, def.fmt, def.hib);
      html += '</div>';
    } else {
      html += '<div class="kpi-label">' + def.label + '</div>';
      html += '<div class="kpi-value" style="color:' + def.sumColor + '">' + fmtVal(sv.v, def.fmt) + '</div>';
      html += '<div class="kpi-sub">' + sv.n.slice(0,25) + '</div>';
      if (chal) html += chalLine(chal.summary[def.sumKey], sv.v, def.fmt, def.hib);
    }

    card.innerHTML = html;
    kpiRow.appendChild(card);
  });
}

let rankingSortCol = null, rankingSortAsc = false, rankingLimit = 0, rankingPage = 0;

function onRankingLimitChange(value) {
  rankingLimit = parseInt(value);
  rankingPage = 0;
  rebuildRankingTable();
}

function rankingPagePrev() { if (rankingPage > 0) { rankingPage--; rebuildRankingTable(); } }
function rankingPageNext() {
  const pageSize = rankingLimit || STRATEGIES.length;
  if ((rankingPage + 1) * pageSize < STRATEGIES.length) { rankingPage++; rebuildRankingTable(); }
}

function rebuildRankingTable() {
  const tbody = document.querySelector('#comp-table tbody');
  if (!tbody) return;

  // Build sorted index array (filter to selected strategies if any)
  let indices = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);
  if (rankingSortCol) {
    indices.sort((a,b) => {
      const ma = getViewMetrics(a), mb = getViewMetrics(b);
      let va = ma[rankingSortCol], vb = mb[rankingSortCol];
      if (rankingSortCol === '_n_windows') { va = STRATEGIES[a].runIds.length; vb = STRATEGIES[b].runIds.length; }
      if (rankingSortCol === 'cagr') { va = STRATEGIES[a].summary.cagr; vb = STRATEGIES[b].summary.cagr; }
      if (va == null) va = rankingSortAsc ? Infinity : -Infinity;
      if (vb == null) vb = rankingSortAsc ? Infinity : -Infinity;
      if (rankingSortCol === 'max_drawdown') { va = Math.abs(va); vb = Math.abs(vb); }
      return rankingSortAsc ? va - vb : vb - va;
    });
  }

  // Apply pagination
  const total = indices.length;
  const pageSize = (rankingLimit > 0 && rankingLimit < total) ? rankingLimit : total;
  const totalPages = Math.ceil(total / pageSize);
  if (rankingPage >= totalPages) rankingPage = totalPages - 1;
  if (rankingPage < 0) rankingPage = 0;
  const start = rankingPage * pageSize;
  const pageIndices = indices.slice(start, start + pageSize);

  // Count label
  const countEl = document.getElementById('ranking-count');
  if (countEl) {
    if (totalPages > 1) {
      countEl.textContent = 'Showing ' + (start+1) + '\u2013' + (start+pageIndices.length) + ' of ' + total;
    } else {
      countEl.textContent = total + ' strategies';
    }
  }

  // Pagination controls
  const paginationEl = document.getElementById('ranking-pagination');
  const prevBtn = document.getElementById('ranking-prev');
  const nextBtn = document.getElementById('ranking-next');
  const pageInfo = document.getElementById('ranking-page-info');
  if (paginationEl) {
    paginationEl.style.display = totalPages > 1 ? 'flex' : 'none';
  }
  if (prevBtn) prevBtn.disabled = rankingPage === 0;
  if (nextBtn) nextBtn.disabled = rankingPage >= totalPages - 1;
  if (pageInfo) pageInfo.textContent = 'Page ' + (rankingPage+1) + ' of ' + totalPages;

  // Best values (across current page)
  const bestVals = {};
  COMP_COLS.forEach(([label,key,ftype,direction]) => {
    let bestIdx=-1, bestVal=direction==='min'?Infinity:-Infinity;
    pageIndices.forEach(i => {
      const m=getViewMetrics(i); const v = key === 'cagr' ? STRATEGIES[i].summary.cagr : m[key];
      if (v==null) return;
      if (direction==='max' && v>bestVal) { bestVal=v; bestIdx=i; }
      if (direction==='min' && Math.abs(v)<bestVal) { bestVal=Math.abs(v); bestIdx=i; }
    });
    if (bestIdx>=0) bestVals[key]=bestIdx;
  });

  let html = '';
  pageIndices.forEach(i => {
    const s = STRATEGIES[i];
    const m = getViewMetrics(i);
    const isChallenger = challengerIdx === i;
    const chalCls = isChallenger ? ' challenger-row' : '';
    html += '<tr class="comp-row'+chalCls+'">';
    html += '<td class="sticky-col" onclick="showPage(\'strat-'+i+'\')"><span class="sb-dot" style="background:'+s.color+'"></span>'+s.name+'</td>';
    COMP_COLS.forEach(([label,key,ftype,direction]) => {
      const v = key === 'cagr' ? s.summary.cagr : m[key];
      const isBest = bestVals[key]===i;
      const cls = (isBest && pageIndices.length>1) ? ' class="best-cell"' : '';
      if (key==='max_drawdown' && v!=null) html += '<td'+cls+' onclick="showPage(\'strat-'+i+'\')">'+(Math.abs(v)*100).toFixed(1)+'%</td>';
      else if (key==='average_trade_duration' && v!=null) html += '<td'+cls+' onclick="showPage(\'strat-'+i+'\')">'+v.toFixed(1)+'d</td>';
      else html += '<td'+cls+' onclick="showPage(\'strat-'+i+'\')">' + fmtVal(v,ftype) + '</td>';
    });
    html += '</tr>';
  });
  tbody.innerHTML = html;
}

function onRunViewChange(value) {
  selectedRunView = value;
  const overviewSel = document.getElementById('overview-window-select');
  if (overviewSel) overviewSel.value = value;
  const compareSel = document.getElementById('compare-window-select');
  if (compareSel) compareSel.value = value;
  rebuildOverviewKPIs();
  rebuildRankingTable();
  rebuildOverviewTradingActivity();
  rebuildReturnScenarios();
  drawMultiOverviewEquity();
  drawMetricComparison();
  rebuildBenchmarkInsights();
  buildEquityLegend();
  drawMultiOverviewDrawdown();
  drawReturnDistribution();
  buildCorrelationMatrix();
  drawMultiRollingSharpe();
  drawRiskReturnScatter('c-overview-scatter');
  drawRollingReturns('overview');
  setupTooltip('c-overview-eq', 'tt-overview-eq');
  setupTooltip('c-overview-dd', 'tt-overview-dd');
  setupTooltip('c-overview-rsharpe', 'tt-overview-rsharpe');
  // Redraw compare page charts (safe no-ops if elements absent)
  if (selectedForCompare.size >= 2) {
    buildComparePage();
    drawCompareEquity();
    drawCompareMetricBars();
    drawCompareExtras();
    setupTooltip('c-compare-eq', 'tt-compare-eq');
    setupTooltip('c-compare-dd-time', 'tt-compare-dd-time');
    setupTooltip('c-compare-rsharpe', 'tt-compare-rsharpe');
  }
}

// ===== RUN SELECTION (per-strategy drill-down) =====
const stratSelectedRun = {};

function onStratWindowChange(stratIdx, runId) {
  stratSelectedRun[stratIdx] = runId;
  updateStratSummary(stratIdx);
  updateStratPerformance(stratIdx);
  drawStrategyEquity(stratIdx);
  drawStrategyRollingSharpe(stratIdx);
  drawStrategyDrawdown(stratIdx);
  setupTooltip('c-strat-'+stratIdx+'-eq', 'tt-strat-'+stratIdx+'-eq');
  setupTooltip('c-strat-'+stratIdx+'-rsharpe', 'tt-strat-'+stratIdx+'-rsharpe');
  setupTooltip('c-strat-'+stratIdx+'-dd', 'tt-strat-'+stratIdx+'-dd');
  initCollapseButtons();
}

function selectStratRun(stratIdx, runId) {
  onStratWindowChange(stratIdx, runId);
}

function kpiCard(label, value, color, sub) {
  let html = '<div class="kpi-card"><div class="kpi-label">' + label + '</div>';
  html += '<div class="kpi-value"' + (color ? ' style="color:' + color + '"' : '') + '>' + value + '</div>';
  if (sub) html += '<div class="kpi-sub">' + sub + '</div>';
  html += '</div>';
  return html;
}

function updateStratSummary(stratIdx) {
  const sid = 'strat-' + stratIdx;
  const container = document.getElementById(sid + '-summary-content');
  if (!container) return;
  const strat = STRATEGIES[stratIdx];
  const runId = stratSelectedRun[stratIdx] || 'summary';

  // Resolve the run data and metrics
  let m, rd;
  if (runId === 'summary') {
    m = strat.summary;
    // Find best run for EOB snapshot
    let bestRid = strat.runIds[0], bestLen = 0;
    strat.runIds.forEach(function(r) { const d = RUN_DATA[r]; if (d && d.EQ && d.EQ.length > bestLen) { bestLen = d.EQ.length; bestRid = r; } });
    rd = RUN_DATA[bestRid];
  } else {
    rd = RUN_DATA[runId];
    m = (rd && rd.metrics) ? rd.metrics : strat.summary;
  }

  // Derive trades_per_month/week if missing
  if (m.trades_per_month == null && m.trades_per_year != null) m.trades_per_month = m.trades_per_year / 12;
  if (m.trades_per_week == null && m.trades_per_year != null) m.trades_per_week = m.trades_per_year / 52;

  if (runId === 'summary') {
    container.innerHTML = '<div class="kpi-row">'
      + kpiCard('CAGR', fmtVal(m.cagr,'pct'), 'var(--green)')
      + kpiCard('Sharpe', fmtVal(m.sharpe_ratio,'ratio'), 'var(--accent)')
      + kpiCard('Sortino', fmtVal(m.sortino_ratio,'ratio'), 'var(--accent)')
      + kpiCard('Max DD', fmtVal(m.max_drawdown,'pct_abs'), 'var(--red)')
      + kpiCard('Profit Factor', fmtVal(m.profit_factor,'ratio'), 'var(--green)')
      + kpiCard('Win Rate', fmtVal(m.win_rate,'pct_abs'))
      + '</div><div class="kpi-row">'
      + kpiCard('Calmar', fmtVal(m.calmar_ratio,'ratio'), 'var(--accent)')
      + kpiCard('Trades/yr', fmtVal(m.trades_per_year,'ratio'))
      + kpiCard('Volatility', fmtVal(m.annual_volatility,'pct_abs'))
      + kpiCard('Win/Loss', fmtVal(m.win_loss_ratio,'ratio'))
      + kpiCard('DD Duration', m.max_drawdown_duration != null ? Math.round(m.max_drawdown_duration) + 'd' : '—')
      + kpiCard('Exposure', fmtVal(m.exposure_ratio,'pct_abs'))
      + '</div><div class="kpi-row">'
      + kpiCard('Windows', String(m.number_of_windows || 0))
      + kpiCard('Profitable', String(m.number_of_profitable_windows || 0), 'var(--green)')
      + kpiCard('Total Net Gain', fmtVal(m.total_net_gain_percentage,'pct'))
      + kpiCard('Runs', String(strat.runIds.length))
      + '</div>';
  } else {
    var sm = strat.summary;
    container.innerHTML = '<div class="kpi-row">'
      + kpiCard('CAGR', fmtVal(sm.cagr,'pct'), 'var(--green)', 'Run: ' + fmtVal(m.cagr,'pct'))
      + kpiCard('Sharpe', fmtVal(sm.sharpe_ratio,'ratio'), 'var(--accent)', 'Run: ' + fmtVal(m.sharpe_ratio,'ratio'))
      + kpiCard('Sortino', fmtVal(sm.sortino_ratio,'ratio'), 'var(--accent)', 'Run: ' + fmtVal(m.sortino_ratio,'ratio'))
      + kpiCard('Max DD', fmtVal(sm.max_drawdown,'pct_abs'), 'var(--red)', 'Run: ' + fmtVal(m.max_drawdown,'pct_abs'))
      + kpiCard('Profit Factor', fmtVal(sm.profit_factor,'ratio'), 'var(--green)', 'Run: ' + fmtVal(m.profit_factor,'ratio'))
      + kpiCard('Win Rate', fmtVal(sm.win_rate,'pct_abs'), null, 'Run: ' + fmtVal(m.win_rate,'pct_abs'))
      + '</div><div class="kpi-row">'
      + kpiCard('Calmar', fmtVal(sm.calmar_ratio,'ratio'), 'var(--accent)', 'Run: ' + fmtVal(m.calmar_ratio,'ratio'))
      + kpiCard('Trades/yr', fmtVal(sm.trades_per_year,'ratio'), null, 'Run: ' + fmtVal(m.trades_per_year,'ratio'))
      + kpiCard('Volatility', fmtVal(sm.annual_volatility,'pct_abs'), null, 'Run: ' + fmtVal(m.annual_volatility,'pct_abs'))
      + kpiCard('Win/Loss', fmtVal(sm.win_loss_ratio,'ratio'), null, 'Run: ' + fmtVal(m.win_loss_ratio,'ratio'))
      + kpiCard('DD Duration', sm.max_drawdown_duration != null ? Math.round(sm.max_drawdown_duration) + 'd' : '\u2014', null, 'Run: ' + (m.max_drawdown_duration != null ? Math.round(m.max_drawdown_duration) + 'd' : '\u2014'))
      + kpiCard('Exposure', fmtVal(sm.exposure_ratio,'pct_abs'), null, 'Run: ' + fmtVal(m.exposure_ratio,'pct_abs'))
      + '</div>';
  }

  // Portfolio Summary (only when a specific run is selected)
  const psEl = document.getElementById(sid + '-portfolio-summary');
  if (psEl) {
    var sn = (rd && rd.snapshot) ? rd.snapshot : null;
    if (runId !== 'summary' && sn && sn.initial_value != null) {
      var startVal = sn.initial_value;
      var endVal = sn.final_value || 0;
      var netGain = sn.net_gain || 0;
      var growth = sn.growth || 0;
      var gainColor = netGain >= 0 ? 'var(--green)' : 'var(--red)';
      var gp = (m && m.gross_profit != null) ? m.gross_profit : null;
      var gl = (m && m.gross_loss != null) ? m.gross_loss : null;
      var unalloc = sn.unallocated || 0;
      var allocated = endVal - unalloc;
      psEl.innerHTML = '<div class="chart-card">'
        + '<div class="chart-title">Portfolio Summary</div>'
        + '<div class="kpi-row">'
        + kpiCard('Start Value', '\u20AC' + startVal.toFixed(2))
        + kpiCard('End Value', '\u20AC' + endVal.toFixed(2), 'var(--accent)')
        + kpiCard('Net Gain', (netGain >= 0 ? '+' : '') + '\u20AC' + netGain.toFixed(2), gainColor)
        + kpiCard('Growth', (growth >= 0 ? '+' : '') + growth.toFixed(2) + '%', gainColor)
        + (gp != null ? kpiCard('Gross Profit', '\u20AC' + gp.toFixed(2), 'var(--green)') : '')
        + (gl != null ? kpiCard('Gross Loss', '\u20AC' + gl.toFixed(2), 'var(--red)') : '')
        + kpiCard('Allocated', '\u20AC' + allocated.toFixed(2))
        + kpiCard('Unallocated', '\u20AC' + unalloc.toFixed(2))
        + '</div></div>';
    } else {
      psEl.innerHTML = '';
    }
  }

  buildTradingActivity(sid + '-trading-activity', function() { return m; });
}

// Per-strategy monthly/yearly toggle state (per strategy index)
var stratMonthlyData = {};    // stratIdx -> 'returns' | 'growth'
var stratMonthlyDisplay = {}; // stratIdx -> 'rows' | 'heatmap'
var stratMonthlyYear = {};    // stratIdx -> 'all' | year string

function updateStratPerformance(stratIdx) {
  buildStratMonthlyReturns(stratIdx);
  buildStratYearlyReturns(stratIdx);
  buildStratReturnScenarios(stratIdx);
}

function buildStratMonthlyReturns(stratIdx) {
  var sid = 'strat-' + stratIdx;
  var el = document.getElementById(sid + '-monthly-returns');
  if (!el) return;
  var strat = STRATEGIES[stratIdx];
  var runId = stratSelectedRun[stratIdx] || 'summary';
  var rd;
  if (runId === 'summary') {
    var bestRid = strat.runIds[0], bestLen = 0;
    strat.runIds.forEach(function(r) { var d = RUN_DATA[r]; if (d && d.EQ && d.EQ.length > bestLen) { bestLen = d.EQ.length; bestRid = r; } });
    rd = RUN_DATA[bestRid];
  } else {
    rd = RUN_DATA[runId];
  }
  var hm = (rd && rd.MONTHLY_HEATMAP) ? rd.MONTHLY_HEATMAP : {};

  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var allYears = Object.keys(hm).sort();
  if (allYears.length === 0) { el.innerHTML = ''; return; }

  // Init per-strategy state if needed
  if (!stratMonthlyData[stratIdx]) stratMonthlyData[stratIdx] = 'returns';
  if (!stratMonthlyDisplay[stratIdx]) stratMonthlyDisplay[stratIdx] = 'heatmap';
  if (!stratMonthlyYear[stratIdx]) stratMonthlyYear[stratIdx] = 'all';

  var dataMode = stratMonthlyData[stratIdx];
  var dispMode = stratMonthlyDisplay[stratIdx];
  var yearFilter = stratMonthlyYear[stratIdx];
  var filteredYears = yearFilter === 'all' ? allYears : allYears.filter(function(y){ return y === yearFilter; });
  var isGrowth = dataMode === 'growth';
  var isHeatmap = dispMode === 'heatmap';

  var title = (isGrowth ? 'Cumulative Growth' : 'Monthly Returns') + (isHeatmap ? ' (Heatmap)' : '');
  if (rd && rd.label && runId !== 'summary') title += ' \u2013 ' + rd.label;

  var html = '<div class="chart-card">';
  html += '<div class="chart-title">';
  html += '<span>' + title + '</span>';
  html += '<span style="display:flex;gap:0.4rem;align-items:center">';

  // Year filter
  if (allYears.length > 1) {
    html += '<select class="view-select" onchange="stratMonthlyYear['+stratIdx+']=this.value;buildStratMonthlyReturns('+stratIdx+')">';
    html += '<option value="all"' + (yearFilter === 'all' ? ' selected' : '') + '>All Years</option>';
    allYears.forEach(function(y) {
      html += '<option value="'+y+'"' + (yearFilter === y ? ' selected' : '') + '>'+y+'</option>';
    });
    html += '</select>';
  }

  // Data toggle
  [['returns','Returns'],['growth','Growth']].forEach(function(m) {
    var active = dataMode === m[0];
    html += '<button class="view-select" style="cursor:pointer;font-size:0.65rem;padding:2px 8px;'
      + (active ? 'background:var(--accent);color:#fff;border-color:var(--accent)' : '')
      + '" onclick="stratMonthlyData['+stratIdx+']=\''+m[0]+'\';buildStratMonthlyReturns('+stratIdx+')">'+m[1]+'</button>';
  });

  html += '<span style="color:var(--border);font-size:0.7rem">|</span>';

  // Display toggle
  [['rows','Rows'],['heatmap','Heatmap']].forEach(function(m) {
    var active = dispMode === m[0];
    html += '<button class="view-select" style="cursor:pointer;font-size:0.65rem;padding:2px 8px;'
      + (active ? 'background:var(--accent);color:#fff;border-color:var(--accent)' : '')
      + '" onclick="stratMonthlyDisplay['+stratIdx+']=\''+m[0]+'\';buildStratMonthlyReturns('+stratIdx+')">'+m[1]+'</button>';
  });
  html += '</span></div>';

  // Cumulative growth base
  var cumVal = 100;
  if (isGrowth && yearFilter !== 'all') {
    for (var yi = 0; yi < allYears.length; yi++) {
      if (allYears[yi] === yearFilter) break;
      var preY = allYears[yi];
      for (var pmi = 1; pmi <= 12; pmi++) {
        var pv = (hm[preY] && hm[preY][String(pmi)] != null) ? hm[preY][String(pmi)] : 0;
        cumVal *= (1 + pv / 100);
      }
    }
  }

  function fmtReturnCell(v, bgTint) {
    if (v == null) return '<td>\u2014</td>';
    var color = v >= 0 ? 'var(--green)' : 'var(--red)';
    var style = '';
    if (bgTint) {
      var intensity = Math.min(Math.abs(v) / 10, 1);
      var bg = v >= 0 ? 'rgba(34,197,94,' + (intensity * 0.2) + ')' : 'rgba(239,68,68,' + (intensity * 0.2) + ')';
      style = ' style="background:'+bg+'"';
    }
    return '<td'+style+'><span style="color:'+color+'">' + (v >= 0 ? '+' : '') + v.toFixed(1) + '%</span></td>';
  }

  function fmtGrowthCell(val, bgTint) {
    if (val == null) return '<td>\u2014</td>';
    var gain = val - 100;
    var color = gain >= 0 ? 'var(--green)' : 'var(--red)';
    var style = '';
    if (bgTint) {
      var intensity = Math.min(Math.abs(gain) / 50, 1);
      var bg = gain >= 0 ? 'rgba(34,197,94,' + (intensity * 0.15) + ')' : 'rgba(239,68,68,' + (intensity * 0.15) + ')';
      style = ' style="background:'+bg+'"';
    }
    return '<td'+style+'><span style="color:'+color+';font-weight:500">' + val.toFixed(1) + '</span> <span style="font-size:0.6rem;color:var(--text-secondary)">(' + (gain >= 0 ? '+' : '') + gain.toFixed(1) + '%)</span></td>';
  }

  if (!isHeatmap) {
    // === ROWS: months as rows, single strategy ===
    html += '<div class="table-wrap"><table class="comp-table" style="font-size:0.7rem"><thead><tr>';
    html += '<th class="sticky-col">Period</th><th>' + (isGrowth ? 'Growth' : 'Return') + '</th>';
    html += '</tr></thead><tbody>';

    filteredYears.forEach(function(y) {
      // Year summary row
      if (isGrowth) {
        var peekCum = cumVal;
        for (var pmi2 = 1; pmi2 <= 12; pmi2++) {
          var v2 = (hm[y] && hm[y][String(pmi2)] != null) ? hm[y][String(pmi2)] : 0;
          peekCum *= (1 + v2 / 100);
        }
        var gain = peekCum - 100;
        var color = gain >= 0 ? 'var(--green)' : 'var(--red)';
        html += '<tr style="background:var(--surface2);font-weight:600"><td class="sticky-col" style="background:var(--surface2)">' + y + ' End</td>';
        html += '<td style="font-weight:600"><span style="color:'+color+'">' + peekCum.toFixed(1) + '</span></td></tr>';
      } else {
        var yearTotal = 0;
        var hmY = hm[y] || {};
        for (var mi = 1; mi <= 12; mi++) yearTotal += hmY[String(mi)] || 0;
        var color = yearTotal >= 0 ? 'var(--green)' : 'var(--red)';
        html += '<tr style="background:var(--surface2);font-weight:600"><td class="sticky-col" style="background:var(--surface2)">' + y + ' Total</td>';
        html += '<td style="font-weight:600"><span style="color:'+color+'">' + (yearTotal >= 0 ? '+' : '') + yearTotal.toFixed(1) + '%</span></td></tr>';
      }

      // Monthly rows
      for (var mi = 1; mi <= 12; mi++) {
        var v = (hm[y] && hm[y][String(mi)] != null) ? hm[y][String(mi)] : null;
        if (v == null) { if (isGrowth) { /* skip */ } continue; }

        if (isGrowth) cumVal *= (1 + v / 100);

        html += '<tr><td class="sticky-col" style="padding-left:1.5rem;color:var(--text-secondary)">' + MONTHS[mi-1] + ' ' + y + '</td>';
        html += isGrowth ? fmtGrowthCell(cumVal, true) : fmtReturnCell(v, true);
        html += '</tr>';
      }
    });
    html += '</tbody></table></div>';
  } else {
    // === HEATMAP: months as columns, years as rows ===
    var stratCum = isGrowth ? cumVal : 0;

    html += '<table class="heatmap-table"><thead><tr><th></th>';
    MONTHS.forEach(function(m){ html += '<th>'+m+'</th>'; });
    html += '<th>Year</th></tr></thead><tbody>';

    filteredYears.forEach(function(y) {
      html += '<tr><th>'+y+'</th>';
      if (isGrowth) {
        for (var mi = 1; mi <= 12; mi++) {
          var v = (hm[y] && hm[y][String(mi)] != null) ? hm[y][String(mi)] : undefined;
          if (v !== undefined) {
            stratCum *= (1 + v / 100);
            var gain = stratCum - 100;
            var cls = gain > 20 ? 'hm-strong-pos' : gain > 0 ? 'hm-pos' : gain < -10 ? 'hm-strong-neg' : gain < 0 ? 'hm-neg' : 'hm-zero';
            html += '<td class="'+cls+'">'+stratCum.toFixed(0)+'</td>';
          } else {
            html += '<td class="hm-zero">&mdash;</td>';
          }
        }
        var yearGain = stratCum - 100;
        var ycls = yearGain > 0 ? 'hm-pos' : yearGain < 0 ? 'hm-neg' : 'hm-zero';
        html += '<td class="'+ycls+'" style="font-weight:600">' + stratCum.toFixed(0) + '</td></tr>';
      } else {
        var yTotal = 0;
        for (var mi = 1; mi <= 12; mi++) {
          var v = (hm[y] && hm[y][String(mi)] != null) ? hm[y][String(mi)] : undefined;
          if (v !== undefined) {
            yTotal += v;
            var cls = 'hm-zero';
            if (v > 10) cls = 'hm-strong-pos';
            else if (v > 0) cls = 'hm-pos';
            else if (v < -3) cls = 'hm-strong-neg';
            else if (v < 0) cls = 'hm-neg';
            html += '<td class="'+cls+'">'+(v>0?'+':'')+v.toFixed(1)+'%</td>';
          } else {
            html += '<td class="hm-zero">&mdash;</td>';
          }
        }
        var ycls = yTotal > 0 ? 'hm-pos' : yTotal < 0 ? 'hm-neg' : 'hm-zero';
        html += '<td class="'+ycls+'" style="font-weight:600">'+(yTotal>0?'+':'')+yTotal.toFixed(1)+'%</td></tr>';
      }
    });
    html += '</tbody></table>';
  }

  html += '</div>';
  el.innerHTML = html;
  initCollapseButtons();
}

// Per-strategy yearly toggle state
var stratYearlyData = {};    // stratIdx -> 'returns' | 'growth'
var stratYearlyDisplay = {}; // stratIdx -> 'bar' | 'table'

function buildStratYearlyReturns(stratIdx) {
  var sid = 'strat-' + stratIdx;
  var el = document.getElementById(sid + '-yearly-returns');
  if (!el) return;
  var strat = STRATEGIES[stratIdx];
  var runId = stratSelectedRun[stratIdx] || 'summary';
  var rd;
  if (runId === 'summary') {
    var bestRid = strat.runIds[0], bestLen = 0;
    strat.runIds.forEach(function(r) { var d = RUN_DATA[r]; if (d && d.EQ && d.EQ.length > bestLen) { bestLen = d.EQ.length; bestRid = r; } });
    rd = RUN_DATA[bestRid];
  } else {
    rd = RUN_DATA[runId];
  }
  if (!rd || !rd.YR || rd.YR.length === 0) { el.innerHTML = ''; return; }

  // Init per-strategy state if needed
  if (!stratYearlyData[stratIdx]) stratYearlyData[stratIdx] = 'returns';
  if (!stratYearlyDisplay[stratIdx]) stratYearlyDisplay[stratIdx] = 'bar';

  var dataMode = stratYearlyData[stratIdx];
  var dispMode = stratYearlyDisplay[stratIdx];
  var isGrowth = dataMode === 'growth';
  var isTable = dispMode === 'table';

  var titleSuffix = '';
  if (runId !== 'summary' && rd && rd.label) titleSuffix = ' \u2013 ' + rd.label;
  var title = (isGrowth ? 'Cumulative Growth (Yearly)' : 'Yearly Returns') + titleSuffix;

  var html = '<div class="chart-card">';
  html += '<div class="chart-title">';
  html += '<span>' + title + '</span>';
  html += '<span style="display:flex;gap:0.4rem;align-items:center">';

  // Data toggle
  [['returns','Returns'],['growth','Growth']].forEach(function(m) {
    var active = dataMode === m[0];
    html += '<button class="view-select" style="cursor:pointer;font-size:0.65rem;padding:2px 8px;'
      + (active ? 'background:var(--accent);color:#fff;border-color:var(--accent)' : '')
      + '" onclick="stratYearlyData['+stratIdx+']=\''+m[0]+'\';buildStratYearlyReturns('+stratIdx+')">'+m[1]+'</button>';
  });

  html += '<span style="color:var(--border);font-size:0.7rem">|</span>';

  // Display toggle
  [['bar','Bar Chart'],['table','Table']].forEach(function(m) {
    var active = dispMode === m[0];
    html += '<button class="view-select" style="cursor:pointer;font-size:0.65rem;padding:2px 8px;'
      + (active ? 'background:var(--accent);color:#fff;border-color:var(--accent)' : '')
      + '" onclick="stratYearlyDisplay['+stratIdx+']=\''+m[0]+'\';buildStratYearlyReturns('+stratIdx+')">'+m[1]+'</button>';
  });
  html += '</span></div>';

  var yr = rd.YR; // [[pct, yearLabel], ...]

  if (isTable) {
    html += '<div class="table-wrap"><table class="comp-table" style="font-size:0.7rem"><thead><tr>';
    html += '<th class="sticky-col">Year</th><th>' + (isGrowth ? 'Growth' : 'Return') + '</th>';
    html += '</tr></thead><tbody>';

    var cumVal = 100;
    yr.forEach(function(d) {
      var pct = d[0], label = d[1];
      if (isGrowth) {
        cumVal *= (1 + pct / 100);
        var gain = cumVal - 100;
        var color = gain >= 0 ? 'var(--green)' : 'var(--red)';
        var intensity = Math.min(Math.abs(gain) / 50, 1);
        var bg = gain >= 0 ? 'rgba(34,197,94,' + (intensity * 0.15) + ')' : 'rgba(239,68,68,' + (intensity * 0.15) + ')';
        html += '<tr><td class="sticky-col">' + label + '</td>';
        html += '<td style="background:'+bg+'"><span style="color:'+color+';font-weight:500">' + cumVal.toFixed(1) + '</span>';
        html += ' <span style="font-size:0.6rem;color:var(--text-secondary)">(' + (gain >= 0 ? '+' : '') + gain.toFixed(1) + '%)</span></td></tr>';
      } else {
        var color = pct >= 0 ? 'var(--green)' : 'var(--red)';
        var intensity = Math.min(Math.abs(pct) / 30, 1);
        var bg = pct >= 0 ? 'rgba(34,197,94,' + (intensity * 0.2) + ')' : 'rgba(239,68,68,' + (intensity * 0.2) + ')';
        html += '<tr><td class="sticky-col">' + label + '</td>';
        html += '<td style="background:'+bg+'"><span style="color:'+color+'">' + (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%</span></td></tr>';
      }
    });
    html += '</tbody></table></div>';
    html += '</div>';
    el.innerHTML = html;
    initCollapseButtons();
  } else {
    // Bar chart mode
    var barData;
    if (isGrowth) {
      var cumVal = 100;
      barData = yr.map(function(d) {
        cumVal *= (1 + d[0] / 100);
        return [cumVal - 100, d[1]];
      });
    } else {
      barData = yr;
    }
    html += '<div class="chart-wrap chart-sm"><canvas id="c-' + sid + '-yearly"></canvas></div>';
    html += '</div>';
    el.innerHTML = html;
    initCollapseButtons();
    requestAnimationFrame(function() {
      drawBarChart('c-' + sid + '-yearly', barData);
    });
  }
}

function buildStratReturnScenarios(stratIdx) {
  const sid = 'strat-' + stratIdx;
  const el = document.getElementById(sid + '-return-scenarios');
  if (!el) return;
  const strat = STRATEGIES[stratIdx];
  const sm = strat.summary;
  const cagr = sm.cagr;
  const vol = sm.annual_volatility;
  const hasBoth = cagr != null && vol != null;
  const good = hasBoth ? (cagr + vol) * 100 : null;
  const avg = cagr != null ? cagr * 100 : null;
  const bad = hasBoth ? (cagr - vol) * 100 : null;
  const vbad = hasBoth ? (cagr - 2 * vol) * 100 : null;

  function fmtScenario(v) {
    if (v == null) return '\u2014';
    var color = v >= 0 ? 'var(--green)' : 'var(--red)';
    return '<span style="color:' + color + '">' + (v >= 0 ? '+' : '') + v.toFixed(1) + '%</span>';
  }

  // Also show per-run scenarios if a window is selected
  const runId = stratSelectedRun[stratIdx] || 'summary';
  let runRow = '';
  if (runId !== 'summary') {
    const rd = RUN_DATA[runId];
    const rm = (rd && rd.metrics) ? rd.metrics : null;
    if (rm) {
      const rc = rm.cagr, rv = rm.annual_volatility;
      const rh = rc != null && rv != null;
      runRow = '<tr style="opacity:0.7">';
      runRow += '<td class="sticky-col" style="font-size:0.75rem">' + (rd.label || runId) + '</td>';
      runRow += '<td>' + fmtVal(rc, 'pct') + '</td>';
      runRow += '<td>' + fmtVal(rv, 'pct_abs') + '</td>';
      runRow += '<td>' + fmtScenario(rh ? (rc + rv) * 100 : null) + '</td>';
      runRow += '<td>' + fmtScenario(rc != null ? rc * 100 : null) + '</td>';
      runRow += '<td>' + fmtScenario(rh ? (rc - rv) * 100 : null) + '</td>';
      runRow += '<td>' + fmtScenario(rh ? (rc - 2 * rv) * 100 : null) + '</td>';
      runRow += '</tr>';
    }
  }

  let html = '<div class="chart-card">';
  html += '<div class="chart-title">Return Scenarios (Annual)</div>';
  html += '<div class="table-wrap"><table class="comp-table"><thead><tr>';
  html += '<th class="sticky-col"></th>';
  html += '<th>CAGR</th>';
  html += '<th>Volatility</th>';
  html += '<th style="color:var(--green)">Good Year</th>';
  html += '<th>Average Year</th>';
  html += '<th style="color:var(--amber)">Bad Year</th>';
  html += '<th style="color:var(--red)">Very Bad Year (2\u03C3)</th>';
  html += '</tr></thead><tbody>';
  html += '<tr>';
  html += '<td class="sticky-col"><span class="sb-dot" style="background:'+strat.color+'"></span>Summary</td>';
  html += '<td>' + fmtVal(cagr, 'pct') + '</td>';
  html += '<td>' + fmtVal(vol, 'pct_abs') + '</td>';
  html += '<td>' + fmtScenario(good) + '</td>';
  html += '<td>' + fmtScenario(avg) + '</td>';
  html += '<td>' + fmtScenario(bad) + '</td>';
  html += '<td>' + fmtScenario(vbad) + '</td>';
  html += '</tr>';
  html += runRow;
  html += '</tbody></table></div></div>';
  el.innerHTML = html;
  initCollapseButtons();
}

// ===== TABLE SORTING (multi mode) =====
(function() {
  const table = document.getElementById('comp-table');
  if (!table) return;
  const headers = table.querySelectorAll('th[data-col]');
  headers.forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (rankingSortCol === col) rankingSortAsc = !rankingSortAsc;
      else { rankingSortCol = col; rankingSortAsc = false; }
      headers.forEach(h => { const a=h.querySelector('.sort-arrow'); if(a) a.textContent='\u25B2'; });
      const arrow = th.querySelector('.sort-arrow');
      if (arrow) arrow.textContent = rankingSortAsc ? '\u25B2' : '\u25BC';
      rebuildRankingTable();
    });
  });
})();

// ===== BENCHMARK VISIBILITY =====
const benchmarkVisible = new Set(
  (typeof BENCHMARKS !== 'undefined' ? BENCHMARKS : []).map((_, i) => i)
);

function toggleBenchmark(idx) {
  if (benchmarkVisible.has(idx)) benchmarkVisible.delete(idx);
  else benchmarkVisible.add(idx);
  const chip = document.querySelector('.bench-chip[data-bench="'+idx+'"]');
  if (chip) chip.classList.toggle('bench-off', !benchmarkVisible.has(idx));
  drawMultiOverviewEquity();
  rebuildBenchmarkInsights();
  buildEquityLegend();
  setupTooltip('c-overview-eq', 'tt-overview-eq');
}

function buildBenchmarkChips() {
  const container = document.getElementById('benchmark-chips');
  if (!container || typeof BENCHMARKS === 'undefined' || !BENCHMARKS.length) return;
  container.innerHTML = BENCHMARKS.map((b, i) =>
    '<button class="bench-chip" data-bench="'+i+'" onclick="toggleBenchmark('+i+')">' +
    '<span class="bench-dot" style="background:'+b.color+'"></span>' +
    b.name + '</button>'
  ).join('');
}

function getBenchmarkEquity(benchIdx) {
  const b = BENCHMARKS[benchIdx];
  if (!b) return [];
  if (selectedRunView === 'summary') return b.summaryEQ || [];
  return (b.windowEQ && b.windowEQ[selectedRunView]) || [];
}

// ===== COLLAPSIBLE CARDS =====
function toggleCollapse(btn) {
  var card = btn.closest('.chart-card');
  if (card) card.classList.toggle('collapsed');
}
function initCollapseButtons() {
  var titles = document.querySelectorAll('.chart-card > .chart-title');
  titles.forEach(function(t) {
    if (t.querySelector('.collapse-btn')) return;
    var btn = document.createElement('button');
    btn.className = 'collapse-btn';
    btn.title = 'Collapse / Expand';
    btn.innerHTML = '&#9650;';
    btn.setAttribute('onclick', 'event.stopPropagation();toggleCollapse(this)');
    t.appendChild(btn);
  });
}

// ===== CHALLENGER SELECTION =====
let challengerIdx = null;

function toggleChallenger(idx, event) {
  if (event) event.stopPropagation();
  challengerIdx = challengerIdx === idx ? null : idx;
  // Update sidebar challenger badges
  document.querySelectorAll('.sb-challenger').forEach(el => el.remove());
  if (challengerIdx !== null) {
    const sbItems = document.querySelectorAll('.sb-item[data-page^="strat-"]');
    if (sbItems[challengerIdx]) {
      const badge = document.createElement('span');
      badge.className = 'sb-challenger';
      badge.textContent = '\u2691';
      sbItems[challengerIdx].appendChild(badge);
    }
  }
  rebuildOverviewKPIs();
  rebuildRankingTable();
  drawMultiOverviewEquity();
  drawMetricComparison();
  rebuildBenchmarkInsights();
  buildEquityLegend();
  drawMultiOverviewDrawdown();
  drawReturnDistribution();
  buildCorrelationMatrix();
  drawMultiRollingSharpe();
  rebuildOverviewTradingActivity();
  rebuildReturnScenarios();
  setupTooltip('c-overview-eq', 'tt-overview-eq');
  setupTooltip('c-overview-dd', 'tt-overview-dd');
  setupTooltip('c-overview-rsharpe', 'tt-overview-rsharpe');
}

// ===== COMPARE SELECTION =====
const selectedForCompare = new Set();

function toggleStratCompare(idx, checked) {
  if (checked) selectedForCompare.add(idx);
  else selectedForCompare.delete(idx);
  updateCompareUI();
}

function toggleAllStrats(el) {
  if (el.checked) STRATEGIES.forEach((_, i) => selectedForCompare.add(i));
  else selectedForCompare.clear();
  document.querySelectorAll('#comp-table .strat-checkbox[data-strat-idx]').forEach(cb => cb.checked = el.checked);
  updateCompareUI();
}

function updateCompareUI() {
  const btn = document.getElementById('compare-btn');
  const countEl = document.getElementById('compare-count');
  const sbItem = document.getElementById('sb-compare');
  const n = selectedForCompare.size;
  if (countEl) countEl.textContent = n;
  if (btn) btn.classList.toggle('visible', n >= 2);
  if (sbItem) sbItem.style.display = n >= 2 ? '' : 'none';
  if (STRATEGIES.length > 1) {
    rebuildWindowCoverage();
    rebuildRankingTable();
    drawMultiOverviewEquity();
    drawMetricComparison();
    rebuildBenchmarkInsights();
    buildEquityLegend();
    drawMultiOverviewDrawdown();
    drawReturnDistribution();
    buildCorrelationMatrix();
    drawMultiRollingSharpe();
    rebuildOverviewTradingActivity();
    rebuildReturnScenarios();
    drawRiskReturnScatter('c-overview-scatter');
    drawRollingReturns('overview');
    setupTooltip('c-overview-eq', 'tt-overview-eq');
    setupTooltip('c-overview-dd', 'tt-overview-dd');
    setupTooltip('c-overview-rsharpe', 'tt-overview-rsharpe');
  }
}

// ===== STRATEGY SELECTION MODAL =====
var modalSortCol = null, modalSortAsc = false, modalPage = 0, modalPageSize = 25;

function openStrategyModal() {
  var overlay = document.getElementById('strat-modal-overlay');
  if (!overlay) return;
  modalPage = 0;
  rebuildStrategyModal();
  overlay.classList.add('open');
  document.addEventListener('keydown', modalEscHandler);
}

function closeStrategyModal() {
  // Auto-apply parameter filters if any are active
  var hasActiveFilters = Object.keys(paramFilters).some(function(k) {
    var f = paramFilters[k];
    return (f.selected && f.selected.size > 0) || f.min != null || f.max != null;
  });
  if (hasActiveFilters) {
    applyParamFiltersQuiet();
  }
  var overlay = document.getElementById('strat-modal-overlay');
  if (overlay) overlay.classList.remove('open');
  document.removeEventListener('keydown', modalEscHandler);
  updateCompareUI();
  rebuildOverviewKPIs();
}

function modalEscHandler(e) { if (e.key === 'Escape') closeStrategyModal(); }

function modalPageSizeChange(val) {
  modalPageSize = parseInt(val);
  modalPage = 0;
  rebuildStrategyModal();
}
function modalPagePrev() { if (modalPage > 0) { modalPage--; rebuildStrategyModal(); } }
function modalPageNext() {
  var total = STRATEGIES.length;
  var ps = modalPageSize > 0 ? modalPageSize : total;
  if ((modalPage + 1) * ps < total) { modalPage++; rebuildStrategyModal(); }
}

function getModalMetricVal(m, key) {
  var v = key === 'cagr' ? m.cagr : m[key];
  if (key === 'recovery_factor' && v == null && m.total_net_gain_percentage != null && m.max_drawdown != null && Math.abs(m.max_drawdown) > 0) {
    v = m.total_net_gain_percentage / Math.abs(m.max_drawdown);
  }
  return v;
}

function rebuildStrategyModal() {
  var body = document.getElementById('strat-modal-body');
  if (!body) return;

  // Build sorted indices
  var indices = STRATEGIES.map(function(_,i){return i;});
  if (modalSortCol) {
    indices.sort(function(a,b) {
      var ma = STRATEGIES[a].summary, mb = STRATEGIES[b].summary;
      var va = getModalMetricVal(ma, modalSortCol);
      var vb = getModalMetricVal(mb, modalSortCol);
      if (modalSortCol === 'max_drawdown' || modalSortCol === 'annual_volatility') {
        va = va != null ? Math.abs(va) : null;
        vb = vb != null ? Math.abs(vb) : null;
      }
      if (va == null) va = modalSortAsc ? Infinity : -Infinity;
      if (vb == null) vb = modalSortAsc ? Infinity : -Infinity;
      return modalSortAsc ? va - vb : vb - va;
    });
  }

  // Pagination
  var total = indices.length;
  var ps = modalPageSize > 0 && modalPageSize < total ? modalPageSize : total;
  var totalPages = Math.ceil(total / ps);
  if (modalPage >= totalPages) modalPage = totalPages - 1;
  if (modalPage < 0) modalPage = 0;
  var start = modalPage * ps;
  var pageIndices = indices.slice(start, start + ps);

  // Best values across ALL strategies (not just page)
  var bestVals = {};
  COMP_COLS.forEach(function(col) {
    var key = col[1], direction = col[3];
    var bestIdx = -1, bestVal = direction === 'min' ? Infinity : -Infinity;
    indices.forEach(function(i) {
      var v = getModalMetricVal(STRATEGIES[i].summary, key);
      if (v == null) return;
      var av = (direction === 'min') ? Math.abs(v) : v;
      if (direction === 'max' && v > bestVal) { bestVal = v; bestIdx = i; }
      if (direction === 'min' && Math.abs(v) < bestVal) { bestVal = Math.abs(v); bestIdx = i; }
    });
    if (bestIdx >= 0) bestVals[key] = bestIdx;
  });

  // Build table
  var html = '<table class="comp-table" id="modal-table" style="width:100%;font-size:0.72rem">';
  html += '<thead><tr>';
  html += '<th class="check-col" style="padding:8px"><input type="checkbox" id="modal-select-all-inner"></th>';
  html += '<th class="sticky-col">Strategy</th>';
  COMP_COLS.forEach(function(col) {
    var key = col[1];
    var arrow = '';
    if (modalSortCol === key) arrow = modalSortAsc ? ' \u25B2' : ' \u25BC';
    html += '<th data-modal-col="' + key + '" style="cursor:pointer">' + col[0] + arrow + '</th>';
  });
  html += '</tr></thead><tbody>';

  pageIndices.forEach(function(i) {
    var s = STRATEGIES[i];
    var m = s.summary;
    var checked = selectedForCompare.has(i) ? ' checked' : '';
    var isChallenger = challengerIdx === i;
    var chalCls = isChallenger ? ' challenger-row' : '';
    html += '<tr class="comp-row' + chalCls + '">';
    html += '<td class="check-col" style="padding:8px"><input type="checkbox" class="modal-strat-cb" data-idx="' + i + '"' + checked + '><button class="challenger-btn' + (isChallenger ? ' active' : '') + '" title="' + (isChallenger ? 'Remove' : 'Set as') + ' challenger" onclick="modalToggleChallenger(' + i + ',event)">\u2691</button></td>';
    html += '<td class="sticky-col"><span class="sb-dot" style="background:' + s.color + '"></span>' + s.name + '</td>';
    COMP_COLS.forEach(function(col) {
      var key = col[1], ftype = col[2];
      var v = getModalMetricVal(m, key);
      var isBest = bestVals[key] === i;
      var cls = isBest && total > 1 ? ' class="best-cell"' : '';
      if (key === 'max_drawdown' && v != null) html += '<td' + cls + '>' + (Math.abs(v) * 100).toFixed(1) + '%</td>';
      else html += '<td' + cls + '>' + fmtVal(v, ftype) + '</td>';
    });
    html += '</tr>';
  });

  html += '</tbody></table>';
  body.innerHTML = html;

  // Pagination controls
  var prevBtn = document.getElementById('modal-prev');
  var nextBtn = document.getElementById('modal-next');
  var pageInfo = document.getElementById('modal-page-info');
  if (prevBtn) prevBtn.disabled = modalPage === 0;
  if (nextBtn) nextBtn.disabled = modalPage >= totalPages - 1;
  if (pageInfo) {
    if (totalPages > 1) pageInfo.textContent = (start+1) + '\u2013' + (start+pageIndices.length) + ' of ' + total;
    else pageInfo.textContent = total + ' strategies';
  }

  // Sort handlers
  body.querySelectorAll('th[data-modal-col]').forEach(function(th) {
    th.addEventListener('click', function() {
      var col = this.dataset.modalCol;
      if (modalSortCol === col) modalSortAsc = !modalSortAsc;
      else { modalSortCol = col; modalSortAsc = false; }
      modalPage = 0;
      rebuildStrategyModal();
    });
  });

  // Checkbox handlers
  body.querySelectorAll('.modal-strat-cb').forEach(function(cb) {
    cb.addEventListener('change', function() {
      var idx = parseInt(this.dataset.idx);
      if (this.checked) selectedForCompare.add(idx);
      else selectedForCompare.delete(idx);
      syncModalCount();
      syncMainTableCheckboxes();
      updateCompareUI();
    });
  });

  // Select-all in table header
  var selAllInner = document.getElementById('modal-select-all-inner');
  if (selAllInner) {
    selAllInner.checked = selectedForCompare.size === STRATEGIES.length;
    selAllInner.addEventListener('change', function() {
      var checked = this.checked;
      if (checked) STRATEGIES.forEach(function(_, i) { selectedForCompare.add(i); });
      else selectedForCompare.clear();
      body.querySelectorAll('.modal-strat-cb').forEach(function(cb) { cb.checked = checked; });
      syncModalCount();
      syncMainTableCheckboxes();
      updateCompareUI();
    });
  }

  // Sync header "All" checkbox
  var selAllHeader = document.getElementById('modal-select-all');
  if (selAllHeader) selAllHeader.checked = selectedForCompare.size === STRATEGIES.length;

  syncModalCount();
}

function syncModalCount() {
  var n = selectedForCompare.size;
  var total = STRATEGIES.length;
  var countEl = document.getElementById('modal-selected-count');
  if (countEl) {
    if (n === 0) countEl.textContent = 'None selected';
    else if (n === total) countEl.textContent = 'All ' + total + ' strategies selected';
    else countEl.textContent = n + ' of ' + total + ' strategies selected';
  }
  var btn = document.getElementById('strat-select-btn');
  if (btn) {
    if (n === 0 || n === total) btn.innerHTML = 'All Strategies (' + total + ')';
    else btn.innerHTML = n + ' Strategies <span style="font-weight:700;color:var(--accent)">/ ' + total + '</span>';
  }
  // Update all mirror strategy-select buttons (e.g. windows page)
  document.querySelectorAll('.strat-select-count-mirror').forEach(function(el) {
    el.textContent = (n > 0 && n < total) ? '/ ' + total : '';
    var mirrorBtn = el.parentElement;
    if (mirrorBtn && mirrorBtn.classList.contains('view-select')) {
      var label = (n === 0 || n === total) ? 'All Strategies (' + total + ')' : n + ' Strategies ';
      mirrorBtn.innerHTML = label + '<span class="strat-select-count-mirror" style="font-weight:700;color:var(--accent)">' + ((n > 0 && n < total) ? '/ ' + total : '') + '</span>';
    }
  });
}

function modalToggleChallenger(idx, event) {
  if (event) event.stopPropagation();
  challengerIdx = challengerIdx === idx ? null : idx;
  // Update sidebar challenger badges
  document.querySelectorAll('.sb-challenger').forEach(function(el) { el.remove(); });
  if (challengerIdx !== null) {
    var sbItems = document.querySelectorAll('.sb-item[data-page^="strat-"]');
    if (sbItems[challengerIdx]) {
      var badge = document.createElement('span');
      badge.className = 'sb-challenger';
      badge.textContent = '\u2691';
      sbItems[challengerIdx].appendChild(badge);
    }
  }
  // Rebuild modal to reflect new challenger
  rebuildStrategyModal();
  // Update overview page
  rebuildOverviewKPIs();
  rebuildRankingTable();
  drawMultiOverviewEquity();
  drawMetricComparison();
  rebuildBenchmarkInsights();
  buildEquityLegend();
  drawMultiOverviewDrawdown();
  drawReturnDistribution();
  buildCorrelationMatrix();
  drawMultiRollingSharpe();
  rebuildOverviewTradingActivity();
  rebuildReturnScenarios();
  setupTooltip('c-overview-eq', 'tt-overview-eq');
  setupTooltip('c-overview-dd', 'tt-overview-dd');
  setupTooltip('c-overview-rsharpe', 'tt-overview-rsharpe');
}

function syncMainTableCheckboxes() {
  document.querySelectorAll('#comp-table .strat-checkbox[data-strat-idx]').forEach(function(cb) {
    cb.checked = selectedForCompare.has(parseInt(cb.dataset.stratIdx));
  });
  var selAll = document.getElementById('select-all-strats');
  if (selAll) selAll.checked = selectedForCompare.size === STRATEGIES.length;
}

function modalToggleAll(el) {
  var checked = el.checked;
  if (checked) STRATEGIES.forEach(function(_, i) { selectedForCompare.add(i); });
  else selectedForCompare.clear();
  var body = document.getElementById('strat-modal-body');
  if (body) body.querySelectorAll('.modal-strat-cb').forEach(function(cb) { cb.checked = checked; });
  var selAllInner = document.getElementById('modal-select-all-inner');
  if (selAllInner) selAllInner.checked = checked;
  syncModalCount();
  syncMainTableCheckboxes();
  updateCompareUI();
}

// ===== MODAL TABS: METRICS / PARAMETERS =====
var currentModalTab = 'metrics';
var paramFilters = {}; // { paramKey: { type:'discrete'|'range', selected:Set, min:number, max:number } }

function switchModalTab(tab) {
  currentModalTab = tab;
  var metricsBody = document.getElementById('strat-modal-body');
  var paramsBody = document.getElementById('strat-modal-params-body');
  var footer = document.querySelector('.modal-footer');
  document.querySelectorAll('.modal-tab').forEach(function(t) {
    t.classList.toggle('active', t.dataset.modalTab === tab);
  });
  if (tab === 'metrics') {
    if (metricsBody) metricsBody.style.display = '';
    if (paramsBody) paramsBody.style.display = 'none';
  } else {
    if (metricsBody) metricsBody.style.display = 'none';
    if (paramsBody) paramsBody.style.display = '';
    rebuildModalParams();
  }
}

function rebuildModalParams() {
  var body = document.getElementById('strat-modal-params-body');
  if (!body) return;

  // Collect all parameter keys and their unique values across strategies
  var paramInfo = {}; // { key: { values: Set, allNumeric: bool } }
  STRATEGIES.forEach(function(s) {
    var p = s.parameters;
    if (!p) return;
    Object.keys(p).forEach(function(key) {
      if (!paramInfo[key]) paramInfo[key] = { values: new Set(), allNumeric: true };
      var v = p[key];
      var display = (typeof v === 'object' && v !== null) ? JSON.stringify(v) : String(v);
      paramInfo[key].values.add(display);
      if (typeof v !== 'number') paramInfo[key].allNumeric = false;
    });
  });

  var keys = Object.keys(paramInfo).sort();
  if (keys.length === 0) {
    body.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--text-dim);font-size:0.8rem">No strategy parameters found.</div>';
    return;
  }

  // Count matching strategies
  var matchCount = countParamFilterMatches();

  var html = '<div class="param-filter-actions">';
  html += '<button class="param-filter-apply" onclick="applyParamFilters()">Select ' + matchCount + ' matching</button>';
  html += '<button class="param-filter-reset" onclick="resetParamFilters()">Reset filters</button>';
  html += '<span style="margin-left:auto;font-size:0.72rem;color:var(--text-dim)">' + matchCount + ' of ' + STRATEGIES.length + ' strategies match</span>';
  html += '</div>';

  keys.forEach(function(key) {
    var info = paramInfo[key];
    var vals = Array.from(info.values).sort();
    var filter = paramFilters[key];

    html += '<div class="param-filter-row">';
    html += '<div class="param-filter-label">' + key + '</div>';
    html += '<div class="param-filter-controls">';

    if (info.allNumeric && vals.length > 2) {
      // Numeric range filter
      var nums = [];
      STRATEGIES.forEach(function(s) {
        if (s.parameters && s.parameters[key] != null) nums.push(s.parameters[key]);
      });
      var minVal = Math.min.apply(null, nums);
      var maxVal = Math.max.apply(null, nums);
      var curMin = (filter && filter.min != null) ? filter.min : '';
      var curMax = (filter && filter.max != null) ? filter.max : '';

      html += '<div class="param-filter-range">';
      html += '<span>min</span><input type="number" step="any" placeholder="' + minVal + '" value="' + curMin + '" data-param="' + key + '" data-bound="min" onchange="onParamRangeChange(this)">';
      html += '<span>&ndash;</span>';
      html += '<span>max</span><input type="number" step="any" placeholder="' + maxVal + '" value="' + curMax + '" data-param="' + key + '" data-bound="max" onchange="onParamRangeChange(this)">';
      html += '</div>';

      // Also show chip values
      html += '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-left:8px">';
      vals.forEach(function(v) {
        var isSelected = filter && filter.selected && filter.selected.has(v);
        html += '<span class="param-filter-chip' + (isSelected ? ' selected' : '') + '" data-param="' + key + '" data-value="' + v + '" onclick="toggleParamChip(this)">' + v + '</span>';
      });
      html += '</div>';
    } else {
      // Discrete chip filter
      vals.forEach(function(v) {
        var isSelected = filter && filter.selected && filter.selected.has(v);
        html += '<span class="param-filter-chip' + (isSelected ? ' selected' : '') + '" data-param="' + key + '" data-value="' + v + '" onclick="toggleParamChip(this)">' + v + '</span>';
      });
    }

    html += '</div></div>';
  });

  body.innerHTML = html;
}

function toggleParamChip(el) {
  var key = el.dataset.param;
  var val = el.dataset.value;
  if (!paramFilters[key]) paramFilters[key] = { selected: new Set(), min: null, max: null };
  var filter = paramFilters[key];
  if (filter.selected.has(val)) {
    filter.selected.delete(val);
    el.classList.remove('selected');
  } else {
    filter.selected.add(val);
    el.classList.add('selected');
  }
  // Clear range if chips are used
  filter.min = null;
  filter.max = null;
  updateParamFilterCount();
}

function onParamRangeChange(input) {
  var key = input.dataset.param;
  var bound = input.dataset.bound;
  if (!paramFilters[key]) paramFilters[key] = { selected: new Set(), min: null, max: null };
  var val = input.value !== '' ? parseFloat(input.value) : null;
  paramFilters[key][bound] = val;
  // Clear chip selection when range is used
  paramFilters[key].selected = new Set();
  // Re-render to update chip states
  rebuildModalParams();
}

function countParamFilterMatches() {
  var count = 0;
  STRATEGIES.forEach(function(s) {
    if (strategyMatchesParamFilters(s)) count++;
  });
  return count;
}

function strategyMatchesParamFilters(s) {
  var params = s.parameters || {};
  var keys = Object.keys(paramFilters);
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    var filter = paramFilters[key];
    var hasChips = filter.selected && filter.selected.size > 0;
    var hasRange = filter.min != null || filter.max != null;
    if (!hasChips && !hasRange) continue; // No filter active for this key

    var val = params[key];
    if (val === undefined) return false; // Strategy doesn't have this param

    if (hasChips) {
      var display = (typeof val === 'object' && val !== null) ? JSON.stringify(val) : String(val);
      if (!filter.selected.has(display)) return false;
    }

    if (hasRange) {
      if (typeof val !== 'number') return false;
      if (filter.min != null && val < filter.min) return false;
      if (filter.max != null && val > filter.max) return false;
    }
  }
  return true;
}

function updateParamFilterCount() {
  var count = countParamFilterMatches();
  var actions = document.querySelector('.param-filter-actions');
  if (actions) {
    var applyBtn = actions.querySelector('.param-filter-apply');
    if (applyBtn) applyBtn.textContent = 'Select ' + count + ' matching';
    var info = actions.querySelector('span');
    if (info) info.textContent = count + ' of ' + STRATEGIES.length + ' strategies match';
  }
}

function applyParamFilters() {
  selectedForCompare.clear();
  STRATEGIES.forEach(function(s, i) {
    if (strategyMatchesParamFilters(s)) selectedForCompare.add(i);
  });
  syncModalCount();
  syncMainTableCheckboxes();
  rebuildStrategyModal();
  updateCompareUI();
  switchModalTab('metrics');
}

function applyParamFiltersQuiet() {
  selectedForCompare.clear();
  STRATEGIES.forEach(function(s, i) {
    if (strategyMatchesParamFilters(s)) selectedForCompare.add(i);
  });
  syncModalCount();
  syncMainTableCheckboxes();
}

function resetParamFilters() {
  paramFilters = {};
  rebuildModalParams();
}

function openCompare() {
  if (selectedForCompare.size < 2) return;
  buildComparePage();
  showPage('compare');
}

function buildComparePage() {
  const indices = Array.from(selectedForCompare).sort((a,b) => a-b);

  // Key Metrics ranking table (overview style)
  buildCompareKeyMetrics(indices);

  // Parameters Comparison
  buildCompareParameters();

  // Trading Activity ranking table (overview style)
  buildCompareTradingActivityRanking(indices);

  // Return Scenarios
  buildCompareReturnScenarios(indices);

  // Monthly Returns (rows / heatmap / growth)
  buildCompareMonthlyReturns(indices);

  // Yearly returns
  const yrEl = document.getElementById('compare-yearly');
  if (yrEl) {
    let html = '<div class="chart-card">';
    html += '<div class="chart-title">Yearly Returns</div>';
    indices.forEach(i => {
      html += '<div style="margin-bottom:1.25rem"><div style="font-size:0.72rem;font-weight:500;color:var(--text-secondary);margin-bottom:0.5rem;display:flex;align-items:center;gap:0.3rem"><span class="sb-dot" style="background:'+STRATEGIES[i].color+'"></span>'+STRATEGIES[i].name+'</div><div class="chart-wrap chart-sm"><canvas id="c-compare-yearly-'+i+'"></canvas></div></div>';
    });
    html += '</div>';
    yrEl.innerHTML = html;
  }
}

function buildCompareKeyMetrics(indices) {
  var el = document.getElementById('compare-key-metrics');
  if (!el) return;
  if (indices.length < 2) { el.innerHTML = ''; return; }

  var bestVals = {};
  COMP_COLS.forEach(function(col) {
    var key = col[1], direction = col[3];
    var bestIdx = -1, bestVal = direction === 'min' ? Infinity : -Infinity;
    indices.forEach(function(i) {
      var m = getViewMetrics(i);
      var v = key === 'cagr' ? STRATEGIES[i].summary.cagr : m[key];
      if (v == null) return;
      if (direction === 'max' && v > bestVal) { bestVal = v; bestIdx = i; }
      if (direction === 'min' && Math.abs(v) < bestVal) { bestVal = Math.abs(v); bestIdx = i; }
    });
    if (bestIdx >= 0) bestVals[key] = bestIdx;
  });

  var html = '<div class="chart-card">';
  html += '<div class="chart-title">Key Metrics</div>';
  html += '<div class="table-wrap"><table class="comp-table"><thead><tr>';
  html += '<th class="sticky-col">Strategy</th>';
  COMP_COLS.forEach(function(col) { html += '<th>' + col[0] + '</th>'; });
  html += '</tr></thead><tbody>';

  indices.forEach(function(i) {
    var s = STRATEGIES[i];
    var m = getViewMetrics(i);
    var isChallenger = challengerIdx === i;
    html += '<tr class="comp-row' + (isChallenger ? ' challenger-row' : '') + '" onclick="showPage(\'strat-'+i+'\')">';
    html += '<td class="sticky-col"><span class="sb-dot" style="background:'+s.color+'"></span>'+s.name+'</td>';
    COMP_COLS.forEach(function(col) {
      var key = col[1], ftype = col[2];
      var v = key === 'cagr' ? s.summary.cagr : m[key];
      var isBest = bestVals[key] === i;
      var cls = isBest && indices.length > 1 ? ' class="best-cell"' : '';
      if (key === 'max_drawdown' && v != null) html += '<td'+cls+'>'+(Math.abs(v)*100).toFixed(1)+'%</td>';
      else html += '<td'+cls+'>' + fmtVal(v, ftype) + '</td>';
    });
    html += '</tr>';
  });

  html += '</tbody></table></div></div>';
  el.innerHTML = html;
  initCollapseButtons();
}

function buildCompareTradingActivityRanking(indices) {
  var el = document.getElementById('compare-trading-activity');
  if (!el) return;
  if (indices.length < 2) { el.innerHTML = ''; return; }

  var bestVals = {};
  TRADING_COLS.forEach(function(col) {
    var key = col[1], direction = col[3];
    var bestIdx = -1, bestVal = direction === 'min' ? Infinity : -Infinity;
    indices.forEach(function(i) {
      var m = getViewMetrics(i);
      var v = m[key];
      if (v == null) return;
      if (direction === 'max' && v > bestVal) { bestVal = v; bestIdx = i; }
      if (direction === 'min' && Math.abs(v) < bestVal) { bestVal = Math.abs(v); bestIdx = i; }
    });
    if (bestIdx >= 0) bestVals[key] = bestIdx;
  });

  var html = '<div class="chart-card">';
  html += '<div class="chart-title">Trading Activity Ranking</div>';
  html += '<div class="table-wrap"><table class="comp-table"><thead><tr>';
  html += '<th class="sticky-col">Strategy</th>';
  TRADING_COLS.forEach(function(col) { html += '<th>' + col[0] + '</th>'; });
  html += '</tr></thead><tbody>';

  indices.forEach(function(i) {
    var s = STRATEGIES[i];
    var m = getViewMetrics(i);
    var isChallenger = challengerIdx === i;
    html += '<tr class="comp-row' + (isChallenger ? ' challenger-row' : '') + '" onclick="showPage(\'strat-'+i+'\')">';
    html += '<td class="sticky-col"><span class="sb-dot" style="background:'+s.color+'"></span>'+s.name+'</td>';
    TRADING_COLS.forEach(function(col) {
      var key = col[1], ftype = col[2];
      var v = m[key];
      var isBest = bestVals[key] === i;
      var cls = isBest && indices.length > 1 ? ' class="best-cell"' : '';
      if (key === 'average_trade_duration' && v != null) html += '<td'+cls+'>'+v.toFixed(1)+'d</td>';
      else html += '<td'+cls+'>' + fmtVal(v, ftype) + '</td>';
    });
    html += '</tr>';
  });

  html += '</tbody></table></div></div>';
  el.innerHTML = html;
  initCollapseButtons();
}

function buildCompareReturnScenarios(indices) {
  var el = document.getElementById('compare-return-scenarios');
  if (!el) return;
  if (indices.length < 2) { el.innerHTML = ''; return; }

  var html = '<div class="chart-card">';
  html += '<div class="chart-title">Return Scenarios (Annual)</div>';
  html += '<div class="table-wrap"><table class="comp-table"><thead><tr>';
  html += '<th class="sticky-col">Strategy</th>';
  html += '<th>CAGR</th><th>Volatility</th>';
  html += '<th style="color:var(--green)">Good Year</th><th>Average Year</th>';
  html += '<th style="color:var(--amber)">Bad Year</th><th style="color:var(--red)">Very Bad Year (2\u03C3)</th>';
  html += '</tr></thead><tbody>';

  indices.forEach(function(i) {
    var s = STRATEGIES[i];
    var m = s.summary;
    var cagr = m.cagr;
    var vol = m.annual_volatility;
    var hasBoth = cagr != null && vol != null;
    var good = hasBoth ? (cagr + vol) * 100 : null;
    var avg = cagr != null ? cagr * 100 : null;
    var bad = hasBoth ? (cagr - vol) * 100 : null;
    var vbad = hasBoth ? (cagr - 2 * vol) * 100 : null;

    function fmtScenario(v) {
      if (v == null) return '\u2014';
      var color = v >= 0 ? 'var(--green)' : 'var(--red)';
      return '<span style="color:' + color + '">' + (v >= 0 ? '+' : '') + v.toFixed(1) + '%</span>';
    }

    var isChallenger = challengerIdx === i;
    html += '<tr class="comp-row' + (isChallenger ? ' challenger-row' : '') + '" onclick="showPage(\'strat-'+i+'\')">';
    html += '<td class="sticky-col"><span class="sb-dot" style="background:'+s.color+'"></span>'+s.name+'</td>';
    html += '<td>' + fmtVal(cagr, 'pct') + '</td>';
    html += '<td>' + fmtVal(vol, 'pct_abs') + '</td>';
    html += '<td>' + fmtScenario(good) + '</td>';
    html += '<td>' + fmtScenario(avg) + '</td>';
    html += '<td>' + fmtScenario(bad) + '</td>';
    html += '<td>' + fmtScenario(vbad) + '</td>';
    html += '</tr>';
  });

  html += '</tbody></table></div></div>';
  el.innerHTML = html;
  initCollapseButtons();
}

var compareMonthlyData = 'returns';   // 'returns' | 'growth'
var compareMonthlyDisplay = 'rows';   // 'rows' | 'heatmap'
var compareMonthlyYear = 'all';

function buildCompareMonthlyReturns(indices) {
  var el = document.getElementById('compare-return-distribution');
  if (!el) return;
  if (!indices) indices = Array.from(selectedForCompare).sort(function(a,b){return a-b;});
  if (indices.length < 2) { el.innerHTML = ''; return; }

  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  var allYears = new Set();
  var stratData = [];
  indices.forEach(function(i) {
    var rd = getViewRunData(i);
    var hm = (rd && rd.MONTHLY_HEATMAP) ? rd.MONTHLY_HEATMAP : {};
    Object.keys(hm).forEach(function(y) { allYears.add(y); });
    stratData.push({ idx: i, hm: hm });
  });
  var years = Array.from(allYears).sort();
  if (years.length === 0) { el.innerHTML = ''; return; }

  var filteredYears = compareMonthlyYear === 'all' ? years : years.filter(function(y){ return y === compareMonthlyYear; });
  var isGrowth = compareMonthlyData === 'growth';
  var isHeatmap = compareMonthlyDisplay === 'heatmap';

  var title = (isGrowth ? 'Cumulative Growth' : 'Monthly Returns') + (isHeatmap ? ' (Heatmap)' : '');

  var html = '<div class="chart-card">';
  html += '<div class="chart-title">';
  html += '<span>' + title + '</span>';
  html += '<span style="display:flex;gap:0.4rem;align-items:center">';

  // Year filter
  if (years.length > 1) {
    html += '<select class="view-select" id="compare-monthly-year" onchange="compareMonthlyYear=this.value;buildCompareMonthlyReturns()">';
    html += '<option value="all"' + (compareMonthlyYear === 'all' ? ' selected' : '') + '>All Years</option>';
    years.forEach(function(y) {
      html += '<option value="'+y+'"' + (compareMonthlyYear === y ? ' selected' : '') + '>'+y+'</option>';
    });
    html += '</select>';
  }

  // Data toggle
  [['returns','Returns'],['growth','Growth']].forEach(function(m) {
    var active = compareMonthlyData === m[0];
    html += '<button class="view-select" style="cursor:pointer;font-size:0.65rem;padding:2px 8px;'
      + (active ? 'background:var(--accent);color:#fff;border-color:var(--accent)' : '')
      + '" onclick="compareMonthlyData=\''+m[0]+'\';buildCompareMonthlyReturns()">'+m[1]+'</button>';
  });

  // Separator
  html += '<span style="color:var(--border);font-size:0.7rem">|</span>';

  // Display toggle
  [['rows','Rows'],['heatmap','Heatmap']].forEach(function(m) {
    var active = compareMonthlyDisplay === m[0];
    html += '<button class="view-select" style="cursor:pointer;font-size:0.65rem;padding:2px 8px;'
      + (active ? 'background:var(--accent);color:#fff;border-color:var(--accent)' : '')
      + '" onclick="compareMonthlyDisplay=\''+m[0]+'\';buildCompareMonthlyReturns()">'+m[1]+'</button>';
  });
  html += '</span></div>';

  // --- Helper: compute values per strategy per month ---
  // For growth mode, pre-compute cumulative values
  var cumValues = null;
  if (isGrowth) {
    cumValues = stratData.map(function() { return 100; });
    // Walk ALL years up to and including filtered years to get correct cumulative values
    // If year filter active, we still need to accumulate from start
    var allSorted = Array.from(allYears).sort();
    var startIdx = 0;
    if (compareMonthlyYear !== 'all') {
      // Accumulate all years before the filtered year
      for (var yi = 0; yi < allSorted.length; yi++) {
        if (allSorted[yi] === compareMonthlyYear) break;
        var preY = allSorted[yi];
        for (var pmi = 1; pmi <= 12; pmi++) {
          stratData.forEach(function(sd, si) {
            var v = (sd.hm[preY] && sd.hm[preY][String(pmi)] != null) ? sd.hm[preY][String(pmi)] : 0;
            cumValues[si] *= (1 + v / 100);
          });
        }
      }
    }
  }

  function fmtReturnCell(v, bgTint) {
    if (v == null) return '<td>\u2014</td>';
    var color = v >= 0 ? 'var(--green)' : 'var(--red)';
    var style = '';
    if (bgTint) {
      var intensity = Math.min(Math.abs(v) / 10, 1);
      var bg = v >= 0 ? 'rgba(34,197,94,' + (intensity * 0.2) + ')' : 'rgba(239,68,68,' + (intensity * 0.2) + ')';
      style = ' style="background:'+bg+'"';
    }
    return '<td'+style+'><span style="color:'+color+'">' + (v >= 0 ? '+' : '') + v.toFixed(1) + '%</span></td>';
  }

  function fmtGrowthCell(val, bgTint) {
    if (val == null) return '<td>\u2014</td>';
    var gain = val - 100;
    var color = gain >= 0 ? 'var(--green)' : 'var(--red)';
    var style = '';
    if (bgTint) {
      var intensity = Math.min(Math.abs(gain) / 50, 1);
      var bg = gain >= 0 ? 'rgba(34,197,94,' + (intensity * 0.15) + ')' : 'rgba(239,68,68,' + (intensity * 0.15) + ')';
      style = ' style="background:'+bg+'"';
    }
    return '<td'+style+'><span style="color:'+color+';font-weight:500">' + val.toFixed(1) + '</span> <span style="font-size:0.6rem;color:var(--text-secondary)">(' + (gain >= 0 ? '+' : '') + gain.toFixed(1) + '%)</span></td>';
  }

  if (!isHeatmap) {
    // === ROWS: strategies as columns, months as rows ===
    html += '<div class="table-wrap"><table class="comp-table" style="font-size:0.7rem"><thead><tr>';
    html += '<th class="sticky-col">Period</th>';
    indices.forEach(function(i) {
      html += '<th><span class="sb-dot" style="background:'+STRATEGIES[i].color+'"></span> '+STRATEGIES[i].name+'</th>';
    });
    html += '</tr></thead><tbody>';

    filteredYears.forEach(function(y) {
      // Year summary row
      html += '<tr style="background:var(--surface2);font-weight:600"><td class="sticky-col" style="background:var(--surface2)">' + y + (isGrowth ? ' End' : ' Total') + '</td>';
      if (isGrowth) {
        // Peek ahead: compute year-end cum values (clone current)
        var peekCum = cumValues.map(function(v){ return v; });
        for (var pmi2 = 1; pmi2 <= 12; pmi2++) {
          stratData.forEach(function(sd, si) {
            var v2 = (sd.hm[y] && sd.hm[y][String(pmi2)] != null) ? sd.hm[y][String(pmi2)] : 0;
            peekCum[si] *= (1 + v2 / 100);
          });
        }
        stratData.forEach(function(sd, si) {
          var val = peekCum[si];
          var gain = val - 100;
          var color = gain >= 0 ? 'var(--green)' : 'var(--red)';
          html += '<td style="font-weight:600"><span style="color:'+color+'">' + val.toFixed(1) + '</span></td>';
        });
      } else {
        stratData.forEach(function(sd) {
          var yearTotal = 0;
          var hm = sd.hm[y] || {};
          for (var mi = 1; mi <= 12; mi++) { yearTotal += hm[String(mi)] || 0; }
          var color = yearTotal >= 0 ? 'var(--green)' : 'var(--red)';
          html += '<td style="font-weight:600"><span style="color:'+color+'">' + (yearTotal >= 0 ? '+' : '') + yearTotal.toFixed(1) + '%</span></td>';
        });
      }
      html += '</tr>';

      // Monthly detail rows
      for (var mi = 1; mi <= 12; mi++) {
        var hasAny = false;
        stratData.forEach(function(sd) { if (sd.hm[y] && sd.hm[y][String(mi)] != null) hasAny = true; });
        if (!hasAny) { if (isGrowth) { /* no update needed */ } continue; }

        if (isGrowth) {
          stratData.forEach(function(sd, si) {
            var v = (sd.hm[y] && sd.hm[y][String(mi)] != null) ? sd.hm[y][String(mi)] : 0;
            cumValues[si] *= (1 + v / 100);
          });
        }

        html += '<tr><td class="sticky-col" style="padding-left:1.5rem;color:var(--text-secondary)">' + MONTHS[mi-1] + ' ' + y + '</td>';
        if (isGrowth) {
          stratData.forEach(function(sd, si) { html += fmtGrowthCell(cumValues[si], true); });
        } else {
          stratData.forEach(function(sd) {
            var v = (sd.hm[y] && sd.hm[y][String(mi)] != null) ? sd.hm[y][String(mi)] : null;
            html += fmtReturnCell(v, true);
          });
        }
        html += '</tr>';
      }
    });
    html += '</tbody></table></div>';

  } else {
    // === HEATMAP: per-strategy grid, months as columns, years as rows ===
    indices.forEach(function(i, si) {
      var sd = stratData[si];
      var strat = STRATEGIES[i];
      var hm = sd.hm;
      var yrs = filteredYears.filter(function(y){ return hm[y]; });
      if (yrs.length === 0) return;

      // For growth heatmap, compute cumulative per strategy independently
      var stratCum = 100;
      if (isGrowth) {
        // Accumulate prior years
        var allSorted2 = Array.from(allYears).sort();
        if (compareMonthlyYear !== 'all') {
          for (var yi2 = 0; yi2 < allSorted2.length; yi2++) {
            if (allSorted2[yi2] === compareMonthlyYear) break;
            var preY2 = allSorted2[yi2];
            for (var pmi3 = 1; pmi3 <= 12; pmi3++) {
              var pv = (hm[preY2] && hm[preY2][pmi3] != null) ? hm[preY2][pmi3] : 0;
              stratCum *= (1 + pv / 100);
            }
          }
        }
      }

      html += '<div style="margin-bottom:1rem"><div style="font-size:0.72rem;font-weight:500;color:var(--text-secondary);margin-bottom:0.4rem;display:flex;align-items:center;gap:0.3rem">';
      html += '<span class="sb-dot" style="background:'+strat.color+'"></span>'+strat.name+'</div>';
      html += '<table class="heatmap-table"><thead><tr><th></th>';
      MONTHS.forEach(function(m){ html += '<th>'+m+'</th>'; });
      html += '<th>Year</th></tr></thead><tbody>';

      yrs.forEach(function(y) {
        html += '<tr><th>'+y+'</th>';

        if (isGrowth) {
          var yearStartCum = stratCum;
          for (var mi = 1; mi <= 12; mi++) {
            var v = (hm[y] && hm[y][mi] != null) ? hm[y][mi] : undefined;
            if (v !== undefined) {
              stratCum *= (1 + v / 100);
              var gain = stratCum - 100;
              var cls = gain > 20 ? 'hm-strong-pos' : gain > 0 ? 'hm-pos' : gain < -10 ? 'hm-strong-neg' : gain < 0 ? 'hm-neg' : 'hm-zero';
              html += '<td class="'+cls+'">'+stratCum.toFixed(0)+'</td>';
            } else {
              html += '<td class="hm-zero">&mdash;</td>';
            }
          }
          var yearGain = stratCum - 100;
          var ycls = yearGain > 0 ? 'hm-pos' : yearGain < 0 ? 'hm-neg' : 'hm-zero';
          html += '<td class="'+ycls+'" style="font-weight:600">' + stratCum.toFixed(0) + '</td></tr>';
        } else {
          var yTotal = 0;
          for (var mi = 1; mi <= 12; mi++) {
            var v = (hm[y] && hm[y][mi] != null) ? hm[y][mi] : undefined;
            if (v !== undefined) {
              yTotal += v;
              var cls = 'hm-zero';
              if (v > 10) cls = 'hm-strong-pos';
              else if (v > 0) cls = 'hm-pos';
              else if (v < -3) cls = 'hm-strong-neg';
              else if (v < 0) cls = 'hm-neg';
              html += '<td class="'+cls+'">'+(v>0?'+':'')+v.toFixed(1)+'%</td>';
            } else {
              html += '<td class="hm-zero">&mdash;</td>';
            }
          }
          var ycls = yTotal > 0 ? 'hm-pos' : yTotal < 0 ? 'hm-neg' : 'hm-zero';
          html += '<td class="'+ycls+'" style="font-weight:600">'+(yTotal>0?'+':'')+yTotal.toFixed(1)+'%</td></tr>';
        }
      });
      html += '</tbody></table></div>';
    });
  }

  html += '</div>';
  el.innerHTML = html;
  initCollapseButtons();
}

function drawCompareExtras() {
  const indices = Array.from(selectedForCompare).sort((a,b) => a-b);

  // Equity legend (hide when summary — no curve to label)
  const legEl = document.getElementById('compare-eq-legend');
  if (legEl) {
    if (selectedRunView === 'summary') {
      legEl.innerHTML = '';
    } else {
      let html = '';
      indices.forEach(i => {
        html += '<span class="eq-legend-item"><span class="eq-legend-swatch" style="background:'+STRATEGIES[i].color+'"></span>'+STRATEGIES[i].name+'</span>';
      });
      legEl.innerHTML = html;
    }
  }

  // Drawdown overlay
  drawCompareDrawdown(indices);

  // Return distribution
  drawCompareReturnDist(indices);

  // Correlation matrix
  buildCompareCorrelation(indices);

  // Rolling Sharpe
  drawCompareRollingSharpe(indices);

  // Risk-Return Scatter
  drawRiskReturnScatter('c-compare-scatter');

  // Rolling Returns
  drawRollingReturns('compare');

  // Relative Performance
  drawRelativePerformance();

  // Draw yearly bar charts
  indices.forEach(i => {
    const rd = getViewRunData(i);
    if (rd && rd.YR) drawBarChart('c-compare-yearly-'+i, rd.YR);
  });
}

function drawCompareDrawdown(indices) {
  const canvas = document.getElementById('c-compare-dd-time');
  if (!canvas) return;
  const wrap = canvas.parentElement;

  let placeholder = wrap.querySelector('.eq-placeholder');
  if (selectedRunView === 'summary') {
    const r2 = resizeCanvas('c-compare-dd-time');
    if (r2) { r2.ctx.clearRect(0, 0, r2.w, r2.h); }
    if (!placeholder) {
      placeholder = document.createElement('div');
      placeholder.className = 'eq-placeholder';
      placeholder.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:13px;pointer-events:none;';
      wrap.style.position = 'relative';
      wrap.appendChild(placeholder);
    }
    placeholder.textContent = 'Select a backtest window to see drawdown curves';
    placeholder.style.display = 'flex';
    wrap.style.height = '80px';
    return;
  }
  if (placeholder) placeholder.style.display = 'none';
  wrap.style.height = '';

  const ddSeries = [];
  indices.forEach(si => {
    const s = STRATEGIES[si];
    const rd = getViewRunData(si);
    if (rd && rd.DD && rd.DD.length > 1) {
      ddSeries.push({ dd: rd.DD, color: s.color, name: s.name });
    }
  });

  if (ddSeries.length === 0) return;

  const r = resizeCanvas('c-compare-dd-time');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;

  let gMin = 0;
  ddSeries.forEach(item => { item.dd.forEach(d => { if (d[0] < gMin) gMin = d[0]; }); });
  if (gMin >= 0) gMin = -1;
  const range = 0 - gMin;

  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + (i/4)*ch;
    const val = 0 - (i/4)*range;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
    ctx.fillText(val.toFixed(1)+'%', w-pad.r+50, y+3.5);
  }

  let longestDD = ddSeries[0].dd;
  ddSeries.forEach(item => { if (item.dd.length > longestDD.length) longestDD = item.dd; });
  ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
  const li = Math.max(1, Math.floor(longestDD.length/6));
  for (let i = 0; i < longestDD.length; i += li) {
    const x = pad.l + (i/(longestDD.length-1))*cw;
    ctx.fillText(longestDD[i][1], x, h-5);
  }

  ddSeries.forEach(item => {
    const dd = item.dd;
    ctx.beginPath();
    for (let i = 0; i < dd.length; i++) {
      const x = pad.l + (i/(dd.length-1))*cw;
      const y = pad.t + ((0 - dd[i][0])/range)*ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.lineTo(pad.l+cw, pad.t); ctx.lineTo(pad.l, pad.t); ctx.closePath();
    ctx.fillStyle = item.color + '15'; ctx.fill();
    ctx.beginPath(); ctx.strokeStyle = item.color; ctx.lineWidth = 1.5; ctx.lineJoin = 'round';
    for (let i = 0; i < dd.length; i++) {
      const x = pad.l + (i/(dd.length-1))*cw;
      const y = pad.t + ((0 - dd[i][0])/range)*ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
  });

  canvas._chartData = { data: longestDD, pad, cw, ch, mn: gMin, range, mx: 0, color: COL.red, type: 'area' };
}

function drawCompareReturnDist(indices) {
  const canvas = document.getElementById('c-compare-dist');
  if (!canvas) return;
  const r = resizeCanvas('c-compare-dist');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:15, b:35, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;

  const stratReturns = [];
  indices.forEach(si => {
    const s = STRATEGIES[si];
    const returns = [];
    for (const [wname] of RUN_LABELS) {
      const rid = s.runNameMap[wname];
      if (rid && RUN_DATA[rid] && RUN_DATA[rid].EQ && RUN_DATA[rid].EQ.length >= 2) {
        const eq = RUN_DATA[rid].EQ;
        returns.push(eq[eq.length-1][0]);
      }
    }
    if (returns.length > 0) {
      returns.sort((a,b) => a-b);
      stratReturns.push({ name: s.name, color: s.color, returns });
    }
  });

  if (stratReturns.length === 0) return;

  let gMin = Infinity, gMax = -Infinity;
  stratReturns.forEach(sr => { sr.returns.forEach(v => { if (v < gMin) gMin = v; if (v > gMax) gMax = v; }); });
  const margin = (gMax - gMin) * 0.15 || 5;
  gMin -= margin; gMax += margin;
  const range = gMax - gMin;

  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + ch - (i/4)*ch;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
  }
  if (gMin < 0 && gMax > 0) {
    const zeroY = pad.t + ch - ((0-gMin)/range)*ch;
    ctx.strokeStyle = COL.dim; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l,zeroY); ctx.lineTo(w-pad.r,zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }

  const gap = cw / stratReturns.length;
  const boxW = Math.min(40, gap * 0.6);

  stratReturns.forEach((sr, idx) => {
    const cx2 = pad.l + gap * idx + gap/2;
    const rets = sr.returns;
    const n = rets.length;
    const q1 = rets[Math.floor(n * 0.25)];
    const median = rets[Math.floor(n * 0.5)];
    const q3 = rets[Math.floor(n * 0.75)];
    const min = rets[0], max = rets[n-1];
    const toY = v => pad.t + ch - ((v - gMin)/range)*ch;

    ctx.strokeStyle = sr.color; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(cx2, toY(min)); ctx.lineTo(cx2, toY(q1)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx2, toY(q3)); ctx.lineTo(cx2, toY(max)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx2-boxW*0.3, toY(min)); ctx.lineTo(cx2+boxW*0.3, toY(min)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx2-boxW*0.3, toY(max)); ctx.lineTo(cx2+boxW*0.3, toY(max)); ctx.stroke();

    const boxTop = toY(q3), boxBot = toY(q1);
    ctx.fillStyle = sr.color + '30'; ctx.strokeStyle = sr.color; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.rect(cx2-boxW/2, boxTop, boxW, boxBot-boxTop); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = sr.color; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.moveTo(cx2-boxW/2, toY(median)); ctx.lineTo(cx2+boxW/2, toY(median)); ctx.stroke();

    rets.forEach(v => {
      const y = toY(v);
      const jx = cx2 + (Math.random()-0.5)*boxW*0.4;
      ctx.beginPath(); ctx.arc(jx, y, 2.5, 0, Math.PI*2);
      ctx.fillStyle = sr.color + '60'; ctx.fill();
    });

    ctx.fillStyle = COL.dim; ctx.font = '10px Inter, sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(sr.name.slice(0,8), cx2, h-8);
  });
}

function buildCompareCorrelation(indices) {
  const container = document.getElementById('compare-corr-matrix');
  if (!container) return;

  if (selectedRunView === 'summary') {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:180px;color:var(--dim);font-size:13px;">Select a backtest window to see correlations</div>';
    return;
  }

  const equities = [];
  indices.forEach(si => {
    const s = STRATEGIES[si];
    const rd = getViewRunData(si);
    if (rd && rd.EQ && rd.EQ.length > 1) {
      equities.push({ name: s.name, color: s.color, eq: rd.EQ.map(d => d[0]) });
    }
  });

  if (equities.length < 2) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:180px;color:var(--dim);font-size:13px;">Need at least 2 strategies</div>';
    return;
  }

  function correlation(a, b) {
    const n = Math.min(a.length, b.length);
    if (n < 3) return 0;
    let sumA = 0, sumB = 0, sumAB = 0, sumA2 = 0, sumB2 = 0;
    for (let i = 0; i < n; i++) {
      sumA += a[i]; sumB += b[i]; sumAB += a[i]*b[i];
      sumA2 += a[i]*a[i]; sumB2 += b[i]*b[i];
    }
    const denom = Math.sqrt((n*sumA2-sumA*sumA)*(n*sumB2-sumB*sumB));
    if (denom === 0) return 0;
    return (n*sumAB - sumA*sumB) / denom;
  }

  function corrColor(v) {
    if (v > 0.8) return 'color:var(--green);background:#10b98125';
    if (v > 0.5) return 'color:var(--green);background:#10b98115';
    if (v > 0.2) return 'color:var(--text)';
    if (v > -0.2) return 'color:var(--amber)';
    if (v > -0.5) return 'color:var(--red);background:#ef444415';
    return 'color:var(--red);background:#ef444425';
  }

  let html = '<table class="corr-table"><thead><tr><th></th>';
  equities.forEach(e => { html += '<th title="'+e.name+'">'+e.name.slice(0,8)+'</th>'; });
  html += '</tr></thead><tbody>';
  equities.forEach((ei, i) => {
    html += '<tr><th style="text-align:right">'+ei.name.slice(0,8)+'</th>';
    equities.forEach((ej, j) => {
      if (i === j) html += '<td class="corr-self">1.00</td>';
      else { const corr = correlation(ei.eq, ej.eq); html += '<td style="'+corrColor(corr)+'">'+corr.toFixed(2)+'</td>'; }
    });
    html += '</tr>';
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

function drawCompareRollingSharpe(indices) {
  const canvas = document.getElementById('c-compare-rsharpe');
  if (!canvas) return;
  const wrap = canvas.parentElement;

  let placeholder = wrap.querySelector('.eq-placeholder');
  if (selectedRunView === 'summary') {
    const r2 = resizeCanvas('c-compare-rsharpe');
    if (r2) { r2.ctx.clearRect(0, 0, r2.w, r2.h); }
    if (!placeholder) {
      placeholder = document.createElement('div');
      placeholder.className = 'eq-placeholder';
      placeholder.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:13px;pointer-events:none;';
      wrap.style.position = 'relative';
      wrap.appendChild(placeholder);
    }
    placeholder.textContent = 'Select a backtest window to see rolling Sharpe';
    placeholder.style.display = 'flex';
    wrap.style.height = '80px';
    return;
  }
  if (placeholder) placeholder.style.display = 'none';
  wrap.style.height = '';

  const rsSeries = [];
  indices.forEach(si => {
    const s = STRATEGIES[si];
    const rd = getViewRunData(si);
    if (rd && rd.RS && rd.RS.length > 1) {
      rsSeries.push({ rs: rd.RS, color: s.color, name: s.name });
    }
  });

  if (rsSeries.length === 0) {
    const r = resizeCanvas('c-compare-rsharpe');
    if (r) r.ctx.clearRect(0, 0, r.w, r.h);
    return;
  }

  const r = resizeCanvas('c-compare-rsharpe');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;

  let gMin = Infinity, gMax = -Infinity;
  rsSeries.forEach(item => {
    item.rs.forEach(d => {
      if (d[0] != null && !isNaN(d[0])) {
        if (d[0] < gMin) gMin = d[0]; if (d[0] > gMax) gMax = d[0];
      }
    });
  });
  if (!isFinite(gMin)) return;
  if (gMin === gMax) { gMin -= 1; gMax += 1; }
  const range = gMax - gMin;

  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i = 0; i <= 5; i++) {
    const y = pad.t + ch - (i/5)*ch;
    const val = gMin + (i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
    ctx.fillText(val.toFixed(2), w-pad.r+50, y+3.5);
  }
  if (gMin < 0 && gMax > 0) {
    const zeroY = pad.t + ch - ((0-gMin)/range)*ch;
    ctx.strokeStyle = COL.dim; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l, zeroY); ctx.lineTo(w-pad.r, zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }

  let longestRS = rsSeries[0].rs;
  rsSeries.forEach(item => { if (item.rs.length > longestRS.length) longestRS = item.rs; });
  ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
  const li = Math.max(1, Math.floor(longestRS.length/6));
  for (let i = 0; i < longestRS.length; i += li) {
    const x = pad.l + (i/(longestRS.length-1))*cw;
    ctx.fillText(longestRS[i][1], x, h-5);
  }

  rsSeries.forEach(item => {
    const rs = item.rs;
    ctx.beginPath(); ctx.strokeStyle = item.color; ctx.lineWidth = 1.5; ctx.lineJoin = 'round';
    let started = false;
    for (let i = 0; i < rs.length; i++) {
      if (rs[i][0] == null || isNaN(rs[i][0])) continue;
      const x = pad.l + (i/(rs.length-1))*cw;
      const y = pad.t + ch - ((rs[i][0]-gMin)/range)*ch;
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
  });

  canvas._chartData = { data: longestRS, pad, cw, ch, mn: gMin, range, color: COL.amber, opts: { decimals: 2 }, type: 'line' };
}

// ===== EQUITY LEGEND =====
function buildEquityLegend() {
  const container = document.getElementById('equity-legend');
  if (!container) return;
  let html = '';

  const vis = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);

  vis.forEach(i => {
    const s = STRATEGIES[i];
    const isChal = challengerIdx === i;
    html += '<span class="eq-legend-item">' +
      '<span class="eq-legend-swatch" style="background:'+s.color+(isChal?';height:4px':'')+'"></span>' +
      (isChal ? '\u2691 ' : '') + s.name + '</span>';
  });

  if (typeof BENCHMARKS !== 'undefined') {
    BENCHMARKS.forEach((b, bi) => {
      if (!benchmarkVisible.has(bi)) return;
      const cls = b.lineStyle === 'dotted' ? 'dotted' : 'dashed';
      html += '<span class="eq-legend-item">' +
        '<span class="eq-legend-swatch '+cls+'" style="--swatch-color:'+b.color+'"></span>' +
        b.name + '</span>';
    });
  }

  container.innerHTML = html;
}

// ===== OVERVIEW: MULTI DRAWDOWN OVERLAY =====
function drawMultiOverviewDrawdown() {
  const canvas = document.getElementById('c-overview-dd');
  if (!canvas) return;
  const wrap = canvas.parentElement;

  let placeholder = wrap.querySelector('.eq-placeholder');
  if (selectedRunView === 'summary') {
    const r = resizeCanvas('c-overview-dd');
    if (r) { r.ctx.clearRect(0, 0, r.w, r.h); }
    if (!placeholder) {
      placeholder = document.createElement('div');
      placeholder.className = 'eq-placeholder';
      placeholder.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:13px;pointer-events:none;';
      wrap.style.position = 'relative';
      wrap.appendChild(placeholder);
    }
    placeholder.textContent = 'Select a backtest window to see drawdown curves';
    placeholder.style.display = 'flex';
    wrap.style.height = '80px';
    return;
  }
  if (placeholder) placeholder.style.display = 'none';
  wrap.style.height = '';

  const r = resizeCanvas('c-overview-dd');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;

  const visibleIndices = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);

  // Gather DD series for each strategy
  const ddSeries = [];
  visibleIndices.forEach(si => {
    const s = STRATEGIES[si];
    const rid = s.runNameMap[selectedRunView];
    if (rid && RUN_DATA[rid] && RUN_DATA[rid].DD && RUN_DATA[rid].DD.length > 1) {
      ddSeries.push({ dd: RUN_DATA[rid].DD, color: s.color, name: s.name, isChal: challengerIdx === si });
    }
  });

  if (ddSeries.length === 0) {
    const r2 = resizeCanvas('c-overview-dd');
    if (r2) r2.ctx.clearRect(0, 0, r2.w, r2.h);
    return;
  }

  let gMin = 0;
  ddSeries.forEach(item => {
    item.dd.forEach(d => { if (d[0] < gMin) gMin = d[0]; });
  });
  if (gMin >= 0) gMin = -1;
  const range = 0 - gMin;

  // Grid lines (0% at top, worst at bottom)
  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + (i/4)*ch;
    const val = 0 - (i/4)*range;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
    ctx.fillText(val.toFixed(1)+'%', w-pad.r+50, y+3.5);
  }

  // X-axis dates from longest series
  let longestDD = ddSeries[0].dd;
  ddSeries.forEach(item => { if (item.dd.length > longestDD.length) longestDD = item.dd; });
  ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
  const li = Math.max(1, Math.floor(longestDD.length/6));
  for (let i = 0; i < longestDD.length; i += li) {
    const x = pad.l + (i/(longestDD.length-1))*cw;
    ctx.fillText(longestDD[i][1], x, h-5);
  }

  // Draw each strategy's drawdown with area fill
  ddSeries.forEach(item => {
    const dd = item.dd;
    // Area fill
    ctx.beginPath();
    for (let i = 0; i < dd.length; i++) {
      const x = pad.l + (i/(dd.length-1))*cw;
      const y = pad.t + ((0 - dd[i][0])/range)*ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.lineTo(pad.l+cw, pad.t);
    ctx.lineTo(pad.l, pad.t);
    ctx.closePath();
    ctx.fillStyle = item.color + '15';
    ctx.fill();

    // Stroke line
    ctx.beginPath();
    ctx.strokeStyle = item.color;
    ctx.lineWidth = item.isChal ? 3 : 1.5;
    ctx.lineJoin = 'round';
    for (let i = 0; i < dd.length; i++) {
      const x = pad.l + (i/(dd.length-1))*cw;
      const y = pad.t + ((0 - dd[i][0])/range)*ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
  });

  canvas._chartData = { data: longestDD, pad, cw, ch, mn: gMin, range, mx: 0, color: COL.red, type: 'area' };
}

// ===== RETURN DISTRIBUTION (box-plot style) =====
function drawReturnDistribution() {
  const canvas = document.getElementById('c-return-dist');
  if (!canvas) return;
  const r = resizeCanvas('c-return-dist');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:15, b:35, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;

  const vis = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);

  // Gather per-window returns for each strategy
  const stratReturns = [];
  vis.forEach(si => {
    const s = STRATEGIES[si];
    const returns = [];
    for (const [wname] of RUN_LABELS) {
      const rid = s.runNameMap[wname];
      if (rid && RUN_DATA[rid] && RUN_DATA[rid].EQ && RUN_DATA[rid].EQ.length >= 2) {
        const eq = RUN_DATA[rid].EQ;
        returns.push(eq[eq.length-1][0]);
      }
    }
    if (returns.length > 0) {
      returns.sort((a,b) => a-b);
      stratReturns.push({ name: s.name, color: s.color, returns, isChal: challengerIdx === si });
    }
  });

  if (stratReturns.length === 0) return;

  // Global y-range
  let gMin = Infinity, gMax = -Infinity;
  stratReturns.forEach(sr => {
    sr.returns.forEach(v => { if (v < gMin) gMin = v; if (v > gMax) gMax = v; });
  });
  const margin = (gMax - gMin) * 0.15 || 5;
  gMin -= margin; gMax += margin;
  const range = gMax - gMin;

  // Grid
  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim;
  ctx.textAlign = 'left';
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + ch - (i/4)*ch;
    const val = gMin + (i/4)*range;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
  }
  // Zero line
  if (gMin < 0 && gMax > 0) {
    const zeroY = pad.t + ch - ((0-gMin)/range)*ch;
    ctx.strokeStyle = COL.dim; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l,zeroY); ctx.lineTo(w-pad.r,zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }

  const gap = cw / stratReturns.length;
  const boxW = Math.min(40, gap * 0.6);

  stratReturns.forEach((sr, idx) => {
    const cx = pad.l + gap * idx + gap/2;
    const rets = sr.returns;
    const n = rets.length;

    // Quartiles
    const q1 = rets[Math.floor(n * 0.25)];
    const median = rets[Math.floor(n * 0.5)];
    const q3 = rets[Math.floor(n * 0.75)];
    const min = rets[0];
    const max = rets[n-1];

    const toY = v => pad.t + ch - ((v - gMin)/range)*ch;

    // Whiskers
    ctx.strokeStyle = sr.color; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(cx, toY(min)); ctx.lineTo(cx, toY(q1)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx, toY(q3)); ctx.lineTo(cx, toY(max)); ctx.stroke();
    // Whisker caps
    ctx.beginPath(); ctx.moveTo(cx-boxW*0.3, toY(min)); ctx.lineTo(cx+boxW*0.3, toY(min)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx-boxW*0.3, toY(max)); ctx.lineTo(cx+boxW*0.3, toY(max)); ctx.stroke();

    // Box (Q1 to Q3)
    const boxTop = toY(q3);
    const boxBot = toY(q1);
    ctx.fillStyle = sr.color + '30';
    ctx.strokeStyle = sr.color;
    ctx.lineWidth = sr.isChal ? 2.5 : 1.5;
    ctx.beginPath(); ctx.rect(cx-boxW/2, boxTop, boxW, boxBot-boxTop); ctx.fill(); ctx.stroke();

    // Median line
    ctx.strokeStyle = sr.color; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.moveTo(cx-boxW/2, toY(median)); ctx.lineTo(cx+boxW/2, toY(median)); ctx.stroke();

    // Individual data points (jitter)
    rets.forEach(v => {
      const y = toY(v);
      const jx = cx + (Math.random()-0.5)*boxW*0.4;
      ctx.beginPath(); ctx.arc(jx, y, 2.5, 0, Math.PI*2);
      ctx.fillStyle = sr.color + '60'; ctx.fill();
    });

    // Label
    ctx.fillStyle = COL.dim; ctx.font = '10px Inter, sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(sr.name.slice(0,8), cx, h-8);
  });
}

// ===== CORRELATION MATRIX =====
function buildCorrelationMatrix() {
  const container = document.getElementById('corr-matrix');
  if (!container) return;

  if (selectedRunView === 'summary') {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:180px;color:var(--dim);font-size:13px;">Select a backtest window to see correlations</div>';
    return;
  }

  const vis = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);

  // Collect equity arrays (same window)
  const equities = [];
  vis.forEach(si => {
    const eq = getViewEquity(si);
    equities.push({ name: STRATEGIES[si].name, color: STRATEGIES[si].color, eq: eq.map(d => d[0]) });
  });

  if (equities.length < 2) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:180px;color:var(--dim);font-size:13px;">Need at least 2 strategies</div>';
    return;
  }

  // Pearson correlation
  function correlation(a, b) {
    const n = Math.min(a.length, b.length);
    if (n < 3) return 0;
    let sumA = 0, sumB = 0, sumAB = 0, sumA2 = 0, sumB2 = 0;
    for (let i = 0; i < n; i++) {
      sumA += a[i]; sumB += b[i]; sumAB += a[i]*b[i];
      sumA2 += a[i]*a[i]; sumB2 += b[i]*b[i];
    }
    const denom = Math.sqrt((n*sumA2-sumA*sumA)*(n*sumB2-sumB*sumB));
    if (denom === 0) return 0;
    return (n*sumAB - sumA*sumB) / denom;
  }

  function corrColor(v) {
    if (v > 0.8) return 'color:var(--green);background:#10b98125';
    if (v > 0.5) return 'color:var(--green);background:#10b98115';
    if (v > 0.2) return 'color:var(--text)';
    if (v > -0.2) return 'color:var(--amber)';
    if (v > -0.5) return 'color:var(--red);background:#ef444415';
    return 'color:var(--red);background:#ef444425';
  }

  let html = '<table class="corr-table"><thead><tr><th></th>';
  equities.forEach(e => { html += '<th title="'+e.name+'">'+e.name.slice(0,8)+'</th>'; });
  html += '</tr></thead><tbody>';

  equities.forEach((ei, i) => {
    html += '<tr><th style="text-align:right">'+ei.name.slice(0,8)+'</th>';
    equities.forEach((ej, j) => {
      if (i === j) {
        html += '<td class="corr-self">1.00</td>';
      } else {
        const corr = correlation(ei.eq, ej.eq);
        html += '<td style="'+corrColor(corr)+'">'+corr.toFixed(2)+'</td>';
      }
    });
    html += '</tr>';
  });
  html += '</tbody></table>';
  container.innerHTML = html;
}

// ===== ROLLING SHARPE OVERLAY =====
function drawMultiRollingSharpe() {
  const canvas = document.getElementById('c-overview-rsharpe');
  if (!canvas) return;
  const wrap = canvas.parentElement;

  let placeholder = wrap.querySelector('.eq-placeholder');
  if (selectedRunView === 'summary') {
    const r = resizeCanvas('c-overview-rsharpe');
    if (r) { r.ctx.clearRect(0, 0, r.w, r.h); }
    if (!placeholder) {
      placeholder = document.createElement('div');
      placeholder.className = 'eq-placeholder';
      placeholder.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:13px;pointer-events:none;';
      wrap.style.position = 'relative';
      wrap.appendChild(placeholder);
    }
    placeholder.textContent = 'Select a backtest window to see rolling Sharpe';
    placeholder.style.display = 'flex';
    wrap.style.height = '80px';
    return;
  }
  if (placeholder) placeholder.style.display = 'none';
  wrap.style.height = '';

  const r = resizeCanvas('c-overview-rsharpe');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;

  const visibleIndices = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);

  // Gather RS for each strategy
  const rsSeries = [];
  visibleIndices.forEach(si => {
    const s = STRATEGIES[si];
    const rid = s.runNameMap[selectedRunView];
    if (rid && RUN_DATA[rid] && RUN_DATA[rid].RS && RUN_DATA[rid].RS.length > 1) {
      rsSeries.push({ rs: RUN_DATA[rid].RS, color: s.color, name: s.name, isChal: challengerIdx === si });
    }
  });

  if (rsSeries.length === 0) {
    const r2 = resizeCanvas('c-overview-rsharpe');
    if (r2) r2.ctx.clearRect(0, 0, r2.w, r2.h);
    return;
  }

  let gMin = Infinity, gMax = -Infinity;
  rsSeries.forEach(item => {
    item.rs.forEach(d => {
      if (d[0] != null && !isNaN(d[0])) {
        if (d[0] < gMin) gMin = d[0];
        if (d[0] > gMax) gMax = d[0];
      }
    });
  });
  if (!isFinite(gMin)) return;
  if (gMin === gMax) { gMin -= 1; gMax += 1; }
  const range = gMax - gMin;

  // Grid
  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i = 0; i <= 5; i++) {
    const y = pad.t + ch - (i/5)*ch;
    const val = gMin + (i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
    ctx.fillText(val.toFixed(2), w-pad.r+50, y+3.5);
  }

  // Zero line
  if (gMin < 0 && gMax > 0) {
    const zeroY = pad.t + ch - ((0-gMin)/range)*ch;
    ctx.strokeStyle = COL.dim; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l, zeroY); ctx.lineTo(w-pad.r, zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }

  // X-axis from longest series
  let longestRS = rsSeries[0].rs;
  rsSeries.forEach(item => { if (item.rs.length > longestRS.length) longestRS = item.rs; });
  ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
  const li = Math.max(1, Math.floor(longestRS.length/6));
  for (let i = 0; i < longestRS.length; i += li) {
    const x = pad.l + (i/(longestRS.length-1))*cw;
    ctx.fillText(longestRS[i][1], x, h-5);
  }

  // Draw lines
  rsSeries.forEach(item => {
    const rs = item.rs;
    ctx.beginPath();
    ctx.strokeStyle = item.color;
    ctx.lineWidth = item.isChal ? 3 : 1.5;
    ctx.lineJoin = 'round';
    let started = false;
    for (let i = 0; i < rs.length; i++) {
      if (rs[i][0] == null || isNaN(rs[i][0])) continue;
      const x = pad.l + (i/(rs.length-1))*cw;
      const y = pad.t + ch - ((rs[i][0]-gMin)/range)*ch;
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
  });

  canvas._chartData = { data: longestRS, pad, cw, ch, mn: gMin, range, color: COL.amber, opts: { decimals: 2 }, type: 'line' };
}

function drawCompareEquity() {
  const indices = Array.from(selectedForCompare).sort((a,b) => a-b);
  if (indices.length < 2) return;
  const canvas = document.getElementById('c-compare-eq');
  if (!canvas) return;
  const wrap = canvas.parentElement;
  let placeholder = wrap.querySelector('.eq-placeholder');
  if (selectedRunView === 'summary') {
    const r2 = resizeCanvas('c-compare-eq');
    if (r2) { r2.ctx.clearRect(0, 0, r2.w, r2.h); }
    if (!placeholder) {
      placeholder = document.createElement('div');
      placeholder.className = 'eq-placeholder';
      placeholder.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:13px;pointer-events:none;';
      wrap.style.position = 'relative';
      wrap.appendChild(placeholder);
    }
    placeholder.textContent = 'Select a backtest window to see equity curves';
    placeholder.style.display = 'flex';
    wrap.style.height = '80px';
    return;
  }
  if (placeholder) placeholder.style.display = 'none';
  wrap.style.height = '';
  const r = resizeCanvas('c-compare-eq');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  let gMin=0, gMax=0;
  indices.forEach(i => {
    const eq = getViewEquity(i);
    eq.forEach(d => { if(d[0]<gMin) gMin=d[0]; if(d[0]>gMax) gMax=d[0]; });
  });
  if (gMin===gMax) { gMin-=1; gMax+=1; }
  const range = gMax-gMin;
  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i=0;i<=5;i++) {
    const y = pad.t+ch-(i/5)*ch;
    const val = gMin+(i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    ctx.fillText(val.toFixed(0)+'%', w-pad.r+50, y+3.5);
  }
  if (gMin<0 && gMax>0) {
    const zeroY = pad.t+ch-((0-gMin)/range)*ch;
    ctx.strokeStyle = COL.dim; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l,zeroY); ctx.lineTo(w-pad.r,zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }
  indices.forEach((si, ci) => {
    const eq = getViewEquity(si); if (!eq || eq.length<2) return;
    if (ci===0) {
      ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
      const li = Math.max(1,Math.floor(eq.length/6));
      for (let i=0;i<eq.length;i+=li) { const x=pad.l+(i/(eq.length-1))*cw; ctx.fillText(eq[i][1], x, h-5); }
    }
    ctx.beginPath(); ctx.strokeStyle = STRATEGIES[si].color; ctx.lineWidth = 2; ctx.lineJoin = 'round';
    for (let i=0;i<eq.length;i++) {
      const x=pad.l+(i/(eq.length-1))*cw;
      const y=pad.t+ch-((eq[i][0]-gMin)/range)*ch;
      i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
    }
    ctx.stroke();
  });
}

function drawCompareMetricBars() {
  const indices = Array.from(selectedForCompare).sort((a,b) => a-b);
  drawHorizontalBars('c-compare-cagr', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:(m.cagr||0)*100, color:STRATEGIES[i].color, formatted:((m.cagr||0)*100).toFixed(1)+'%' }; }), METRIC_ZONES.cagr);
  drawHorizontalBars('c-compare-sharpe', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:m.sharpe_ratio||0, color:STRATEGIES[i].color, formatted:(m.sharpe_ratio||0).toFixed(2) }; }), METRIC_ZONES.sharpe);
  drawHorizontalBars('c-compare-sortino', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:m.sortino_ratio||0, color:STRATEGIES[i].color, formatted:(m.sortino_ratio||0).toFixed(2) }; }), METRIC_ZONES.sortino);
  drawHorizontalBars('c-compare-calmar', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:m.calmar_ratio||0, color:STRATEGIES[i].color, formatted:(m.calmar_ratio||0).toFixed(2) }; }), METRIC_ZONES.calmar);
  drawHorizontalBars('c-compare-dd', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:Math.abs(m.max_drawdown||0)*100, color:STRATEGIES[i].color, formatted:(Math.abs(m.max_drawdown||0)*100).toFixed(1)+'%' }; }), METRIC_ZONES.dd);
  drawHorizontalBars('c-compare-wr', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:(m.win_rate||0)*100, color:STRATEGIES[i].color, formatted:((m.win_rate||0)*100).toFixed(1)+'%' }; }), METRIC_ZONES.wr);
  drawHorizontalBars('c-compare-pf', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:m.profit_factor||0, color:STRATEGIES[i].color, formatted:(m.profit_factor||0).toFixed(2) }; }), METRIC_ZONES.pf);
}

// ===== DRAW PAGE CHARTS =====
function drawPageCharts(pageId) {
  if (pageId === 'compare') {
    drawCompareEquity();
    drawCompareMetricBars();
    drawCompareExtras();
    buildCompareParameters();
    setupTooltip('c-compare-eq', 'tt-compare-eq');
    setupTooltip('c-compare-dd-time', 'tt-compare-dd-time');
    setupTooltip('c-compare-rsharpe', 'tt-compare-rsharpe');
    return;
  }
  if (pageId === 'overview') {
    if (IS_SINGLE) {
      drawSingleOverviewEquity();
      setupTooltip('c-overview-eq', 'tt-overview-eq');
    } else {
      drawMultiOverviewEquity();
      drawMetricComparison();
      rebuildBenchmarkInsights();
      buildEquityLegend();
      drawMultiOverviewDrawdown();
      drawReturnDistribution();
      buildCorrelationMatrix();
      drawMultiRollingSharpe();
      rebuildOverviewTradingActivity();
      rebuildReturnScenarios();
      drawRiskReturnScatter('c-overview-scatter');
      drawRollingReturns('overview');
      setupTooltip('c-overview-eq', 'tt-overview-eq');
      setupTooltip('c-overview-dd', 'tt-overview-dd');
      setupTooltip('c-overview-rsharpe', 'tt-overview-rsharpe');
    }
    return;
  }
  if (pageId === 'finterion') return;

  if (IS_SINGLE) {
    // Single mode: run page with full details
    const rd = RUN_DATA[pageId];
    if (!rd) return;
    drawLineChart('c-'+pageId+'-equity', rd.EQ, COL.accent, { fill:true, prefix:'\u20AC', decimals:0, fillColor:COL.accent+'20' });
    drawAreaChart('c-'+pageId+'-dd', rd.DD, COL.red);
    drawLineChart('c-'+pageId+'-cumret', rd.CR, COL.green, { fill:true, suffix:'%', decimals:1, fillColor:COL.green+'15' });
    drawBarChart('c-'+pageId+'-yearly', rd.YR);
    buildHeatmap('heatmap-'+pageId, rd.MONTHLY_HEATMAP);
    drawDonut('c-'+pageId+'-donut', 'legend-'+pageId+'-donut', rd.SYM_STATS);
    drawPnlBar('c-'+pageId+'-pnl', rd.SYM_STATS);
    renderTrades(pageId, rd.TRADES);
    drawLineChart('c-'+pageId+'-rsharpe', rd.RS, COL.amber, { decimals:2 });
    drawAreaChart('c-'+pageId+'-dd2', rd.DD, COL.red);
    setupTooltip('c-'+pageId+'-equity', 'tt-'+pageId+'-equity');
    setupTooltip('c-'+pageId+'-dd', 'tt-'+pageId+'-dd');
    setupTooltip('c-'+pageId+'-cumret', 'tt-'+pageId+'-cumret');
    setupTooltip('c-'+pageId+'-rsharpe', 'tt-'+pageId+'-rsharpe');
    setupTooltip('c-'+pageId+'-dd2', 'tt-'+pageId+'-dd2');
  } else {
    // Multi mode: strategy page (unified, no tabs)
    const match = pageId.match(/^strat-(\d+)$/);
    if (!match) return;
    const idx = parseInt(match[1]);
    const strat = STRATEGIES[idx];
    if (!strat) return;
    updateStratSummary(idx);
    updateStratPerformance(idx);
    drawStrategyEquity(idx);
    drawStrategyRollingSharpe(idx);
    drawStrategyDrawdown(idx);
    populateStratRunsTable(idx);
    buildStratParameters(idx);
    setupTooltip('c-'+pageId+'-eq', 'tt-'+pageId+'-eq');
    setupTooltip('c-'+pageId+'-rsharpe', 'tt-'+pageId+'-rsharpe');
    setupTooltip('c-'+pageId+'-dd', 'tt-'+pageId+'-dd');
    initCollapseButtons();
  }
}

// ===== POPULATE RUNS TAB CELLS =====
function populateRunsTabs() {
  STRATEGIES.forEach((s, idx) => {
    populateStratRunsTable(idx);
  });
}

function populateStratRunsTable(stratIdx) {
  const s = STRATEGIES[stratIdx];
  if (!s) return;
  const table = document.querySelector('#strat-runs-table-'+stratIdx+' tbody');
  if (!table) return;
  const rows = table.querySelectorAll('tr');
  s.runIds.forEach((rid, j) => {
    if (j >= rows.length) return;
    const rd = RUN_DATA[rid];
    if (!rd || !rd.metrics) return;
    const m = rd.metrics;
    const cells = rows[j].querySelectorAll('td');
    // cells: [Run label, Return, Sharpe, Max DD, Trades]
    if (cells.length >= 5) {
      cells[1].textContent = m.total_net_gain_percentage != null ? (m.total_net_gain_percentage * 100).toFixed(1) + '%' : '—';
      cells[2].textContent = m.sharpe_ratio != null ? m.sharpe_ratio.toFixed(2) : '—';
      cells[3].textContent = m.max_drawdown != null ? (Math.abs(m.max_drawdown) * 100).toFixed(1) + '%' : '—';
      cells[4].textContent = m.number_of_trades != null ? m.number_of_trades : '—';
    }
  });
}

// ===== RISK-RETURN SCATTER =====
function drawRiskReturnScatter(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const r = resizeCanvas(canvasId);
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:25, r:60, b:40, l:60 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;

  const visibleIndices = canvasId.includes('compare')
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : (selectedForCompare.size > 0
        ? Array.from(selectedForCompare).sort((a,b) => a-b)
        : STRATEGIES.map((_,i) => i));

  // Collect data points
  const pts = [];
  visibleIndices.forEach(i => {
    const m = getViewMetrics(i);
    const vol = m.annual_volatility != null ? Math.abs(m.annual_volatility) * 100 : null;
    const cagr = STRATEGIES[i].summary.cagr != null ? STRATEGIES[i].summary.cagr * 100 : null;
    if (vol != null && cagr != null) {
      pts.push({ i, vol, cagr, color: STRATEGIES[i].color, name: STRATEGIES[i].name });
    }
  });

  if (pts.length < 1) {
    ctx.font = '12px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'center';
    ctx.fillText('No data available', w/2, h/2);
    return;
  }

  const vols = pts.map(p => p.vol), cagrs = pts.map(p => p.cagr);
  let xMin = Math.min(...vols)*0.8, xMax = Math.max(...vols)*1.2;
  let yMin = Math.min(...cagrs, 0), yMax = Math.max(...cagrs)*1.2;
  if (xMin === xMax) { xMin -= 1; xMax += 1; }
  if (yMin === yMax) { yMin -= 1; yMax += 1; }
  const xRange = xMax - xMin, yRange = yMax - yMin;

  // Grid
  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim;
  ctx.textAlign = 'right';
  for (let i = 0; i <= 5; i++) {
    const y = pad.t + ch - (i/5)*ch;
    const val = yMin + (i/5)*yRange;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w-pad.r, y); ctx.stroke();
    ctx.fillText(val.toFixed(1)+'%', pad.l-5, y+3.5);
  }
  ctx.textAlign = 'center';
  for (let i = 0; i <= 5; i++) {
    const x = pad.l + (i/5)*cw;
    const val = xMin + (i/5)*xRange;
    ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t+ch); ctx.stroke();
    ctx.fillText(val.toFixed(1)+'%', x, h-pad.b+15);
  }

  // Axis labels
  ctx.font = '11px JetBrains Mono, monospace'; ctx.fillStyle = COL.text;
  ctx.textAlign = 'center';
  ctx.fillText('Volatility', pad.l + cw/2, h-5);
  ctx.save(); ctx.translate(12, pad.t + ch/2); ctx.rotate(-Math.PI/2);
  ctx.fillText('CAGR', 0, 0); ctx.restore();

  // Zero line
  if (yMin < 0 && yMax > 0) {
    const zy = pad.t + ch - ((0-yMin)/yRange)*ch;
    ctx.strokeStyle = COL.dim; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l, zy); ctx.lineTo(w-pad.r, zy); ctx.stroke();
    ctx.setLineDash([]);
  }

  // Plot dots
  pts.forEach(p => {
    const x = pad.l + ((p.vol-xMin)/xRange)*cw;
    const y = pad.t + ch - ((p.cagr-yMin)/yRange)*ch;
    ctx.beginPath(); ctx.arc(x, y, 7, 0, Math.PI*2);
    ctx.fillStyle = p.color; ctx.fill();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
    // Label
    ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.text;
    ctx.textAlign = 'center';
    ctx.fillText(p.name, x, y-12);
  });

  canvas._chartData = { pts, pad, cw, ch, xMin, xRange, yMin, yRange, type:'scatter' };
}

// ===== ROLLING RETURNS =====
function drawRollingReturns(page) {
  const prefix = page === 'compare' ? 'compare' : 'overview';
  const canvas = document.getElementById('c-'+prefix+'-rolling-ret');
  if (!canvas) return;
  const wrap = canvas.parentElement;

  const periodSel = document.getElementById(prefix+'-rolling-ret-period');
  const months = periodSel ? parseInt(periodSel.value) : 12;

  // Update title
  const card = canvas.closest('.chart-card');
  if (card) {
    const title = card.querySelector('.chart-title');
    if (title) {
      const selHTML = title.querySelector('select');
      const selOuter = selHTML ? selHTML.outerHTML : '';
      title.innerHTML = 'Rolling '+months+'-Month Returns ' + selOuter;
    }
  }

  let placeholder = wrap.querySelector('.eq-placeholder');
  if (selectedRunView === 'summary') {
    const r2 = resizeCanvas('c-'+prefix+'-rolling-ret');
    if (r2) { r2.ctx.clearRect(0, 0, r2.w, r2.h); }
    if (!placeholder) {
      placeholder = document.createElement('div');
      placeholder.className = 'eq-placeholder';
      placeholder.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:13px;pointer-events:none;';
      wrap.style.position = 'relative';
      wrap.appendChild(placeholder);
    }
    placeholder.textContent = 'Select a backtest window to view rolling returns';
    placeholder.style.display = 'flex';
    wrap.style.height = '80px';
    return;
  }
  if (placeholder) placeholder.style.display = 'none';
  wrap.style.height = '';

  const visibleIndices = page === 'compare'
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : (selectedForCompare.size > 0
        ? Array.from(selectedForCompare).sort((a,b) => a-b)
        : STRATEGIES.map((_,i) => i));

  const r = resizeCanvas('c-'+prefix+'-rolling-ret');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;

  // Compute rolling returns from monthly returns
  const allSeries = [];
  visibleIndices.forEach(i => {
    const rd = getViewRunData(i);
    if (!rd || !rd.MR || rd.MR.length < months) return;
    const mr = rd.MR;
    const rolling = [];
    for (let j = months; j <= mr.length; j++) {
      let compounded = 1;
      for (let k = j - months; k < j; k++) {
        compounded *= (1 + mr[k][0]);
      }
      rolling.push([(compounded - 1) * 100, mr[j-1][1]]);
    }
    allSeries.push({ data: rolling, color: STRATEGIES[i].color, name: STRATEGIES[i].name, isChal: challengerIdx === i });
  });

  // Need at least 2 rolling data points to draw a meaningful line
  const maxPts = allSeries.reduce((mx, s) => Math.max(mx, s.data.length), 0);
  if (allSeries.length === 0 || maxPts < 2) {
    ctx.font = '12px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'center';
    const hint = months > 3 ? '  Try a shorter period.' : '';
    ctx.fillText('Window too short for ' + months + '-month rolling returns.' + hint, w/2, h/2);
    return;
  }

  let gMin = 0, gMax = 0;
  allSeries.forEach(s => s.data.forEach(d => { if (d[0]<gMin) gMin=d[0]; if (d[0]>gMax) gMax=d[0]; }));
  if (gMin === gMax) { gMin -= 1; gMax += 1; }
  const range = gMax - gMin;

  // Grid
  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i=0;i<=5;i++) {
    const y = pad.t+ch-(i/5)*ch;
    const val = gMin+(i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    ctx.fillText(val.toFixed(0)+'%', w-pad.r+50, y+3.5);
  }
  if (gMin<0 && gMax>0) {
    const zeroY = pad.t+ch-((0-gMin)/range)*ch;
    ctx.strokeStyle = COL.dim; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l,zeroY); ctx.lineTo(w-pad.r,zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }

  // Sort: challenger on top
  const sorted = [...allSeries].sort((a,b) => (a.isChal?1:0)-(b.isChal?1:0));
  sorted.forEach((s, ci) => {
    if (ci===0 && s.data.length>1) {
      ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
      const li = Math.max(1, Math.floor(s.data.length/6));
      for (let i=0;i<s.data.length;i+=li) { const x=pad.l+(i/(s.data.length-1))*cw; ctx.fillText(s.data[i][1], x, h-5); }
    }
    ctx.beginPath(); ctx.strokeStyle = s.color;
    ctx.lineWidth = s.isChal ? 3.5 : 2; ctx.lineJoin = 'round';
    s.data.forEach((d, di) => {
      const x = pad.l + (di/(s.data.length-1))*cw;
      const y = pad.t + ch - ((d[0]-gMin)/range)*ch;
      di===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    });
    ctx.stroke();
  });
}

// ===== RELATIVE PERFORMANCE (compare page only) =====
function drawRelativePerformance() {
  const canvas = document.getElementById('c-compare-relative');
  if (!canvas) return;
  const wrap = canvas.parentElement;

  let placeholder = wrap.querySelector('.eq-placeholder');
  if (selectedRunView === 'summary') {
    const r2 = resizeCanvas('c-compare-relative');
    if (r2) { r2.ctx.clearRect(0, 0, r2.w, r2.h); }
    if (!placeholder) {
      placeholder = document.createElement('div');
      placeholder.className = 'eq-placeholder';
      placeholder.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--dim);font-size:13px;pointer-events:none;';
      wrap.style.position = 'relative';
      wrap.appendChild(placeholder);
    }
    placeholder.textContent = 'Select a backtest window to view relative performance';
    placeholder.style.display = 'flex';
    wrap.style.height = '80px';
    return;
  }
  if (placeholder) placeholder.style.display = 'none';
  wrap.style.height = '';

  const indices = Array.from(selectedForCompare).sort((a,b) => a-b);
  if (indices.length < 2) return;

  // Base: first selected strategy
  const baseEq = getViewEquity(indices[0]);
  if (!baseEq || baseEq.length < 2) return;

  const r = resizeCanvas('c-compare-relative');
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:15, r:60, b:30, l:10 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;

  // Calculate relative: (stratEq / baseEq - 1) * 100
  const allLines = [];
  indices.slice(1).forEach(i => {
    const eq = getViewEquity(i);
    if (!eq || eq.length < 2) return;
    const len = Math.min(eq.length, baseEq.length);
    const rel = [];
    for (let j = 0; j < len; j++) {
      const base = baseEq[j][0] !== 0 ? baseEq[j][0] : 1;
      // Normalize: both start at 0%, so use (1+eq/100)/(1+base/100) - 1
      const eqVal = 1 + eq[j][0]/100;
      const baseVal = 1 + base/100;
      rel.push([(eqVal/baseVal - 1) * 100, eq[j][1]]);
    }
    allLines.push({ data: rel, color: STRATEGIES[i].color, name: STRATEGIES[i].name, isChal: challengerIdx === i });
  });

  if (allLines.length === 0) return;

  let gMin=0, gMax=0;
  allLines.forEach(l => l.data.forEach(d => { if(d[0]<gMin) gMin=d[0]; if(d[0]>gMax) gMax=d[0]; }));
  if (gMin===gMax) { gMin-=1; gMax+=1; }
  const range = gMax-gMin;

  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i=0;i<=5;i++) {
    const y = pad.t+ch-(i/5)*ch;
    const val = gMin+(i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    ctx.fillText(val.toFixed(1)+'%', w-pad.r+50, y+3.5);
  }
  // Zero line
  if (gMin<0 && gMax>0) {
    const zeroY = pad.t+ch-((0-gMin)/range)*ch;
    ctx.strokeStyle = COL.dim; ctx.setLineDash([4,4]);
    ctx.beginPath(); ctx.moveTo(pad.l,zeroY); ctx.lineTo(w-pad.r,zeroY); ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
  if (allLines[0].data.length > 1) {
    const li = Math.max(1, Math.floor(allLines[0].data.length/6));
    for (let i=0;i<allLines[0].data.length;i+=li) { const x=pad.l+(i/(allLines[0].data.length-1))*cw; ctx.fillText(allLines[0].data[i][1], x, h-5); }
  }
  allLines.forEach(l => {
    ctx.beginPath(); ctx.strokeStyle = l.color;
    ctx.lineWidth = l.isChal ? 3.5 : 2; ctx.lineJoin = 'round';
    l.data.forEach((d, di) => {
      const x = pad.l + (di/(l.data.length-1))*cw;
      const y = pad.t + ch - ((d[0]-gMin)/range)*ch;
      di===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    });
    ctx.stroke();
  });
  // Label base strategy
  ctx.font = '11px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'left';
  ctx.fillText('vs ' + STRATEGIES[indices[0]].name, pad.l+5, pad.t+12);
}

// ===== STRATEGY PARAMETERS =====

function buildStratParameters(stratIdx) {
  var sid = 'strat-' + stratIdx;
  var el = document.getElementById(sid + '-parameters');
  if (!el) return;
  var params = STRATEGIES[stratIdx].parameters;
  if (!params || Object.keys(params).length === 0) { el.innerHTML = ''; return; }
  var html = '<div class="chart-card">';
  html += '<div class="chart-title">Strategy Parameters</div>';
  html += '<div class="table-wrap"><table class="comp-table params-table"><thead><tr><th>Parameter</th><th>Value</th></tr></thead><tbody>';
  var keys = Object.keys(params).sort();
  for (var k = 0; k < keys.length; k++) {
    var key = keys[k];
    var val = params[key];
    if (typeof val === 'object' && val !== null) val = JSON.stringify(val);
    html += '<tr><td>' + key + '</td><td>' + String(val) + '</td></tr>';
  }
  html += '</tbody></table></div></div>';
  el.innerHTML = html;
}

function buildCompareParameters() {
  var el = document.getElementById('compare-parameters');
  if (!el) return;
  // Collect all parameter keys across all strategies
  var allKeys = {};
  var hasAny = false;
  var indices = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort(function(a,b){return a-b;})
    : STRATEGIES.map(function(_, i) { return i; });
  for (var i = 0; i < indices.length; i++) {
    var params = STRATEGIES[indices[i]].parameters;
    if (params && Object.keys(params).length > 0) {
      hasAny = true;
      var ks = Object.keys(params);
      for (var j = 0; j < ks.length; j++) allKeys[ks[j]] = true;
    }
  }
  if (!hasAny) { el.innerHTML = ''; return; }
  var sortedKeys = Object.keys(allKeys).sort();
  var html = '<div class="chart-card">';
  html += '<div class="chart-title">Parameters Comparison</div>';
  html += '<div class="table-wrap"><table class="comp-table params-table"><thead><tr><th>Parameter</th>';
  for (var i = 0; i < indices.length; i++) {
    html += '<th><span class="sb-dot" style="background:' + STRATEGIES[indices[i]].color + '"></span> ' + STRATEGIES[indices[i]].name + '</th>';
  }
  html += '</tr></thead><tbody>';
  for (var k = 0; k < sortedKeys.length; k++) {
    var key = sortedKeys[k];
    html += '<tr><td>' + key + '</td>';
    // Check if all values are the same
    var vals = [];
    for (var i = 0; i < indices.length; i++) {
      var p = STRATEGIES[indices[i]].parameters || {};
      var v = p[key];
      if (v === undefined) v = '—';
      else if (typeof v === 'object' && v !== null) v = JSON.stringify(v);
      else v = String(v);
      vals.push(v);
    }
    var allSame = vals.every(function(v) { return v === vals[0]; });
    for (var i = 0; i < vals.length; i++) {
      var style = '';
      if (!allSame && vals[i] !== '—') style = ' style="color:var(--accent);font-weight:600"';
      html += '<td' + style + '>' + vals[i] + '</td>';
    }
    html += '</tr>';
  }
  html += '</tbody></table></div></div>';
  el.innerHTML = html;
}

// ===== INIT =====
buildBenchmarkChips();
rebuildWindowCoverage();
rebuildOverviewKPIs();
rebuildRankingTable();
rebuildOverviewTradingActivity();
rebuildReturnScenarios();
initCollapseButtons();
syncModalCount();
populateRunsTabs();
drawPageCharts('overview');
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => drawPageCharts(currentPage), 100);
});
