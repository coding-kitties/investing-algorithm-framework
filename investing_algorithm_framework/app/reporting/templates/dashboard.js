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
  ['Profit Factor','profit_factor','ratio','max'],
  ['Win Rate','win_rate','pct_abs','max'],
  ['Trades/yr','trades_per_year','ratio','neutral'],
  ['Net Gain %','total_net_gain_percentage','pct','max'],
];

// Windows column offset: Strategy(0), Windows(1), then COMP_COLS start at index 2
const WINDOWS_COL_IDX = 1;

let selectedRunView = 'summary';

// Populate dropdowns (multi mode only)
(function() {
  const selectors = [document.getElementById('overview-window-select')];
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

function getViewMetrics(stratIdx) {
  const s = STRATEGIES[stratIdx];
  if (selectedRunView === 'summary') return s.summary;
  const rid = s.runNameMap[selectedRunView];
  if (rid && RUN_DATA[rid]) return RUN_DATA[rid].metrics;
  return s.summary;
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

function fmtVal(v, kind) {
  if (v == null) return '—';
  if (kind === 'pct') return (v*100 >= 0 ? '+' : '') + (v*100).toFixed(1) + '%';
  if (kind === 'pct_abs') return (Math.abs(v)*100).toFixed(1) + '%';
  if (kind === 'ratio') return v.toFixed(2);
  if (kind === 'int') return String(Math.round(v));
  return String(v);
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
function drawHorizontalBars(id, items) {
  if (!items || items.length === 0) return;
  const r = resizeCanvas(id);
  if (!r) return;
  const { ctx, w, h } = r;
  const pad = { t:8, r:75, b:8, l:90 };
  const cw = w-pad.l-pad.r, ch = h-pad.t-pad.b;
  const maxVal = Math.max(...items.map(d => Math.abs(d.value))) || 1;
  const barH = Math.min(28, ch/items.length-4);
  const gap = ch/items.length;
  ctx.font = '11px Inter, sans-serif'; ctx.textBaseline = 'middle';
  items.forEach((d, i) => {
    const y = pad.t + gap*i + gap/2;
    const barW = (Math.abs(d.value)/maxVal)*cw;
    ctx.fillStyle = d.color+'30'; ctx.strokeStyle = d.color; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.roundRect(pad.l, y-barH/2, barW, barH, [0,4,4,0]); ctx.fill(); ctx.stroke();
    ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
    ctx.fillText(d.name.slice(0,12), pad.l-8, y);
    ctx.fillStyle = d.color; ctx.textAlign = 'left';
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
  const equities = visibleIndices.map(i => ({ eq:getViewEquity(i), color:STRATEGIES[i].color }));
  equities.forEach((item, ci) => {
    const eq = item.eq; if (!eq || eq.length<2) return;
    if (ci===0) {
      ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
      const li = Math.max(1,Math.floor(eq.length/6));
      for (let i=0;i<eq.length;i+=li) { const x=pad.l+(i/(eq.length-1))*cw; ctx.fillText(eq[i][1], x, h-5); }
    }
    ctx.beginPath(); ctx.strokeStyle = item.color; ctx.lineWidth = 2; ctx.lineJoin = 'round';
    for (let i=0;i<eq.length;i++) {
      const x=pad.l+(i/(eq.length-1))*cw;
      const y=pad.t+ch-((eq[i][0]-gMin)/range)*ch;
      i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
    }
    ctx.stroke();
  });
  if (equities.length>0 && equities[0].eq.length>0) {
    canvas._chartData = { data:equities[0].eq, pad, cw, ch, mn:gMin, range, color:equities[0].color, opts:{suffix:'%',decimals:1}, type:'line' };
  }
}

// ===== METRIC COMPARISON BARS (multi mode) =====
function drawMetricComparison() {
  const vis = selectedForCompare.size > 0
    ? Array.from(selectedForCompare).sort((a,b) => a-b)
    : STRATEGIES.map((_,i) => i);
  drawHorizontalBars('c-cmp-cagr', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:(m.cagr||0)*100, color:s.color, formatted:((m.cagr||0)*100).toFixed(1)+'%' }; }));
  drawHorizontalBars('c-cmp-sharpe', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:m.sharpe_ratio||0, color:s.color, formatted:(m.sharpe_ratio||0).toFixed(2) }; }));
  drawHorizontalBars('c-cmp-dd', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:Math.abs(m.max_drawdown||0)*100, color:s.color, formatted:(Math.abs(m.max_drawdown||0)*100).toFixed(1)+'%' }; }));
  drawHorizontalBars('c-cmp-wr', vis.map(i => { const s=STRATEGIES[i]; const m=getViewMetrics(i); return { name:s.name, value:(m.win_rate||0)*100, color:s.color, formatted:((m.win_rate||0)*100).toFixed(1)+'%' }; }));
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
  let gMin=Infinity, gMax=-Infinity;
  strat.runIds.forEach(rid => {
    const rd = RUN_DATA[rid]; if (!rd) return;
    rd.EQ.forEach(d => { if(d[0]<gMin) gMin=d[0]; if(d[0]>gMax) gMax=d[0]; });
  });
  if (!isFinite(gMin)) return;
  if (gMin===gMax) { gMin-=1; gMax+=1; }
  const range = gMax-gMin;
  ctx.strokeStyle = COL.border; ctx.lineWidth = 1;
  ctx.font = '10px JetBrains Mono, monospace'; ctx.fillStyle = COL.dim; ctx.textAlign = 'right';
  for (let i=0;i<=5;i++) {
    const y = pad.t+ch-(i/5)*ch; const val = gMin+(i/5)*range;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    ctx.fillText('\u20AC'+val.toFixed(0), w-pad.r+55, y+3.5);
  }
  strat.runIds.forEach((rid, ci) => {
    const rd = RUN_DATA[rid]; if (!rd || !rd.EQ || rd.EQ.length<2) return;
    const eq = rd.EQ; const color = colors[ci%colors.length];
    if (ci===0) {
      ctx.textAlign = 'center'; ctx.fillStyle = COL.dim;
      const li = Math.max(1,Math.floor(eq.length/6));
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
}

// ===== REBUILD (multi mode dynamic) =====
function rebuildOverviewKPIs() {
  const kpiRow = document.querySelector('#page-overview .kpi-row');
  if (!kpiRow) return;
  let bestCagr={val:-Infinity,name:''}, bestSharpe={val:-Infinity,name:''}, bestSortino={val:-Infinity,name:''}, bestCalmar={val:-Infinity,name:''}, bestWR={val:-Infinity,name:''}, bestDD={val:Infinity,name:''};
  STRATEGIES.forEach((s,i) => {
    const m = getViewMetrics(i);
    if ((m.cagr||0)>bestCagr.val) bestCagr={val:m.cagr,name:s.name};
    if ((m.sharpe_ratio||0)>bestSharpe.val) bestSharpe={val:m.sharpe_ratio,name:s.name};
    if ((m.sortino_ratio||0)>bestSortino.val) bestSortino={val:m.sortino_ratio,name:s.name};
    if ((m.calmar_ratio||0)>bestCalmar.val) bestCalmar={val:m.calmar_ratio,name:s.name};
    if ((m.win_rate||0)>bestWR.val) bestWR={val:m.win_rate,name:s.name};
    if (Math.abs(m.max_drawdown||1)<bestDD.val) bestDD={val:Math.abs(m.max_drawdown||1),name:s.name};
  });
  const cards = kpiRow.querySelectorAll('.kpi-card');
  if (cards[2]) { cards[2].querySelector('.kpi-value').textContent = fmtVal(bestCagr.val,'pct'); const sub=cards[2].querySelector('.kpi-sub'); if(sub) sub.textContent=bestCagr.name.slice(0,25); }
  if (cards[3]) { cards[3].querySelector('.kpi-value').textContent = fmtVal(bestSharpe.val,'ratio'); const sub=cards[3].querySelector('.kpi-sub'); if(sub) sub.textContent=bestSharpe.name.slice(0,25); }
  if (cards[4]) { cards[4].querySelector('.kpi-value').textContent = fmtVal(bestSortino.val,'ratio'); const sub=cards[4].querySelector('.kpi-sub'); if(sub) sub.textContent=bestSortino.name.slice(0,25); }
  if (cards[5]) { cards[5].querySelector('.kpi-value').textContent = fmtVal(bestCalmar.val,'ratio'); const sub=cards[5].querySelector('.kpi-sub'); if(sub) sub.textContent=bestCalmar.name.slice(0,25); }
  if (cards[6]) { cards[6].querySelector('.kpi-value').textContent = fmtVal(bestWR.val,'pct_abs'); const sub=cards[6].querySelector('.kpi-sub'); if(sub) sub.textContent=bestWR.name.slice(0,25); }
  if (cards[7]) { cards[7].querySelector('.kpi-value').textContent = fmtVal(bestDD.val,'pct_abs'); const sub=cards[7].querySelector('.kpi-sub'); if(sub) sub.textContent=bestDD.name.slice(0,25); }
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

  // Build sorted index array
  let indices = STRATEGIES.map((_,i) => i);
  if (rankingSortCol) {
    indices.sort((a,b) => {
      const ma = getViewMetrics(a), mb = getViewMetrics(b);
      let va = ma[rankingSortCol], vb = mb[rankingSortCol];
      if (rankingSortCol === '_n_windows') { va = STRATEGIES[a].runIds.length; vb = STRATEGIES[b].runIds.length; }
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
      const m=getViewMetrics(i); const v=m[key];
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
    const checked = selectedForCompare.has(i) ? ' checked' : '';
    html += '<tr class="comp-row">';
    html += '<td class="check-col"><input type="checkbox" class="strat-checkbox" data-strat-idx="'+i+'"'+checked+' onclick="event.stopPropagation();toggleStratCompare('+i+',this.checked)"></td>';
    html += '<td class="sticky-col" onclick="showPage(\'strat-'+i+'\')"><span class="sb-dot" style="background:'+s.color+'"></span>'+s.name+'</td>';
    html += '<td onclick="showPage(\'strat-'+i+'\')">' + s.runIds.length + '</td>';
    COMP_COLS.forEach(([label,key,ftype,direction]) => {
      const v = m[key];
      const isBest = bestVals[key]===i;
      const cls = (isBest && pageIndices.length>1) ? ' class="best-cell"' : '';
      if (key==='max_drawdown' && v!=null) html += '<td'+cls+' onclick="showPage(\'strat-'+i+'\')">'+(Math.abs(v)*100).toFixed(1)+'%</td>';
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
  rebuildOverviewKPIs();
  rebuildRankingTable();
  drawMultiOverviewEquity();
  drawMetricComparison();
  setupTooltip('c-overview-eq', 'tt-overview-eq');
}

// ===== RUN SELECTION (per-strategy drill-down) =====
const stratSelectedRun = {};

function selectStratRun(stratIdx, runId) {
  stratSelectedRun[stratIdx] = runId;
  const pills = document.querySelectorAll('#run-sel-strat-' + stratIdx + ' .run-pill');
  pills.forEach(p => p.classList.toggle('active', p.dataset.run === runId));
  updateStratSummary(stratIdx);
  updateStratPerformance(stratIdx);
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

  if (runId === 'summary') {
    const m = strat.summary;
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
    // End-of-backtest KPIs from best/last run
    const eobEl = document.getElementById(sid + '-eob-kpis');
    if (eobEl) {
      let bestRid = strat.runIds[0], bestLen = 0;
      strat.runIds.forEach(function(r) { const d = RUN_DATA[r]; if (d && d.EQ && d.EQ.length > bestLen) { bestLen = d.EQ.length; bestRid = r; } });
      const sn = RUN_DATA[bestRid]?.snapshot || {};
      eobEl.innerHTML = '<div class="kpi-row">'
        + kpiCard('Equity', '€' + (sn.equity||0).toFixed(2), 'var(--accent)')
        + kpiCard('Net Profit', '€' + (sn.net_profit||0).toFixed(2), (sn.net_profit||0) >= 0 ? 'var(--green)' : 'var(--red)')
        + kpiCard('Growth', fmtVal(sn.growth,'pct'), 'var(--green)')
        + kpiCard('Holdings', '€' + (sn.holdings||0).toFixed(2))
        + kpiCard('Unrealized', '€' + (sn.unrealized||0).toFixed(2))
        + kpiCard('Fees', '€' + (sn.fees||0).toFixed(2), 'var(--amber)')
        + kpiCard('Volume', '€' + (sn.volume||0).toFixed(2))
        + '</div>';
    }
  } else {
    const rd = RUN_DATA[runId];
    if (!rd) return;
    const m = rd.metrics;
    const eq = rd.EQ;
    const finalVal = eq.length > 0 ? eq[eq.length-1][0] : 0;
    const initVal = eq.length > 0 ? eq[0][0] : 1000;
    const netGain = finalVal - initVal;
    container.innerHTML = '<div class="kpi-row">'
      + kpiCard('Final Value', '€' + finalVal.toFixed(2), 'var(--accent)', 'from €' + Math.round(initVal))
      + kpiCard('Total Return', fmtVal(m.total_net_gain_percentage,'pct'), 'var(--green)', '€' + netGain.toFixed(2))
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
      + '</div>';
    // End-of-backtest KPIs for the selected run
    const eobEl = document.getElementById(sid + '-eob-kpis');
    if (eobEl) {
      const sn = rd.snapshot || {};
      eobEl.innerHTML = '<div class="kpi-row">'
        + kpiCard('Equity', '€' + (sn.equity||0).toFixed(2), 'var(--accent)')
        + kpiCard('Net Profit', '€' + (sn.net_profit||0).toFixed(2), (sn.net_profit||0) >= 0 ? 'var(--green)' : 'var(--red)')
        + kpiCard('Growth', fmtVal(sn.growth,'pct'), 'var(--green)')
        + kpiCard('Holdings', '€' + (sn.holdings||0).toFixed(2))
        + kpiCard('Unrealized', '€' + (sn.unrealized||0).toFixed(2))
        + kpiCard('Fees', '€' + (sn.fees||0).toFixed(2), 'var(--amber)')
        + kpiCard('Volume', '€' + (sn.volume||0).toFixed(2))
        + '</div>';
    }
  }
}

function updateStratPerformance(stratIdx) {
  const sid = 'strat-' + stratIdx;
  const strat = STRATEGIES[stratIdx];
  const runId = stratSelectedRun[stratIdx] || 'summary';
  let rd, titleSuffix;
  if (runId === 'summary') {
    let bestRid = strat.runIds[0], bestLen = 0;
    strat.runIds.forEach(function(r) { const d = RUN_DATA[r]; if (d && d.EQ && d.EQ.length > bestLen) { bestLen = d.EQ.length; bestRid = r; } });
    rd = RUN_DATA[bestRid];
    titleSuffix = 'Best Run';
  } else {
    rd = RUN_DATA[runId];
    titleSuffix = rd ? rd.label : runId;
  }
  const htTitle = document.getElementById('ht-title-' + sid);
  const yrTitle = document.getElementById('yr-title-' + sid);
  if (htTitle) htTitle.textContent = 'Monthly Returns (' + titleSuffix + ')';
  if (yrTitle) yrTitle.textContent = 'Yearly Returns (' + titleSuffix + ')';
  if (rd) {
    buildHeatmap('heatmap-' + sid, rd.MONTHLY_HEATMAP);
    drawBarChart('c-' + sid + '-yearly', rd.YR);
  }
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
    drawMultiOverviewEquity();
    drawMetricComparison();
    setupTooltip('c-overview-eq', 'tt-overview-eq');
  }
}

function openCompare() {
  if (selectedForCompare.size < 2) return;
  buildComparePage();
  showPage('compare');
}

function buildComparePage() {
  const indices = Array.from(selectedForCompare).sort((a,b) => a-b);

  // KPI comparison table
  const kpiEl = document.getElementById('compare-kpis');
  if (kpiEl) {
    let html = '<div class="chart-card" style="margin-bottom:0"><div class="chart-title">Metrics Comparison</div><div class="table-wrap"><table class="comp-table"><thead><tr><th>Metric</th>';
    indices.forEach(i => html += '<th><span class="sb-dot" style="background:'+STRATEGIES[i].color+'"></span> '+STRATEGIES[i].name+'</th>');
    html += '</tr></thead><tbody>';
    const metrics = [
      ['CAGR','cagr','pct'], ['Sharpe','sharpe_ratio','ratio'], ['Sortino','sortino_ratio','ratio'],
      ['Calmar','calmar_ratio','ratio'], ['Max DD','max_drawdown','pct_abs'], ['Profit Factor','profit_factor','ratio'],
      ['Win Rate','win_rate','pct_abs'], ['Trades/yr','trades_per_year','ratio'], ['Volatility','annual_volatility','pct_abs'],
      ['Net Gain','total_net_gain_percentage','pct']
    ];
    metrics.forEach(([label, key, fmt]) => {
      html += '<tr><td class="sticky-col">'+label+'</td>';
      let bestIdx=-1, bestVal=key==='max_drawdown'?Infinity:-Infinity;
      indices.forEach(i => {
        const v = getViewMetrics(i)[key];
        if (v==null) return;
        if (key==='max_drawdown') { if(Math.abs(v)<bestVal){bestVal=Math.abs(v);bestIdx=i;} }
        else { if(v>bestVal){bestVal=v;bestIdx=i;} }
      });
      indices.forEach(i => {
        const v = getViewMetrics(i)[key];
        const isBest = bestIdx===i && indices.length>1;
        const cls = isBest ? ' class="best-cell"' : '';
        if (key==='max_drawdown' && v!=null) html += '<td'+cls+'>'+(Math.abs(v)*100).toFixed(1)+'%</td>';
        else html += '<td'+cls+'>'+fmtVal(v,fmt)+'</td>';
      });
      html += '</tr>';
    });
    html += '</tbody></table></div></div>';
    kpiEl.innerHTML = html;
  }

  // Monthly returns: unified card with all algorithms, year dropdown
  const moEl = document.getElementById('compare-monthly');
  if (moEl) {
    // Collect all years across all selected strategies
    const allYears = new Set();
    indices.forEach(i => {
      const strat = STRATEGIES[i];
      let targetRid = strat.runIds[0], bestLen = 0;
      strat.runIds.forEach(r => { const d = RUN_DATA[r]; if (d && d.EQ && d.EQ.length > bestLen) { bestLen = d.EQ.length; targetRid = r; } });
      const rd = RUN_DATA[targetRid];
      if (rd && rd.MONTHLY_HEATMAP) Object.keys(rd.MONTHLY_HEATMAP).forEach(y => allYears.add(y));
    });
    const years = Array.from(allYears).sort();
    let html = '<div class="chart-card">';
    html += '<div class="chart-title" style="display:flex;align-items:center;justify-content:space-between"><span>Monthly Returns</span>';
    if (years.length > 0) {
      html += '<select class="view-select" id="compare-year-select" onchange="filterCompareMonthly()">';
      html += '<option value="all">All Years</option>';
      years.forEach(y => html += '<option value="'+y+'">'+y+'</option>');
      html += '</select>';
    }
    html += '</div>';
    html += '<div id="compare-monthly-tables"></div>';
    html += '</div>';
    moEl.innerHTML = html;
  }

  // Yearly returns: unified card with all algorithms
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

function drawCompareExtras() {
  const indices = Array.from(selectedForCompare).sort((a,b) => a-b);
  // Build monthly heatmap tables
  buildCompareMonthlyTables('all');
  // Draw yearly bar charts
  indices.forEach(i => {
    const strat = STRATEGIES[i];
    let targetRid = strat.runIds[0], bestLen = 0;
    strat.runIds.forEach(r => { const d = RUN_DATA[r]; if (d && d.EQ && d.EQ.length > bestLen) { bestLen = d.EQ.length; targetRid = r; } });
    const rd = RUN_DATA[targetRid];
    if (rd && rd.YR) drawBarChart('c-compare-yearly-'+i, rd.YR);
  });
}

function buildCompareMonthlyTables(yearFilter) {
  const container = document.getElementById('compare-monthly-tables');
  if (!container) return;
  const indices = Array.from(selectedForCompare).sort((a,b) => a-b);
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  let html = '';
  indices.forEach(i => {
    const strat = STRATEGIES[i];
    let targetRid = strat.runIds[0], bestLen = 0;
    strat.runIds.forEach(r => { const d = RUN_DATA[r]; if (d && d.EQ && d.EQ.length > bestLen) { bestLen = d.EQ.length; targetRid = r; } });
    const rd = RUN_DATA[targetRid];
    if (!rd || !rd.MONTHLY_HEATMAP) return;
    const hm = rd.MONTHLY_HEATMAP;
    const years = (yearFilter === 'all' ? Object.keys(hm) : [yearFilter]).filter(y => hm[y]).sort();
    if (years.length === 0) return;
    html += '<div style="margin-bottom:1rem"><div style="font-size:0.72rem;font-weight:500;color:var(--text-secondary);margin-bottom:0.4rem;display:flex;align-items:center;gap:0.3rem"><span class="sb-dot" style="background:'+strat.color+'"></span>'+strat.name+'</div>';
    html += '<table class="heatmap-table"><thead><tr><th></th>';
    months.forEach(m => html += '<th>'+m+'</th>');
    html += '<th>Year</th></tr></thead><tbody>';
    years.forEach(y => {
      html += '<tr><th>'+y+'</th>';
      let yTotal = 0;
      months.forEach((_, mi) => {
        const v = hm[y]?.[mi+1];
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
    html += '</tbody></table></div>';
  });
  container.innerHTML = html;
}

function filterCompareMonthly() {
  const sel = document.getElementById('compare-year-select');
  if (!sel) return;
  buildCompareMonthlyTables(sel.value);
}

function drawCompareEquity() {
  const indices = Array.from(selectedForCompare).sort((a,b) => a-b);
  if (indices.length < 2) return;
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
  drawHorizontalBars('c-compare-cagr', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:(m.cagr||0)*100, color:STRATEGIES[i].color, formatted:((m.cagr||0)*100).toFixed(1)+'%' }; }));
  drawHorizontalBars('c-compare-sharpe', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:m.sharpe_ratio||0, color:STRATEGIES[i].color, formatted:(m.sharpe_ratio||0).toFixed(2) }; }));
  drawHorizontalBars('c-compare-dd', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:Math.abs(m.max_drawdown||0)*100, color:STRATEGIES[i].color, formatted:(Math.abs(m.max_drawdown||0)*100).toFixed(1)+'%' }; }));
  drawHorizontalBars('c-compare-wr', indices.map(i => { const m=getViewMetrics(i); return { name:STRATEGIES[i].name, value:(m.win_rate||0)*100, color:STRATEGIES[i].color, formatted:((m.win_rate||0)*100).toFixed(1)+'%' }; }));
}

// ===== DRAW PAGE CHARTS =====
function drawPageCharts(pageId) {
  if (pageId === 'compare') {
    drawCompareEquity();
    drawCompareMetricBars();
    drawCompareExtras();
    setupTooltip('c-compare-eq', 'tt-compare-eq');
    return;
  }
  if (pageId === 'overview') {
    if (IS_SINGLE) {
      drawSingleOverviewEquity();
      setupTooltip('c-overview-eq', 'tt-overview-eq');
    } else {
      drawMultiOverviewEquity();
      drawMetricComparison();
      setupTooltip('c-overview-eq', 'tt-overview-eq');
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
    // Multi mode: strategy page
    const match = pageId.match(/^strat-(\d+)$/);
    if (!match) return;
    const idx = parseInt(match[1]);
    const strat = STRATEGIES[idx];
    if (!strat) return;
    drawStrategyEquity(idx);
    if (strat.runIds.length > 0) {
      const selRun = stratSelectedRun[idx];
      let targetRid;
      if (selRun && selRun !== 'summary' && RUN_DATA[selRun]) {
        targetRid = selRun;
      } else {
        targetRid = strat.runIds[0];
        let bestLen = 0;
        strat.runIds.forEach(function(r) { const d = RUN_DATA[r]; if (d && d.EQ && d.EQ.length > bestLen) { bestLen = d.EQ.length; targetRid = r; } });
      }
      const rd = RUN_DATA[targetRid];
      if (rd) {
        const titleSuffix = (!selRun || selRun === 'summary') ? 'Best Run' : (rd.label || targetRid);
        const htTitle = document.getElementById('ht-title-' + pageId);
        const yrTitle = document.getElementById('yr-title-' + pageId);
        if (htTitle) htTitle.textContent = 'Monthly Returns (' + titleSuffix + ')';
        if (yrTitle) yrTitle.textContent = 'Yearly Returns (' + titleSuffix + ')';
        buildHeatmap('heatmap-'+pageId, rd.MONTHLY_HEATMAP);
        drawBarChart('c-'+pageId+'-yearly', rd.YR);
      }
    }
    setupTooltip('c-'+pageId+'-eq', 'tt-'+pageId+'-eq');
  }
}

// ===== INIT =====
rebuildRankingTable();
drawPageCharts('overview');
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => drawPageCharts(currentPage), 100);
});
