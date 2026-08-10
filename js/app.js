// ============================================================
// 吱吱店長 萬能房產計算機
// ============================================================
'use strict';

const $ = (id) => document.getElementById(id);
const on = (el, ev, fn) => { if (el) el.addEventListener(ev, fn); };

function fmt2(n) {
  return Number.isFinite(n) ? n.toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
}
function fmtInt(n) {
  return Number.isFinite(n) ? Math.round(n).toLocaleString('zh-TW') : '—';
}
function fmtMoney(n) {
  return Number.isFinite(n) ? '$' + Math.round(n).toLocaleString('zh-TW') : '$—';
}
function numOf(id) {
  const el = $(id);
  if (!el) return 0;
  const v = parseFloat(el.value);
  return Number.isFinite(v) ? v : 0;
}
function rawOf(id) {
  const el = $(id);
  return el ? el.value.trim() : '';
}

// ------------------------------------------------------------
// Tab switching
// ------------------------------------------------------------
function initTabs() {
  const btns = document.querySelectorAll('.tab-btn');
  btns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.tab;
      document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('active', b === btn));
      document.querySelectorAll('.panel').forEach((p) => p.classList.toggle('active', p.id === 'panel-' + target));
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });
}
function goToTab(name) {
  const btn = document.querySelector(`.tab-btn[data-tab="${name}"]`);
  if (btn) btn.click();
}

// ------------------------------------------------------------
// Choice-button (segmented) helper
// ------------------------------------------------------------
function initChoiceGroup(groupSelector, onChange) {
  const group = document.querySelector(groupSelector);
  if (!group) return { get: () => null };
  let current = group.querySelector('.choice-btn.active') || group.querySelector('.choice-btn');
  if (current) current.classList.add('active');
  group.querySelectorAll('.choice-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      group.querySelectorAll('.choice-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      current = btn;
      onChange(btn);
    });
  });
  return { get: () => current };
}

// ------------------------------------------------------------
// ROC date select builders
// ------------------------------------------------------------
function fillYearSelect(el, placeholder) {
  if (!el) return;
  const opts = [`<option value="">${placeholder}</option>`];
  for (let y = 130; y >= 60; y--) opts.push(`<option value="${y}">${y}</option>`);
  el.innerHTML = opts.join('');
}
function fillMonthSelect(el) {
  if (!el) return;
  const opts = ['<option value="">月</option>'];
  for (let m = 1; m <= 12; m++) opts.push(`<option value="${m}">${m}</option>`);
  el.innerHTML = opts.join('');
}
function fillDaySelect(el) {
  if (!el) return;
  const opts = ['<option value="">日</option>'];
  for (let d = 1; d <= 31; d++) opts.push(`<option value="${d}">${d}</option>`);
  el.innerHTML = opts.join('');
}
function rocDateToGregorian(y, m, d) {
  if (!y || !m || !d) return null;
  const dt = new Date(Number(y) + 1911, Number(m) - 1, Number(d));
  return isNaN(dt.getTime()) ? null : dt;
}
function holdingRate(prevDate, currDate) {
  if (!prevDate || !currDate) return null;
  const days = Math.round((currDate - prevDate) / 86400000);
  if (days < 0) return null;
  if (days <= 730) return 0.45;
  if (days <= 1825) return 0.35;
  if (days <= 3650) return 0.20;
  return 0.15;
}

// ------------------------------------------------------------
// Tab 1: 房地合一
// ------------------------------------------------------------
function initHo() {
  let transferMode = 'default'; // default(3%上限30萬) | manual
  let periodRate = 0.45;

  initChoiceGroup('#ho-transfer-group', (btn) => {
    transferMode = btn.dataset.mode;
    $('ho-transfer-manual-wrap').style.display = transferMode === 'manual' ? 'block' : 'none';
    computeHo();
  });
  initChoiceGroup('#ho-period-group', (btn) => {
    periodRate = parseFloat(btn.dataset.rate);
    computeHo();
  });

  ['ho-price', 'ho-cost', 'ho-landgain', 'ho-acqfee', 'ho-transfer-manual'].forEach((id) => on($(id), 'input', computeHo));
  on($('ho-selfuse'), 'change', computeHo);

  function computeHo() {
    const price = numOf('ho-price');
    const cost = numOf('ho-cost');
    const landgain = numOf('ho-landgain');
    const acqfee = numOf('ho-acqfee');
    const selfUse = $('ho-selfuse').checked;

    const transferFee = transferMode === 'manual' ? numOf('ho-transfer-manual') : Math.min(price * 0.03, 30);
    $('ho-transfer-auto-note').textContent = `系統計算：${fmt2(Math.min(price * 0.03, 30))} 萬（成交價 3%，上限 30 萬）`;

    const hasPrice = rawOf('ho-price') !== '';
    const base = price - cost - landgain - acqfee - transferFee;

    let rate, tax;
    if (selfUse) {
      rate = null; // special
      tax = Math.max(0, base - 400) * 0.10;
    } else {
      rate = periodRate;
      tax = Math.max(0, base) * rate;
    }

    $('ho-result-tax').textContent = hasPrice ? fmtMoney(tax * 10000) : '$—';
    $('ho-result-base').textContent = hasPrice ? fmt2(base) : '—';
    $('ho-result-rate').textContent = hasPrice ? (selfUse ? '自用 10%（400萬以下免稅）' : (rate * 100).toFixed(0) + '%') : '—';
    $('ho-result-transfer').textContent = hasPrice ? fmt2(transferFee) : '—';
  }

  computeHo();
}

// ------------------------------------------------------------
// Tab 2: 購屋能力
// ------------------------------------------------------------
function initAff() {
  let dti = 0.33;
  let years = 30;

  initChoiceGroup('#aff-dti-group', (btn) => { dti = parseFloat(btn.dataset.rate); computeAff(); });
  initChoiceGroup('#aff-years-group', (btn) => { years = parseFloat(btn.dataset.years); computeAff(); });
  ['aff-income', 'aff-savings'].forEach((id) => on($(id), 'input', computeAff));

  function computeAff() {
    const income = numOf('aff-income');
    const savings = numOf('aff-savings');
    const hasIncome = rawOf('aff-income') !== '';

    const annualRate = 0.023;
    const r = annualRate / 12;
    const n = years * 12;
    const pmtMax = income * dti; // 萬/月

    let loanAmount = 0;
    if (r > 0) {
      loanAmount = pmtMax * (1 - Math.pow(1 + r, -n)) / r;
    } else {
      loanAmount = pmtMax * n;
    }
    const totalCap = loanAmount + savings;

    $('aff-result-total').textContent = hasIncome ? fmtMoney(totalCap * 10000) : '$—';
    $('aff-result-loan').textContent = hasIncome ? fmtMoney(loanAmount * 10000) : '$—';
    $('aff-result-monthly').textContent = hasIncome ? fmtMoney(pmtMax * 10000) : '$—';
  }

  computeAff();
}

// ------------------------------------------------------------
// Tab 3: 房貸試算
// ------------------------------------------------------------
function initLoan() {
  ['loan-amount', 'loan-rate', 'loan-years', 'loan-grace'].forEach((id) => on($(id), 'input', computeLoan));

  function computeLoan() {
    const amountWan = numOf('loan-amount');
    const M = amountWan * 10000;
    const annualRate = numOf('loan-rate');
    const years = numOf('loan-years') || 0;
    const grace = numOf('loan-grace') || 0;
    const hasAmount = rawOf('loan-amount') !== '' && amountWan > 0 && years > 0;

    const r = annualRate / 100 / 12;
    const n = Math.round(years * 12);
    const g = Math.min(Math.round(grace * 12), n);
    const remain = Math.max(n - g, 1);

    let graceMonthly = null;
    let mainMonthly = 0;
    let totalRepay = 0;

    if (hasAmount) {
      graceMonthly = g > 0 ? M * r : null;
      if (r > 0) {
        mainMonthly = M * r * Math.pow(1 + r, remain) / (Math.pow(1 + r, remain) - 1);
      } else {
        mainMonthly = M / remain;
      }
      totalRepay = (graceMonthly ? graceMonthly * g : 0) + mainMonthly * remain;
    }
    const totalInterest = hasAmount ? totalRepay - M : NaN;

    $('loan-result-monthly').textContent = hasAmount ? fmtMoney(mainMonthly) : '$—';
    $('loan-result-grace').textContent = hasAmount && graceMonthly ? fmtMoney(graceMonthly) : '$—';
    $('loan-result-interest').textContent = hasAmount ? fmtMoney(totalInterest) : '$—';
    $('loan-result-repay').textContent = hasAmount ? fmtMoney(totalRepay) : '$—';
  }

  computeLoan();
}

// ------------------------------------------------------------
// Tab 4: 買賣雜費
// ------------------------------------------------------------
function initMisc() {
  let role = 'buyer';
  initChoiceGroup('#misc-role-group', (btn) => {
    role = btn.dataset.role;
    $('misc-buyer-block').style.display = role === 'buyer' ? 'block' : 'none';
    $('misc-seller-block').style.display = role === 'seller' ? 'block' : 'none';
  });

  ['misc-price', 'misc-houseval', 'misc-landval', 'misc-sheets'].forEach((id) => on($(id), 'input', computeMisc));

  function computeMisc() {
    const houseVal = numOf('misc-houseval') * 10000;
    const landVal = numOf('misc-landval') * 10000;
    const sheets = numOf('misc-sheets') || 2;
    const hasInput = rawOf('misc-houseval') !== '' || rawOf('misc-landval') !== '';

    const deedTax = houseVal * 0.06;
    const stampTax = (houseVal + landVal) * 0.001;
    const regFee = (houseVal + landVal) * 0.001;
    const docFee = sheets * 80;
    const total = deedTax + stampTax + regFee + docFee;

    $('misc-fee-deed').textContent = hasInput ? fmtMoney(deedTax) : '$—';
    $('misc-fee-stamp').textContent = hasInput ? fmtMoney(stampTax) : '$—';
    $('misc-fee-reg').textContent = hasInput ? fmtMoney(regFee) : '$—';
    $('misc-fee-doc').textContent = fmtMoney(docFee);
    $('misc-result-total').textContent = hasInput ? fmtMoney(total) : '$—';
  }

  computeMisc();
}

// ------------------------------------------------------------
// Tab 5: 坪數換算
// ------------------------------------------------------------
function initConv() {
  const PING_TO_SQM = 3.30579;
  let updating = false;

  on($('conv-ping'), 'input', () => {
    if (updating) return;
    updating = true;
    const ping = numOf('conv-ping');
    $('conv-sqm').value = rawOf('conv-ping') === '' ? '' : (ping * PING_TO_SQM).toFixed(2);
    updating = false;
  });
  on($('conv-sqm'), 'input', () => {
    if (updating) return;
    updating = true;
    const sqm = numOf('conv-sqm');
    $('conv-ping').value = rawOf('conv-sqm') === '' ? '' : (sqm / PING_TO_SQM).toFixed(2);
    updating = false;
  });
}

// ------------------------------------------------------------
// Tab 6: 車位折算
// ------------------------------------------------------------
function initPark() {
  let updating = false;

  function recompute(source) {
    if (updating) return;
    updating = true;
    const ping = numOf('park-ping');
    if (source === 'unit') {
      const unit = numOf('park-unit');
      $('park-total').value = (ping > 0 && rawOf('park-unit') !== '') ? (unit * ping).toFixed(2) : $('park-total').value;
    } else if (source === 'total') {
      const total = numOf('park-total');
      $('park-unit').value = (ping > 0 && rawOf('park-total') !== '') ? (total / ping).toFixed(2) : $('park-unit').value;
    } else if (source === 'ping') {
      const unit = numOf('park-unit');
      const total = numOf('park-total');
      if (rawOf('park-unit') !== '' && ping > 0) {
        $('park-total').value = (unit * ping).toFixed(2);
      } else if (rawOf('park-total') !== '' && ping > 0) {
        $('park-unit').value = (total / ping).toFixed(2);
      }
    }
    updating = false;
  }

  on($('park-ping'), 'input', () => recompute('ping'));
  on($('park-unit'), 'input', () => recompute('unit'));
  on($('park-total'), 'input', () => recompute('total'));
}

// ------------------------------------------------------------
// Tab 7: 賣方實拿速算
// ------------------------------------------------------------
function initNet() {
  fillYearSelect($('net-prev-y'), '年');
  fillMonthSelect($('net-prev-m'));
  fillDaySelect($('net-prev-d'));
  fillYearSelect($('net-curr-y'), '年');
  fillMonthSelect($('net-curr-m'));
  fillDaySelect($('net-curr-d'));

  const today = new Date();
  $('net-curr-y').value = today.getFullYear() - 1911;
  $('net-curr-m').value = today.getMonth() + 1;
  $('net-curr-d').value = today.getDate();

  let svcMode = 'default';
  let transferMode = 'samesvc';
  let updatingPrice = false;

  initChoiceGroup('#net-svc-group', (btn) => {
    svcMode = btn.dataset.mode;
    $('net-svc-manual-wrap').style.display = svcMode === 'manual' ? 'block' : 'none';
    computeNet();
  });
  initChoiceGroup('#net-transfer-group', (btn) => {
    transferMode = btn.dataset.mode;
    $('net-transfer-manual-wrap').style.display = transferMode === 'manual' ? 'block' : 'none';
    computeNet();
  });
  on($('net-selfuse'), 'change', computeNet);

  const watchIds = [
    'net-totalping', 'net-parkping', 'net-parkprice',
    'net-acqprice', 'net-acqfee', 'net-landtax', 'net-loanleft',
    'net-svc-manual', 'net-transfer-manual',
  ];
  watchIds.forEach((id) => on($(id), 'input', computeNet));
  ['net-prev-y', 'net-prev-m', 'net-prev-d', 'net-curr-y', 'net-curr-m', 'net-curr-d'].forEach((id) => on($(id), 'change', computeNet));

  on($('net-total-price'), 'input', () => {
    if (updatingPrice) return;
    updatingPrice = true;
    syncUnitFromTotal();
    updatingPrice = false;
    computeNet();
  });
  on($('net-unit-price'), 'input', () => {
    if (updatingPrice) return;
    updatingPrice = true;
    syncTotalFromUnit();
    updatingPrice = false;
    computeNet();
  });

  function housePing() {
    return numOf('net-totalping') - numOf('net-parkping');
  }
  function syncUnitFromTotal() {
    const hp = housePing();
    if (hp > 0 && rawOf('net-total-price') !== '') {
      const unit = (numOf('net-total-price') - numOf('net-parkprice')) / hp;
      $('net-unit-price').value = unit.toFixed(2);
    }
  }
  function syncTotalFromUnit() {
    const hp = housePing();
    if (hp > 0 && rawOf('net-unit-price') !== '') {
      const total = numOf('net-unit-price') * hp + numOf('net-parkprice');
      $('net-total-price').value = total.toFixed(2);
    }
  }

  function getSvcFee(T) {
    return svcMode === 'manual' ? numOf('net-svc-manual') : T * 0.04;
  }
  function getTransferFee(T) {
    if (transferMode === 'manual') return numOf('net-transfer-manual');
    if (transferMode === 'percent3') return Math.min(T * 0.03, 30);
    return getSvcFee(T); // samesvc
  }
  function getTaxRate() {
    if ($('net-selfuse').checked) return 'selfuse';
    const prev = rocDateToGregorian($('net-prev-y').value, $('net-prev-m').value, $('net-prev-d').value);
    const curr = rocDateToGregorian($('net-curr-y').value, $('net-curr-m').value, $('net-curr-d').value);
    const rate = holdingRate(prev, curr);
    return rate; // null if dates incomplete
  }
  function getHoTax(T) {
    const rate = getTaxRate();
    if (rate === null) return null;
    const base = T - numOf('net-acqprice') - numOf('net-acqfee') - getTransferFee(T);
    if (rate === 'selfuse') return Math.max(0, base - 400) * 0.10;
    return Math.max(0, base) * rate;
  }

  function feesFor(T) {
    const scribe = 0.10;
    const registry = 0.20;
    const escrow = T * 0.0003;
    const svc = getSvcFee(T);
    const cancel = 0.60;
    const landTax = numOf('net-landtax');
    const hoTax = getHoTax(T);
    const loanLeft = numOf('net-loanleft');
    const hoTaxVal = hoTax === null ? 0 : hoTax;
    const total = scribe + registry + escrow + svc + cancel + landTax + hoTaxVal + loanLeft;
    return { scribe, registry, escrow, svc, cancel, landTax, hoTax, hoTaxVal, loanLeft, total, net: T - total };
  }

  function computeNet() {
    const T = numOf('net-total-price');
    const hasPrice = rawOf('net-total-price') !== '';
    const hp = housePing();

    const unitPrice = hp > 0 && hasPrice ? (T - numOf('net-parkprice')) / hp : NaN;
    $('net-result-unitprice').textContent = fmt2(unitPrice);

    const f = feesFor(T);
    $('net-result-tax').textContent = hasPrice ? (f.hoTax === null ? '—' : fmt2(f.hoTax)) : '—';
    $('net-result-net').textContent = hasPrice ? fmt2(f.net) : '—';

    $('net-fee-scribe').textContent = fmt2(f.scribe);
    $('net-fee-registry').textContent = fmt2(f.registry);
    $('net-fee-escrow').textContent = hasPrice ? fmt2(f.escrow) : '—';
    $('net-fee-svc').textContent = hasPrice ? fmt2(f.svc) : '—';
    $('net-fee-cancel').textContent = fmt2(f.cancel);
    $('net-fee-landtax').textContent = fmt2(f.landTax);
    $('net-fee-hotax').textContent = hasPrice ? (f.hoTax === null ? '—' : fmt2(f.hoTax)) : '—';
    $('net-fee-loanleft').textContent = fmt2(f.loanLeft);
    $('net-fee-total').textContent = hasPrice ? fmt2(f.total) : '—';
  }

  // 反推實拿：屋主說「我要拿 __ 萬」→ 二分搜尋反推想賣的總價
  on($('net-reverse-input'), 'input', () => {
    const target = numOf('net-reverse-input');
    if (rawOf('net-reverse-input') === '' || target <= 0) return;
    let lo = 0, hi = 200000;
    for (let i = 0; i < 60; i++) {
      const mid = (lo + hi) / 2;
      const net = feesFor(mid).net;
      if (net < target) lo = mid; else hi = mid;
    }
    const solvedT = (lo + hi) / 2;
    $('net-total-price').value = solvedT.toFixed(2);
    syncUnitFromTotal();
    computeNet();
  });

  on($('net-clear-btn'), 'click', () => {
    watchIds.concat(['net-total-price', 'net-unit-price', 'net-reverse-input']).forEach((id) => { if ($(id)) $(id).value = ''; });
    ['net-prev-y', 'net-prev-m', 'net-prev-d'].forEach((id) => { $(id).value = ''; });
    $('net-curr-y').value = today.getFullYear() - 1911;
    $('net-curr-m').value = today.getMonth() + 1;
    $('net-curr-d').value = today.getDate();
    $('net-selfuse').checked = false;
    computeNet();
  });

  on($('net-print-btn'), 'click', () => window.print());

  computeNet();
}

// ------------------------------------------------------------
// Boot
// ------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initHo();
  initAff();
  initLoan();
  initMisc();
  initConv();
  initPark();
  initNet();
});
