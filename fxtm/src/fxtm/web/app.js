'use strict';
(() => {
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* ---------- text ---------- */
const I18N = {
  en: {
    play: 'Play', pause: 'Pause', tick: '+1 tick', minute: '+1 min', hour: '+1 hour', speed: 'Speed',
    pauseOnClose: 'Pause on close', jump: 'Jump to time', restart: 'Restart',
    setupTitle: 'Pick a pair and a moment in the past',
    setupHelp: 'Ticks are downloaded once from Dukascopy to this computer and reused offline. All times are UTC.',
    pair: 'Currency pair', startUtc: 'Start (UTC)', endUtc: 'End (UTC)', examples: 'Examples',
    exSnb: 'Swiss franc shock, 2015', exBrexit: 'Brexit vote night, 2016',
    account: 'Practice account', currency: 'Account currency', balance: 'Starting balance', leverage: 'Leverage',
    advanced: 'Trading conditions', extraSpread: 'Extra spread (pips)', slippage: 'Slippage (pips)',
    latency: 'Order delay (seconds)', stopOut: 'Stop-out level (%)', fixedRate: 'Fixed conversion rate (optional)',
    fixedRateHelp: 'Profit is converted to the account currency using live prices of the conversion pair. Enter a rate only if you prefer a constant one.',
    startBtn: 'Load data and start', loading: 'Downloading...',
    market: 'Market', limit: 'Limit', stop: 'Stop', units: 'Units', price: 'Price', sl: 'Stop-loss', tp: 'Take-profit',
    modePrice: 'price', sell: 'Sell', buy: 'Buy', sellLimit: 'Sell limit', buyLimit: 'Buy limit',
    sellStop: 'Sell stop', buyStop: 'Buy stop', marginNeed: 'Margin needed {m} · free {f}',
    aBalance: 'Balance', aEquity: 'Equity', aFloating: 'Floating profit', aUsed: 'Margin used',
    aFree: 'Margin free', aLevel: 'Margin level',
    tabPositions: 'Positions', tabOrders: 'Orders', tabHistory: 'History', tabReport: 'Report', tabLog: 'Log',
    emptyPositions: 'No open positions. Use Buy or Sell to open one.', emptyOrders: 'No pending orders.',
    emptyHistory: 'Closed trades appear here.', emptyLog: 'Events appear here.',
    colId: '#', colSide: 'Side', colUnits: 'Units', colOpen: 'Entry', colSl: 'Stop-loss', colTp: 'Take-profit',
    colPnl: 'Profit', colType: 'Type', colPrice: 'Price', colOpened: 'Opened', colClosed: 'Closed',
    colExit: 'Exit', colReason: 'Reason', close: 'Close', closeAll: 'Close all', cancelOrder: 'Cancel',
    manual: 'manual', sl_: 'stop-loss', tp_: 'take-profit', stopout: 'stop-out',
    rReturn: 'Return', rEquity: 'Final equity', rDd: 'Max drawdown', rTrades: 'Trades', rWin: 'Win rate',
    rPf: 'Profit factor', rTotal: 'Total profit', rAvgWin: 'Average win', rAvgLoss: 'Average loss',
    rBest: 'Best trade', rWorst: 'Worst trade', rHold: 'Average holding', rStopouts: 'Stop-outs',
    rRejected: 'Rejected orders', updateReport: 'Update report', saveRun: 'Save this run',
    saved: 'Saved as run #{id} in {path}', jumpHelp: 'Move forward to (UTC)',
    jumpNote: 'Time only moves forward during a session. Restart to go back.', go: 'Go', cancel: 'Cancel',
    confirmRestart: 'Restart from the beginning? Open positions and trades will be discarded. Save the run first to keep it.',
    endOfData: 'End of data.', waiting: 'Waiting for the first candle...',
    equityEmpty: 'The equity curve appears after some time has passed.',
    evOpen: 'Position #{ref} opened: {units} units at {price}',
    evClose: 'Position #{ref} closed ({reason}) at {price}: {units} units',
    evPending: 'Order #{ref} placed: {note} at {price}', evCancel: 'Order #{ref} cancelled',
    evRejected: 'Order #{ref} rejected: {note}', evModify: 'Position #{ref} updated ({note})',
    errNumber: 'Enter a number.', errUnits: 'Enter the number of units.', errPrice: 'Enter a price for this order type.',
    errDate: 'Use the format YYYY-MM-DD HH:MM.', buySide: 'Buy', sellSide: 'Sell',
    ownData: 'Your own data files',
    ownDataHelp: "If the download does not work, export ticks to a CSV file (for example in your browser from Dukascopy's historical data page) and import it here. The file needs time, bid and ask columns.",
    csvFile: 'Tick CSV file', csvTz: 'Time zone of the file', importBtn: 'Import for the pair above',
    importing: 'Importing...', importedOk: 'Imported {n} ticks: {a} to {b} UTC', useImported: 'Use my imported data',
    datasets: 'Imported data (click to use)', datasetsEmpty: 'No imported data yet.', errFile: 'Choose a file first.',
  },
  ja: {
    play: '再生', pause: '一時停止', tick: '1ティック進む', minute: '1分進む', hour: '1時間進む', speed: '速度',
    pauseOnClose: '決済で一時停止', jump: '時刻へ移動', restart: '最初から',
    setupTitle: '通貨ペアと過去の時点を選びます',
    setupHelp: 'ティックデータはDukascopyから一度だけこのPCにダウンロードされ、以後はオフラインで使えます。時刻はすべてUTCです。',
    pair: '通貨ペア', startUtc: '開始 (UTC)', endUtc: '終了 (UTC)', examples: '例',
    exSnb: 'スイスフランショック (2015年)', exBrexit: '英国のEU離脱投票の夜 (2016年)',
    account: '練習口座', currency: '口座通貨', balance: '初期資金', leverage: 'レバレッジ',
    advanced: '取引条件', extraSpread: '追加スプレッド (pips)', slippage: 'スリッページ (pips)',
    latency: '約定の遅延 (秒)', stopOut: 'ロスカット水準 (%)', fixedRate: '固定の換算レート (任意)',
    fixedRateHelp: '損益は、換算用の通貨ペアの実際の価格で口座通貨に換算します。固定レートを使いたい場合だけ入力してください。',
    startBtn: 'データを読み込んで開始', loading: 'ダウンロード中...',
    market: '成行', limit: '指値', stop: '逆指値', units: '数量', price: '価格', sl: '損切り', tp: '利確',
    modePrice: '価格', sell: '売り', buy: '買い', sellLimit: '売り指値', buyLimit: '買い指値',
    sellStop: '売り逆指値', buyStop: '買い逆指値', marginNeed: '必要証拠金 {m}・余剰 {f}',
    aBalance: '残高', aEquity: '有効証拠金', aFloating: '含み損益', aUsed: '使用証拠金',
    aFree: '余剰証拠金', aLevel: '証拠金維持率',
    tabPositions: 'ポジション', tabOrders: '注文', tabHistory: '履歴', tabReport: 'レポート', tabLog: 'ログ',
    emptyPositions: '保有ポジションはありません。買いまたは売りで建てます。', emptyOrders: '待機中の注文はありません。',
    emptyHistory: '決済した取引がここに表示されます。', emptyLog: '出来事がここに表示されます。',
    colId: '#', colSide: '売買', colUnits: '数量', colOpen: '建値', colSl: '損切り', colTp: '利確',
    colPnl: '損益', colType: '種類', colPrice: '価格', colOpened: '建てた時刻', colClosed: '決済時刻',
    colExit: '決済値', colReason: '理由', close: '決済', closeAll: 'すべて決済', cancelOrder: '取消',
    manual: '手動', sl_: '損切り', tp_: '利確', stopout: 'ロスカット',
    rReturn: '収益率', rEquity: '最終有効証拠金', rDd: '最大ドローダウン', rTrades: '取引数', rWin: '勝率',
    rPf: 'プロフィットファクター', rTotal: '損益合計', rAvgWin: '平均利益', rAvgLoss: '平均損失',
    rBest: '最大利益', rWorst: '最大損失', rHold: '平均保有時間', rStopouts: 'ロスカット回数',
    rRejected: '拒否された注文', updateReport: 'レポートを更新', saveRun: 'この結果を保存',
    saved: '実行 #{id} として保存しました ({path})', jumpHelp: '進める時刻 (UTC)',
    jumpNote: '時刻は先にしか進められません。戻るには最初からやり直してください。', go: '移動', cancel: 'キャンセル',
    confirmRestart: '最初からやり直しますか? 保有ポジションと取引は破棄されます。残したい場合は先に保存してください。',
    endOfData: 'データの終わりです。', waiting: '最初のローソク足を待っています...',
    equityEmpty: 'しばらく時間が進むと、資金推移が表示されます。',
    evOpen: 'ポジション #{ref} を建てました: {units} @ {price}',
    evClose: 'ポジション #{ref} を決済しました ({reason}) @ {price}: {units}',
    evPending: '注文 #{ref} を出しました: {note} @ {price}', evCancel: '注文 #{ref} を取り消しました',
    evRejected: '注文 #{ref} は拒否されました: {note}', evModify: 'ポジション #{ref} を変更しました ({note})',
    errNumber: '数値を入力してください。', errUnits: '数量を入力してください。', errPrice: 'この注文には価格が必要です。',
    errDate: 'YYYY-MM-DD HH:MM の形式で入力してください。', buySide: '買い', sellSide: '売り',
    ownData: '手元のデータファイルを使う',
    ownDataHelp: 'ダウンロードがうまくいかない場合は、ブラウザなどでティックをCSVに書き出して、ここに読み込みます (例: Dukascopyのヒストリカルデータのページ)。時刻・Bid・Askの列が必要です。',
    csvFile: 'ティックのCSVファイル', csvTz: 'ファイルの時刻の時間帯', importBtn: '上の通貨ペアとして読み込む',
    importing: '読み込み中...', importedOk: '{n} ティックを読み込みました: {a} 〜 {b} (UTC)', useImported: '読み込んだデータを使う',
    datasets: '読み込んだデータ (クリックで選択)', datasetsEmpty: '読み込んだデータはまだありません。', errFile: '先にファイルを選んでください。',
  },
};

const TF_SEC = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600, '1d': 86400 };
const store = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
                set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } } };

const S = {
  lang: store.get('fxtm.lang') || ((navigator.language || 'en').startsWith('ja') ? 'ja' : 'en'),
  tz: store.get('fxtm.tz') || 'UTC',
  st: null, tf: '1m', candles: [], since: null, kind: 'market', tab: 'positions',
  playing: false, last: 0, log: [], posKey: '', ordKey: '', histKey: '',
};
const view = { barW: 9, off: 0, mx: null, my: null, drag: null };

const t = (key, vars) => {
  let s = (I18N[S.lang] && I18N[S.lang][key]) ?? I18N.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
  return s;
};
function applyI18n() {
  document.documentElement.lang = S.lang;
  $$('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $('#btnPlay').textContent = S.playing ? t('pause') : t('play');
}

/* ---------- formatting ---------- */
const fmtCache = {};
function parts(ms) {
  let f = fmtCache[S.tz];
  if (!f) {
    f = fmtCache[S.tz] = new Intl.DateTimeFormat('en-CA', {
      timeZone: S.tz, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });
  }
  const o = {};
  for (const p of f.formatToParts(ms)) o[p.type] = p.value;
  return o;
}
const fmtDateTime = (ms) => { const p = parts(ms); return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`; };
const price = (v) => (v == null ? '-' : v.toFixed(S.st ? S.st.digits : 5));
function money(v, signed) {
  if (v == null) return '-';
  const d = S.st && S.st.currency === 'JPY' ? 0 : 2;
  const s = Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  return (v < 0 ? '−' : signed && v > 0 ? '+' : '') + s;
}
const num = (v) => (v == null ? '-' : v.toLocaleString());
const pnlClass = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
const reasonText = (r) => (r === 'sl' || r === 'tp' ? t(r + '_') : t(r));
const sideText = (s) => (s === 'buy' ? t('buySide') : t('sellSide'));
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function duration(sec) {
  if (sec == null) return '-';
  const s = Math.round(sec);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return h ? `${h}h ${m}m` : m ? `${m}m ${r}s` : `${r}s`;
}

/* ---------- api ---------- */
async function api(path, body) {
  const opt = body === undefined ? {} :
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  const res = await fetch(path, opt);
  const data = await res.json().catch(() => ({ error: res.statusText }));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}
const tfBody = () => ({ tf: S.tf, since: S.since });
let toastTimer = null;
function toast(msg) {
  const el = $('#toast');
  el.textContent = msg; el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4500);
}

/* ---------- state ---------- */
function mergeCandles(c) {
  if (!c || c.tf !== S.tf) return;
  if (c.full) {
    S.candles = c.data;
  } else {
    for (const r of c.data) {
      const last = S.candles[S.candles.length - 1];
      if (last && last[0] === r[0]) S.candles[S.candles.length - 1] = r;
      else if (!last || r[0] > last[0]) S.candles.push(r);
    }
  }
  S.since = S.candles.length ? S.candles[S.candles.length - 1][0] : null;
}
function eventText(ev) {
  const base = { ref: ev.ref, price: price(ev.price), units: num(ev.units), note: ev.note };
  switch (ev.kind) {
    case 'open': return t('evOpen', base);
    case 'close': return t('evClose', { ...base, reason: reasonText(ev.note) });
    case 'pending': return t('evPending', base);
    case 'cancel': return t('evCancel', base);
    case 'rejected': return t('evRejected', base);
    default: return t('evModify', base);
  }
}
function apply(st) {
  S.st = st;
  mergeCandles(st.candles);
  let stop = false;
  for (const ev of st.events || []) {
    const text = eventText(ev);
    S.log.unshift({ time: ev.time, text });
    if (ev.kind === 'close' || ev.kind === 'rejected') { toast(text); stop = true; }
  }
  if (S.log.length > 300) S.log.length = 300;
  render();
  if (S.playing && ((stop && $('#pauseOnClose').checked) || st.at_end)) {
    pause();
    if (st.at_end) toast(t('endOfData'));
  }
}
async function refresh() {
  apply(await api(`/api/state?tf=${S.tf}` + (S.since ? `&since=${S.since}` : '')));
}

/* ---------- rendering ---------- */
function render() {
  const st = S.st;
  if (!st) return;
  $('#pairLabel').textContent = `${st.symbol.slice(0, 3)}/${st.symbol.slice(3)}`;
  const p = parts(st.now);
  $('#clockDate').textContent = `${p.year}-${p.month}-${p.day}`;
  $('#clockTime').textContent = `${p.hour}:${p.minute}:${p.second}`;
  $('#clockTz').textContent = S.tz === 'UTC' ? 'UTC' : $('#tz').selectedOptions[0].textContent;
  renderTicket();
  renderAccount();
  renderTabs();
  scheduleDraw();
}
function renderTicket() {
  const st = S.st, q = st.quote;
  const k = S.kind;
  $('#sellLabel').textContent = k === 'market' ? t('sell') : t(k === 'limit' ? 'sellLimit' : 'sellStop');
  $('#buyLabel').textContent = k === 'market' ? t('buy') : t(k === 'limit' ? 'buyLimit' : 'buyStop');
  $('#sellPrice').textContent = q ? price(q.bid) : '-';
  $('#buyPrice').textContent = q ? price(q.ask) : '-';
  $('#btnSell').disabled = $('#btnBuy').disabled = !q;
  const units = parseFloat($('#tUnits').value) || 0;
  const need = units * st.margin_per_unit;
  const line = $('#marginLine');
  line.textContent = t('marginNeed', { m: `${money(need)} ${st.currency}`, f: `${money(st.account.free_margin)} ${st.currency}` });
  line.classList.toggle('bad', need > st.account.free_margin);
}
function renderAccount() {
  const a = S.st.account;
  $('#aBalance').textContent = money(a.balance);
  $('#aEquity').textContent = money(a.equity);
  const fl = $('#aFloating');
  fl.textContent = money(a.floating, true);
  fl.className = pnlClass(a.floating);
  $('#aUsed').textContent = money(a.used_margin);
  $('#aFree').textContent = money(a.free_margin);
  $('#aLevel').textContent = a.margin_level == null ? '-' : `${(a.margin_level * 100).toFixed(0)}%`;
}
function table(cols, rows) {
  return `<table><thead><tr>${cols.map((c, i) => `<th${i === 0 ? '' : ''}>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>`;
}
function renderTabs() {
  const st = S.st;
  $('#cPositions').textContent = st.positions.length || '';
  $('#cOrders').textContent = st.orders.length || '';
  $('#cHistory').textContent = st.trades.length || '';
  renderPositions();
  renderOrders();
  renderHistory();
  if (S.tab === 'log') renderLog();
}
function renderPositions() {
  const st = S.st, box = $('#tab-positions');
  const key = st.positions.map((p) => [p.id, p.units, p.sl, p.tp].join(':')).join('|') + S.lang;
  if (key !== S.posKey && !box.contains(document.activeElement) || (key !== S.posKey && !st.positions.length)) {
    S.posKey = key;
    if (!st.positions.length) { box.innerHTML = `<p class="empty">${esc(t('emptyPositions'))}</p>`; return; }
    const rows = st.positions.map((p) => `<tr data-id="${p.id}">
      <td>${p.id}</td><td class="l ${p.side === 'buy' ? 'pos' : 'neg'}">${esc(sideText(p.side))}</td>
      <td>${num(p.units)}</td><td>${price(p.open_price)}</td>
      <td><input data-k="sl" value="${p.sl ?? ''}" aria-label="${esc(t('colSl'))}"></td>
      <td><input data-k="tp" value="${p.tp ?? ''}" aria-label="${esc(t('colTp'))}"></td>
      <td class="pnl"></td><td><button data-close="${p.id}">${esc(t('close'))}</button></td></tr>`).join('');
    box.innerHTML = `<div style="margin-bottom:6px"><button id="btnCloseAll">${esc(t('closeAll'))}</button></div>` +
      table([t('colId'), t('colSide'), t('colUnits'), t('colOpen'), t('colSl'), t('colTp'), t('colPnl'), ''], rows);
  }
  for (const p of st.positions) {
    const cell = $(`tr[data-id="${p.id}"] .pnl`, box);
    if (cell) { cell.textContent = money(p.pnl, true); cell.className = 'pnl ' + pnlClass(p.pnl); }
  }
}
function renderOrders() {
  const st = S.st, box = $('#tab-orders');
  const key = st.orders.map((o) => o.id).join('|') + S.lang;
  if (key === S.ordKey) return;
  S.ordKey = key;
  if (!st.orders.length) { box.innerHTML = `<p class="empty">${esc(t('emptyOrders'))}</p>`; return; }
  const rows = st.orders.map((o) => `<tr><td>${o.id}</td><td class="l">${esc(sideText(o.side))}</td>
    <td class="l">${esc(t(o.kind))}</td><td>${num(o.units)}</td><td>${o.price == null ? '-' : price(o.price)}</td>
    <td>${o.sl == null ? '-' : price(o.sl)}</td><td>${o.tp == null ? '-' : price(o.tp)}</td>
    <td><button data-cancel="${o.id}">${esc(t('cancelOrder'))}</button></td></tr>`).join('');
  box.innerHTML = table([t('colId'), t('colSide'), t('colType'), t('colUnits'), t('colPrice'), t('colSl'), t('colTp'), ''], rows);
}
function renderHistory() {
  const st = S.st, box = $('#tab-history');
  const key = st.trades.length + S.lang + S.tz;
  if (key === S.histKey) return;
  S.histKey = key;
  if (!st.trades.length) { box.innerHTML = `<p class="empty">${esc(t('emptyHistory'))}</p>`; return; }
  const rows = [...st.trades].reverse().map((r) => `<tr><td>${r.id}</td>
    <td class="l ${r.side === 'buy' ? 'pos' : 'neg'}">${esc(sideText(r.side))}</td><td>${num(r.units)}</td>
    <td>${fmtDateTime(r.open_time)}</td><td>${price(r.open_price)}</td>
    <td>${fmtDateTime(r.close_time)}</td><td>${price(r.close_price)}</td>
    <td class="l">${esc(reasonText(r.reason))}</td><td class="${pnlClass(r.pnl)}">${money(r.pnl, true)}</td></tr>`).join('');
  box.innerHTML = table([t('colId'), t('colSide'), t('colUnits'), t('colOpened'), t('colOpen'), t('colClosed'),
    t('colExit'), t('colReason'), t('colPnl')], rows);
}
function renderLog() {
  const box = $('#tab-log');
  box.innerHTML = S.log.length ? S.log.map((e) =>
    `<div class="log-row"><time>${fmtDateTime(e.time)}</time><span>${esc(e.text)}</span></div>`).join('')
    : `<p class="empty">${esc(t('emptyLog'))}</p>`;
}

/* ---------- report ---------- */
async function loadReport() {
  try { renderReport(await api('/api/report')); } catch (e) { toast(e.message); }
}
function renderReport(r) {
  const s = r.stats, dd = r.max_drawdown, cur = r.currency;
  const m = (v, signed) => `${money(v, signed)} ${cur}`;
  const rows = [
    [t('rReturn'), `${r.return_pct >= 0 ? '+' : '−'}${Math.abs(r.return_pct).toFixed(2)}%`],
    [t('rEquity'), m(r.final_equity)],
    [t('rDd'), `${m(dd.abs)} (${dd.pct.toFixed(2)}%)`],
    [t('rTrades'), s.trades],
    [t('rWin'), s.win_rate == null ? '-' : `${(s.win_rate * 100).toFixed(0)}%`],
    [t('rPf'), s.profit_factor == null ? (s.wins ? '∞' : '-') : s.profit_factor.toFixed(2)],
    [t('rTotal'), m(s.total_pnl, true)],
    [t('rAvgWin'), s.avg_win == null ? '-' : m(s.avg_win, true)],
    [t('rAvgLoss'), s.avg_loss == null ? '-' : m(s.avg_loss, true)],
    [t('rBest'), s.best == null ? '-' : m(s.best, true)],
    [t('rWorst'), s.worst == null ? '-' : m(s.worst, true)],
    [t('rHold'), duration(s.avg_holding)],
    [t('rStopouts'), r.stop_outs],
    [t('rRejected'), r.rejected_orders],
  ];
  $('#reportStats').innerHTML = rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('');
  drawEquity(r);
}
function drawEquity(r) {
  const cv = $('#eq'), w = cv.clientWidth, h = cv.clientHeight;
  if (!w || !h) return;
  const dpr = window.devicePixelRatio || 1;
  cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const css = getComputedStyle(document.documentElement), col = (n) => css.getPropertyValue(n).trim();
  const data = r.equity_curve;
  ctx.font = '11px ' + css.getPropertyValue('--font');
  if (data.length < 2) {
    ctx.fillStyle = col('--ink-soft'); ctx.fillText(t('equityEmpty'), 8, 20); return;
  }
  const xs = data.map((d) => d[0]), ys = data.map((d) => d[1]);
  let lo = Math.min(...ys, r.initial_balance), hi = Math.max(...ys, r.initial_balance);
  if (hi === lo) { hi += 1; lo -= 1; }
  const padL = 62, padR = 10, padT = 10, padB = 18;
  const X = (x) => padL + (x - xs[0]) / (xs[xs.length - 1] - xs[0]) * (w - padL - padR);
  const Y = (y) => padT + (hi - y) / (hi - lo) * (h - padT - padB);
  ctx.strokeStyle = col('--line-soft'); ctx.fillStyle = col('--ink-soft'); ctx.lineWidth = 1;
  for (const v of [lo, (lo + hi) / 2, hi]) {
    ctx.beginPath(); ctx.moveTo(padL, Y(v) + .5); ctx.lineTo(w - padR, Y(v) + .5); ctx.stroke();
    ctx.fillText(money(v), 4, Y(v) + 4);
  }
  ctx.setLineDash([4, 3]); ctx.strokeStyle = col('--ink-soft');
  ctx.beginPath(); ctx.moveTo(padL, Y(r.initial_balance)); ctx.lineTo(w - padR, Y(r.initial_balance)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.strokeStyle = col('--steel'); ctx.lineWidth = 1.6; ctx.beginPath();
  data.forEach((d, i) => (i ? ctx.lineTo(X(d[0]), Y(d[1])) : ctx.moveTo(X(d[0]), Y(d[1]))));
  ctx.stroke();
  const dd = r.max_drawdown;
  if (dd.peak_time != null && dd.abs > 0) {
    ctx.strokeStyle = col('--down'); ctx.lineWidth = 2.4; ctx.beginPath();
    let started = false;  // redraw the equity between the peak and the trough in red
    for (const d of data) {
      if (d[0] < dd.peak_time || d[0] > dd.trough_time) continue;
      if (started) ctx.lineTo(X(d[0]), Y(d[1])); else { ctx.moveTo(X(d[0]), Y(d[1])); started = true; }
    }
    ctx.stroke();
    ctx.fillStyle = col('--down');
    for (const [ms, v] of [[dd.peak_time, dd.peak], [dd.trough_time, dd.trough]]) {
      ctx.beginPath(); ctx.arc(X(ms), Y(v), 3, 0, 6.3); ctx.fill();
    }
  }
  ctx.fillStyle = col('--ink-soft');
  ctx.fillText(fmtDateTime(xs[0]), padL, h - 4);
  const end = fmtDateTime(xs[xs.length - 1]);
  ctx.fillText(end, w - padR - ctx.measureText(end).width, h - 4);
}

/* ---------- chart ---------- */
let drawQueued = false;
function scheduleDraw() {
  if (drawQueued) return;
  drawQueued = true;
  requestAnimationFrame(() => { drawQueued = false; drawChart(); });
}
function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
}
function drawChart() {
  const cv = $('#chart'), wrap = cv.parentElement;
  const w = wrap.clientWidth, h = wrap.clientHeight;
  if (!w || !h || !S.st) return;
  const dpr = window.devicePixelRatio || 1;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    cv.style.width = w + 'px'; cv.style.height = h + 'px';
  }
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const css = getComputedStyle(document.documentElement), col = (n) => css.getPropertyValue(n).trim();
  const st = S.st, C = S.candles, n = C.length;
  ctx.font = '11px ' + css.getPropertyValue('--font');
  if (!n) {
    ctx.fillStyle = col('--ink-soft'); ctx.fillText(t('waiting'), 16, 28); return;
  }
  const padR = 78, padB = 24, padT = 10, rightPad = 56;
  const plotW = w - padR, plotH = h - padB - padT, bw = view.barW;
  view.off = Math.max(0, Math.min(n - 1, view.off));
  const xOf = (i) => plotW - rightPad - (n - 1 - view.off - i + 0.5) * bw;
  const idxAt = (x) => n - 1 - view.off + 0.5 - (plotW - rightPad - x) / bw;
  const lo = Math.max(0, Math.floor(idxAt(0)) - 1);
  const hi = Math.min(n - 1, Math.ceil(idxAt(plotW)) + 1);

  let pMin = Infinity, pMax = -Infinity;
  for (let i = lo; i <= hi; i++) { pMin = Math.min(pMin, C[i][3]); pMax = Math.max(pMax, C[i][2]); }
  if (hi === n - 1 && st.quote) { pMin = Math.min(pMin, st.quote.bid); pMax = Math.max(pMax, st.quote.ask); }
  if (!(pMax > pMin)) { pMax += st.pip * 5; pMin -= st.pip * 5; }
  const pad = (pMax - pMin) * 0.08; pMin -= pad; pMax += pad;
  const yOf = (p) => padT + (pMax - p) / (pMax - pMin) * plotH;

  // price grid
  const step = niceStep((pMax - pMin) / 7);
  ctx.textBaseline = 'middle';
  for (let p = Math.ceil(pMin / step) * step; p < pMax; p += step) {
    const y = Math.round(yOf(p)) + 0.5;
    ctx.strokeStyle = col('--line-soft'); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(plotW, y); ctx.stroke();
    ctx.fillStyle = col('--ink-soft'); ctx.fillText(p.toFixed(st.digits), plotW + 8, y);
  }
  // time grid
  const tfSec = TF_SEC[S.tf];
  const steps = [60, 120, 300, 600, 900, 1800, 3600, 7200, 14400, 21600, 43200, 86400, 172800, 604800];
  const stepSec = steps.find((s) => s >= tfSec && (s / tfSec) * bw >= 84) || 604800;
  ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'center';
  for (let i = lo; i <= hi; i++) {
    if ((C[i][0] / 1000) % stepSec !== 0) continue;
    const x = Math.round(xOf(i)) + 0.5;
    ctx.strokeStyle = col('--line-soft');
    ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, padT + plotH); ctx.stroke();
    const p = parts(C[i][0]);
    ctx.fillStyle = col('--ink-soft');
    ctx.fillText(p.hour === '00' && p.minute === '00' ? `${p.month}-${p.day}` : `${p.hour}:${p.minute}`, x, h - 8);
  }
  ctx.textAlign = 'left';

  // candles
  const bodyW = Math.max(1, Math.floor(bw * 0.7));
  for (let i = lo; i <= hi; i++) {
    const [, o, hgh, low, c] = C[i];
    const x = Math.round(xOf(i)), color = c >= o ? col('--up') : col('--down');
    ctx.strokeStyle = color; ctx.fillStyle = color;
    ctx.beginPath(); ctx.moveTo(x + 0.5, yOf(hgh)); ctx.lineTo(x + 0.5, yOf(low)); ctx.stroke();
    const y1 = yOf(Math.max(o, c)), y2 = yOf(Math.min(o, c));
    ctx.fillRect(x - Math.floor(bodyW / 2), y1, bodyW, Math.max(1, y2 - y1));
  }

  // overlays
  const tag = (p, color, text) => {
    const y = yOf(p);
    if (y < padT || y > padT + plotH) return;
    ctx.fillStyle = color; ctx.fillRect(plotW + 2, y - 8, padR - 4, 16);
    ctx.fillStyle = '#fff'; ctx.textBaseline = 'middle'; ctx.fillText(text, plotW + 6, y + 0.5);
    ctx.textBaseline = 'alphabetic';
  };
  const line = (p, color, dash, text) => {
    const y = yOf(p);
    if (y < padT || y > padT + plotH) return;
    ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.setLineDash(dash);
    ctx.beginPath(); ctx.moveTo(0, Math.round(y) + 0.5); ctx.lineTo(plotW, Math.round(y) + 0.5); ctx.stroke();
    ctx.setLineDash([]);
    if (text) { ctx.fillStyle = color; ctx.fillText(text, 8, y - 4); }
  };
  const levelLine = (p, color, label) => {
    const y = yOf(p);
    if (y >= padT && y <= padT + plotH) { line(p, color, [6, 3], label); tag(p, color, price(p)); return; }
    const up = y < padT, cy = up ? padT + 9 : padT + plotH - 9;  // off screen: pin a marker to the edge
    ctx.fillStyle = color; ctx.fillRect(plotW + 2, cy - 8, padR - 4, 16);
    ctx.fillStyle = '#fff'; ctx.textBaseline = 'middle';
    ctx.fillText((up ? '▲ ' : '▼ ') + price(p), plotW + 6, cy + 0.5);
    ctx.textBaseline = 'alphabetic';
  };
  if (st.quote) {
    line(st.quote.bid, col('--steel'), [], null); tag(st.quote.bid, col('--steel'), price(st.quote.bid));
    line(st.quote.ask, col('--ink-soft'), [4, 3], null); tag(st.quote.ask, col('--ink-soft'), price(st.quote.ask));
  }
  for (const p of st.positions) {
    const c = p.pnl >= 0 ? col('--up') : col('--down');
    line(p.open_price, c, [2, 2], `${sideText(p.side)} ${num(p.units)}  ${money(p.pnl, true)}`);
    if (p.sl != null) levelLine(p.sl, col('--down'), `${t('sl')} #${p.id}`);
    if (p.tp != null) levelLine(p.tp, col('--up'), `${t('tp')} #${p.id}`);
  }
  for (const o of st.orders) {
    if (o.price != null) line(o.price, col('--warn'), [3, 3], `#${o.id} ${t(o.kind)} ${sideText(o.side)}`);
  }

  // crosshair + readout
  const ohlc = $('#ohlc');
  if (view.mx != null && view.mx < plotW && view.my > padT && view.my < padT + plotH) {
    ctx.strokeStyle = col('--ink-soft'); ctx.setLineDash([2, 3]);
    ctx.beginPath(); ctx.moveTo(view.mx + 0.5, padT); ctx.lineTo(view.mx + 0.5, padT + plotH);
    ctx.moveTo(0, view.my + 0.5); ctx.lineTo(plotW, view.my + 0.5); ctx.stroke(); ctx.setLineDash([]);
    tag(pMax - (view.my - padT) / plotH * (pMax - pMin), col('--ink'), (pMax - (view.my - padT) / plotH * (pMax - pMin)).toFixed(st.digits));
    const i = Math.round(idxAt(view.mx));
    if (i >= 0 && i < n) {
      const [tm, o, hg, lw, c, v] = C[i];
      ohlc.textContent = `${fmtDateTime(tm)}  O ${price(o)}  H ${price(hg)}  L ${price(lw)}  C ${price(c)}  (${v} ticks)`;
    }
  } else { ohlc.textContent = ''; }
}

const chart = $('#chart');
chart.addEventListener('pointerdown', (e) => {
  chart.setPointerCapture(e.pointerId);
  view.drag = { x: e.clientX, off: view.off };
});
chart.addEventListener('pointermove', (e) => {
  const r = chart.getBoundingClientRect();
  view.mx = e.clientX - r.left; view.my = e.clientY - r.top;
  if (view.drag) view.off = view.drag.off + (e.clientX - view.drag.x) / view.barW;
  scheduleDraw();
});
chart.addEventListener('pointerup', () => { view.drag = null; });
chart.addEventListener('pointerleave', () => { view.mx = null; scheduleDraw(); });
chart.addEventListener('dblclick', () => { view.off = 0; scheduleDraw(); });
chart.addEventListener('wheel', (e) => {
  e.preventDefault();
  const n = S.candles.length, r = chart.getBoundingClientRect(), mx = e.clientX - r.left;
  const plotW = r.width - 78, rightPad = 56, old = view.barW;
  const i = n - 1 - view.off + 0.5 - (plotW - rightPad - mx) / old;
  view.barW = Math.max(2, Math.min(48, old * Math.pow(1.0015, -e.deltaY)));
  view.off = n - 1 + 0.5 - (plotW - rightPad - mx) / view.barW - i;
  scheduleDraw();
}, { passive: false });
new ResizeObserver(scheduleDraw).observe($('.chart-wrap'));

/* ---------- ticket ---------- */
function level(inputId, which, side, ref) {
  const raw = $('#' + inputId).value.trim();
  if (raw === '') return null;
  const v = parseFloat(raw);
  if (Number.isNaN(v)) throw new Error(t('errNumber'));
  if ($('#' + inputId + 'Mode').value === 'price') return v;
  const level = ref + ((which === 'sl') === (side === 'buy') ? -1 : 1) * v * S.st.pip;
  return Number(level.toFixed(S.st.digits));
}
function showTicketError(msg) {
  const el = $('#ticketError');
  el.textContent = msg; el.hidden = !msg;
}
async function placeOrder(side) {
  showTicketError('');
  try {
    const st = S.st;
    const units = parseFloat($('#tUnits').value);
    if (!(units > 0)) throw new Error(t('errUnits'));
    let px = null;
    if (S.kind !== 'market') {
      px = parseFloat($('#tPrice').value);
      if (Number.isNaN(px)) throw new Error(t('errPrice'));
    }
    const ref = px !== null ? px : (side === 'buy' ? st.quote.ask : st.quote.bid);
    const sl = level('tSl', 'sl', side, ref), tp = level('tTp', 'tp', side, ref);
    apply(await api('/api/order', { side, units, kind: S.kind, price: px, sl, tp, ...tfBody() }));
  } catch (e) { showTicketError(e.message); }
}

/* ---------- transport ---------- */
function setPlaying(on) {
  S.playing = on;
  $('#btnPlay').textContent = on ? t('pause') : t('play');
}
function pause() { setPlaying(false); }
async function playLoop() {
  if (!S.playing) return;
  const now = performance.now();
  const dt = Math.min((now - S.last) / 1000, 0.5);
  S.last = now;
  try {
    apply(await api('/api/advance', { wall_seconds: dt, speed: parseFloat($('#speed').value), ...tfBody() }));
  } catch (e) { pause(); toast(e.message); }
  if (S.playing) setTimeout(playLoop, 80);
}
function togglePlay() {
  if (!S.st || S.st.at_end) return;
  if (S.playing) { pause(); return; }
  setPlaying(true); S.last = performance.now(); playLoop();
}
async function step(body) {
  pause();
  try { apply(await api('/api/step', { ...body, ...tfBody() })); } catch (e) { toast(e.message); }
}
function resetChartState() {
  S.candles = []; S.since = null; S.posKey = ''; S.ordKey = ''; S.histKey = '';
  view.off = 0;
}

/* ---------- own data files ---------- */
const utcStr = (ms) => new Date(ms).toISOString().slice(0, 16).replace('T', ' ');
function renderDatasets() {
  const box = $('#datasetList'), list = S.datasets || [];
  if (!list.length) { box.innerHTML = `<span class="hint">${esc(t('datasetsEmpty'))}</span>`; return; }
  box.innerHTML = list.map((d, i) =>
    `<button type="button" class="chip" data-ds="${i}">${esc(d.symbol.slice(0, 3) + '/' + d.symbol.slice(3))}
     ${utcStr(d.first)} → ${utcStr(d.last)} (${d.ticks.toLocaleString()})</button>`).join('');
}
async function loadDatasets() {
  try { S.datasets = (await api('/api/datasets')).datasets; renderDatasets(); } catch { /* ignore */ }
}
function useDataset(d) {
  const end = Math.min(Math.ceil((d.last + 1) / 60000) * 60000, d.first + 7 * 86400000);
  $('#fSymbol').value = d.symbol.slice(0, 3) + '/' + d.symbol.slice(3);
  $('#fStart').value = utcStr(d.first); $('#fEnd').value = utcStr(end);
  $('#fUseImported').checked = true;
}
async function importFile() {
  const file = $('#fFile').files[0], status = $('#importStatus');
  if (!file) { status.textContent = t('errFile'); return; }
  status.textContent = t('importing');
  $('#btnImport').disabled = true;
  try {
    const url = `/api/import?symbol=${encodeURIComponent($('#fSymbol').value)}&timezone=${encodeURIComponent($('#fFileTz').value)}`;
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: file });
    const data = await res.json().catch(() => ({ error: res.statusText }));
    if (!res.ok) throw new Error(data.error);
    status.textContent = t('importedOk', { n: data.ticks.toLocaleString(), a: utcStr(data.first), b: utcStr(data.last) });
    await loadDatasets();
    useDataset({ symbol: data.symbol, first: data.first, last: data.last });
  } catch (e) { status.textContent = e.message; } finally { $('#btnImport').disabled = false; }
}

/* ---------- setup ---------- */
function utcField(id) {
  const v = $(id).value.trim();
  if (!/^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$/.test(v)) throw new Error(t('errDate'));
  return v;
}
async function startSession(ev) {
  ev.preventDefault();
  const err = $('#setupError'), status = $('#setupStatus');
  err.hidden = true;
  let timer = null;
  try {
    const body = {
      symbol: $('#fSymbol').value, start: utcField('#fStart'), end: utcField('#fEnd'),
      currency: $('#fCurrency').value, balance: $('#fBalance').value, leverage: $('#fLeverage').value,
      stop_out_pct: $('#fStopOut').value, slippage_pips: $('#fSlip').value, extra_spread_pips: $('#fSpread').value,
      latency_s: $('#fLatency').value, fixed_rate: $('#fFixed').value,
      use_imported: $('#fUseImported').checked,
    };
    $('#btnStart').disabled = true;
    status.textContent = t('loading');
    timer = setInterval(async () => {
      try { const s = await api('/api/status'); if (s.message) status.textContent = s.message; } catch { /* ignore */ }
    }, 400);
    const st = await api('/api/start', body);
    resetChartState();
    S.log = []; setPlaying(false);
    $('#setup').hidden = true; $('#workspace').hidden = false;
    $('#transport').hidden = false; $('#clock').hidden = false;
    S.st = null; apply(st);
  } catch (e) {
    err.textContent = e.message; err.hidden = false;
    if (/own data files|imported/i.test(e.message)) $('#ownData').open = true;
  } finally {
    clearInterval(timer);
    $('#btnStart').disabled = false; status.textContent = '';
  }
}

/* ---------- wiring ---------- */
function init() {
  $('#lang').value = S.lang; $('#tz').value = S.tz;
  applyI18n();
  $('#lang').addEventListener('change', (e) => {
    S.lang = e.target.value; store.set('fxtm.lang', S.lang);
    S.posKey = S.ordKey = S.histKey = ''; applyI18n(); if (S.st) render();
  });
  $('#tz').addEventListener('change', (e) => {
    S.tz = e.target.value; store.set('fxtm.tz', S.tz); S.histKey = ''; if (S.st) render();
  });
  $('#setupForm').addEventListener('submit', startSession);
  $('#btnImport').addEventListener('click', importFile);
  $('#datasetList').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-ds]');
    if (b) useDataset(S.datasets[Number(b.dataset.ds)]);
  });
  loadDatasets();
  $$('.chip').forEach((b) => b.addEventListener('click', () => {
    $('#fSymbol').value = b.dataset.sym; $('#fStart').value = b.dataset.start; $('#fEnd').value = b.dataset.end;
  }));
  $('#btnPlay').addEventListener('click', togglePlay);
  $('#btnTick').addEventListener('click', () => step({ mode: 'tick' }));
  $('#btnMin').addEventListener('click', () => step({ mode: 'seconds', seconds: 60 }));
  $('#btnHour').addEventListener('click', () => step({ mode: 'seconds', seconds: 3600 }));
  $('#btnRestart').addEventListener('click', async () => {
    if (!confirm(t('confirmRestart'))) return;
    pause(); resetChartState(); S.log = [];
    try { S.st = null; apply(await api('/api/restart', {})); } catch (e) { toast(e.message); }
  });
  const dlg = $('#jumpDialog');
  $('#btnJump').addEventListener('click', () => { pause(); dlg.showModal(); $('#jumpTo').focus(); });
  $('#jumpCancel').addEventListener('click', () => dlg.close());
  $('#jumpForm').addEventListener('submit', async () => {
    try {
      apply(await api('/api/jump', { to: utcField('#jumpTo'), ...tfBody() }));
    } catch (e) { toast(e.message); }
  });
  $('#tfSeg').addEventListener('click', async (e) => {
    const b = e.target.closest('button[data-tf]');
    if (!b) return;
    $$('#tfSeg button').forEach((x) => x.classList.toggle('on', x === b));
    S.tf = b.dataset.tf; S.candles = []; S.since = null; view.off = 0;
    try { await refresh(); } catch (err) { toast(err.message); }
  });
  $('#kindSeg').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-kind]');
    if (!b) return;
    $$('#kindSeg button').forEach((x) => x.classList.toggle('on', x === b));
    S.kind = b.dataset.kind;
    $('#priceRow').hidden = S.kind === 'market';
    if (S.st) renderTicket();
  });
  $('#quickUnits').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-u]');
    if (b) { $('#tUnits').value = b.dataset.u; if (S.st) renderTicket(); }
  });
  $('#tUnits').addEventListener('input', () => { if (S.st) renderTicket(); });
  $('#btnSell').addEventListener('click', () => placeOrder('sell'));
  $('#btnBuy').addEventListener('click', () => placeOrder('buy'));
  $('#tablist').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-tab]');
    if (!b) return;
    S.tab = b.dataset.tab;
    $$('#tablist button').forEach((x) => x.classList.toggle('on', x === b));
    $$('.tabbody').forEach((x) => { x.hidden = x.id !== 'tab-' + S.tab; });
    if (S.tab === 'report') loadReport();
    if (S.tab === 'log') renderLog();
  });
  $('#btnReport').addEventListener('click', loadReport);
  $('#btnSave').addEventListener('click', async () => {
    try {
      const r = await api('/api/save', {});
      $('#saveStatus').textContent = t('saved', { id: r.run_id, path: r.path });
    } catch (e) { toast(e.message); }
  });
  const posBox = $('#tab-positions');
  posBox.addEventListener('click', async (e) => {
    try {
      if (e.target.dataset.close) apply(await api('/api/close', { id: e.target.dataset.close, ...tfBody() }));
      if (e.target.id === 'btnCloseAll') apply(await api('/api/close', { all: true, ...tfBody() }));
    } catch (err) { toast(err.message); }
  });
  posBox.addEventListener('change', async (e) => {
    const row = e.target.closest('tr[data-id]');
    if (!row || !e.target.dataset.k) return;
    try {
      apply(await api('/api/modify', { id: row.dataset.id, [e.target.dataset.k]: e.target.value, ...tfBody() }));
    } catch (err) { toast(err.message); S.posKey = ''; if (S.st) renderPositions(); }
  });
  $('#tab-orders').addEventListener('click', async (e) => {
    if (!e.target.dataset.cancel) return;
    try { apply(await api('/api/cancel', { id: e.target.dataset.cancel, ...tfBody() })); } catch (err) { toast(err.message); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && !/INPUT|SELECT|TEXTAREA|BUTTON/.test(document.activeElement.tagName)
        && !$('#workspace').hidden) { e.preventDefault(); togglePlay(); }
  });
  window.addEventListener('resize', scheduleDraw);
  // resume a session that is already running on the server (e.g. after a page reload)
  api('/api/status').then((s) => {
    if (!s.ready) return;
    $('#setup').hidden = true; $('#workspace').hidden = false;
    $('#transport').hidden = false; $('#clock').hidden = false;
    return refresh();
  }).catch(() => {});
}
init();
})();
