/* billing.js — 缴费管理前端逻辑（嵌入式 tab 版）
 *
 * 历史：原本是独立页 /billing 的脚本（监听 DOMContentLoaded、自带 token 读取、
 * 自带 .tab-btn 切换）。现在整体作为 index.html 的内嵌 tab 使用，所以本文件
 * 改造为：
 *   1) 全部入口暴露在 window.Billing 命名空间；不再 auto-init。
 *   2) auth header 直接复用 index.html 的 authHeaders()，避免双份 token 逻辑。
 *   3) 子 tab 切换逻辑由 Billing.bindSubtabs() 一次性绑定，幂等。
 *   4) 数据加载入口 Billing.activate()，由外层 switchTab('billing') 触发。
 *      首次激活时全量加载；后续激活只刷新最常变动的 overview/alerts。
 *   5) /billing 独立页保持兼容：billing.html 末尾会调一次 Billing.activate()
 *      + Billing.bindSubtabs()，行为与原页面一致。
 */
(function (global) {
  'use strict';

  // ── auth：优先用宿主页（index.html）暴露的 authHeaders；
  //    在独立 /billing 页面下退化为本地实现（沿用 zhyb_auth_token）。
  const AUTH_KEY = 'zhyb_auth_token';
  function hdr(extra) {
    if (typeof global.authHeaders === 'function') {
      return global.authHeaders(extra || {});
    }
    const h = Object.assign({ 'Content-Type': 'application/json' }, extra || {});
    const t = (localStorage.getItem(AUTH_KEY) || '');
    if (t) h['X-Auth-Token'] = t;
    return h;
  }

  // ── 工具
  function $(id) { return document.getElementById(id); }
  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }
  function err(el, msg) {
    if (!el) return;
    // 嵌入式 tab（index.html）使用 .billing-empty + .empty-title；
    // 独立页 (billing.html) 使用 .empty-state + <p>。两组节点同时挂上，
    // 各自 CSS 控制可见性即可，避免再做环境探测。
    const safe = esc(msg);
    el.innerHTML =
      '<div class="empty-state billing-empty">'
      + '<i class="fa-solid fa-exclamation-triangle"></i>'
      + '<div class="empty-title">' + safe + '</div>'
      + '<p>' + safe + '</p>'
      + '</div>';
  }

  /** 同步左侧导航的红点徽章（嵌入式 tab 模式下才存在）。
   *  count = 即将到期 + 已欠费。0 时隐藏徽章。 */
  function updateNavBadge(count) {
    const nav = $('navBillingBadge');
    if (!nav) return;
    if (count > 0) {
      nav.textContent = count > 99 ? '99+' : String(count);
      nav.hidden = false;
    } else {
      nav.hidden = true;
    }
  }

  // ────────────────────────────────────────────────────────────
  // OVERVIEW
  // ────────────────────────────────────────────────────────────
  async function loadOverview() {
    try {
      const r = await fetch('/api/billing/overview', { headers: hdr() });
      if (!r.ok) throw new Error('加载失败');
      const d = await r.json();

      const summary = d.summary || {};
      $('sNormal').textContent = summary.normal || 0;
      $('sExpiring').textContent = summary.expiring_soon || 0;
      $('sOverdue').textContent = summary.overdue || 0;

      let totalPaid = 0;
      (d.residents || []).forEach(x => { totalPaid += x.total_paid || 0; });
      $('sTotalPaid').textContent = totalPaid.toLocaleString();

      const badge = $('alertBadge');
      const total = (summary.expiring_soon || 0) + (summary.overdue || 0);
      if (badge) badge.textContent = total;
      // 同步更新左侧导航的红点（仅当宿主页中存在该 badge 元素）
      updateNavBadge(total);

      const wrap = $('overviewTable');
      if (!d.residents || d.residents.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><i class="fa-solid fa-inbox"></i><p>暂无缴费数据</p></div>';
        return;
      }
      let html = '<div style="overflow-x:auto"><table><thead><tr><th>老人姓名</th><th>床位</th><th>护理等级</th><th>缴费状态</th><th>截止日期</th><th>剩余天数</th><th>累计缴费</th></tr></thead><tbody>';
      d.residents.forEach(rec => {
        const sc = rec.billing_status === 'normal' ? 'normal'
          : rec.billing_status === 'expiring_soon' ? 'expiring' : 'overdue';
        const sl = rec.billing_status === 'normal' ? '正常'
          : rec.billing_status === 'expiring_soon' ? '即将到期' : '已欠费';
        const days = rec.days_remaining != null
          ? (rec.days_remaining >= 0 ? rec.days_remaining + '天' : '欠' + Math.abs(rec.days_remaining) + '天')
          : '-';
        html += '<tr>'
          + '<td>' + esc(rec.patient_name || '-') + '</td>'
          + '<td>' + esc(rec.bed_number || '-') + '</td>'
          + '<td>' + esc(rec.care_level_key || '-') + '</td>'
          + '<td><span class="status-tag ' + sc + '"><i class="fa-solid fa-circle" style="font-size:6px"></i>' + sl + '</span></td>'
          + '<td>' + esc(rec.latest_period_end || '-') + '</td>'
          + '<td>' + esc(days) + '</td>'
          + '<td>¥' + (rec.total_paid || 0).toLocaleString() + '</td>'
          + '</tr>';
      });
      html += '</tbody></table></div>';
      wrap.innerHTML = html;
    } catch (e) {
      err($('overviewTable'), e.message);
    }
  }

  // ────────────────────────────────────────────────────────────
  // RECORDS
  // ────────────────────────────────────────────────────────────
  async function loadRecords() {
    const admIdEl = $('recFilterAdm');
    const catEl = $('recFilterCat');
    const admId = (admIdEl && admIdEl.value || '').trim();
    const cat = (catEl && catEl.value || '');
    let url = '/api/billing/records?limit=200';
    if (admId) url += '&admission_id=' + encodeURIComponent(admId);
    if (cat) url += '&fee_category=' + encodeURIComponent(cat);
    try {
      const r = await fetch(url, { headers: hdr() });
      if (!r.ok) throw new Error('加载失败');
      const d = await r.json();
      const wrap = $('recordsTable');
      if (!d.records || d.records.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><i class="fa-solid fa-receipt"></i><p>暂无缴费记录</p></div>';
        return;
      }
      const catMap = { bed: '床位费', care: '护理费', meal: '餐饮费', medical: '医疗费', supplies: '耗材', service: '服务', other: '其他' };
      let html = '<div style="overflow-x:auto"><table><thead><tr><th>缴费时间</th><th>老人</th><th>类别</th><th>金额</th><th>周期</th><th>起始</th><th>截止</th><th>方式</th><th>收据号</th></tr></thead><tbody>';
      d.records.forEach(rec => {
        html += '<tr>'
          + '<td>' + esc((rec.paid_at || '').slice(0, 16)) + '</td>'
          + '<td>' + esc(rec.patient_name || rec.admission_id) + '</td>'
          + '<td>' + esc(catMap[rec.fee_category] || rec.fee_category) + '</td>'
          + '<td style="font-weight:600;color:var(--accent)">¥' + (rec.amount || 0).toLocaleString() + '</td>'
          + '<td>' + esc(rec.billing_cycle) + '</td>'
          + '<td>' + esc(rec.period_start) + '</td>'
          + '<td>' + esc(rec.period_end) + '</td>'
          + '<td>' + esc(rec.payment_method) + '</td>'
          + '<td>' + esc(rec.receipt_number || '-') + '</td>'
          + '</tr>';
      });
      html += '</tbody></table></div>';
      wrap.innerHTML = html;
    } catch (e) {
      err($('recordsTable'), e.message);
    }
  }

  // ────────────────────────────────────────────────────────────
  // ALERTS
  // ────────────────────────────────────────────────────────────
  async function loadAlerts() {
    try {
      const r = await fetch('/api/billing/alerts?days=14', { headers: hdr() });
      if (!r.ok) throw new Error('加载失败');
      const d = await r.json();
      const badge = $('alertBadge');
      if (badge) badge.textContent = d.total || 0;
      updateNavBadge(d.total || 0);

      const wrap = $('alertsTable');
      if (!d.alerts || d.alerts.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><i class="fa-solid fa-check-circle" style="color:#10b981"></i><p>无到期提醒，所有老人缴费正常</p></div>';
        return;
      }
      let html = '<div style="overflow-x:auto"><table><thead><tr><th>老人姓名</th><th>床位</th><th>状态</th><th>截止日期</th><th>剩余/欠费天数</th><th>联系人</th><th>联系电话</th><th>操作</th></tr></thead><tbody>';
      d.alerts.forEach(a => {
        const sc = a.billing_status === 'overdue' ? 'overdue' : 'expiring';
        const sl = a.billing_status === 'overdue' ? '已欠费' : '即将到期';
        const days = a.days_remaining >= 0 ? a.days_remaining + '天' : '欠' + Math.abs(a.days_remaining) + '天';
        html += '<tr>'
          + '<td><strong>' + esc(a.patient_name) + '</strong></td>'
          + '<td>' + esc(a.bed_number || '-') + '</td>'
          + '<td><span class="status-tag ' + sc + '"><i class="fa-solid fa-circle" style="font-size:6px"></i>' + sl + '</span></td>'
          + '<td>' + esc(a.latest_period_end) + '</td>'
          + '<td style="font-weight:600;' + (a.days_remaining < 0 ? 'color:#ef4444' : '') + '">' + esc(days) + '</td>'
          + '<td>' + esc(a.contact_name || '-') + '</td>'
          + '<td>' + esc(a.contact_phone || '-') + '</td>'
          + '<td><button class="btn btn-primary btn-sm" data-billing-renew="' + esc(a.admission_id) + '"><i class="fa-solid fa-rotate"></i>续费</button></td>'
          + '</tr>';
      });
      html += '</tbody></table></div>';
      wrap.innerHTML = html;
      // 事件委托：避免在 HTML 字符串里直接写 onclick="quickRenew(...)" 时，
      // 当 admission_id 含特殊字符会导致 JS 注入或属性截断。
      wrap.querySelectorAll('[data-billing-renew]').forEach(btn => {
        btn.addEventListener('click', () => quickRenew(btn.dataset.billingRenew));
      });
    } catch (e) {
      err($('alertsTable'), e.message);
    }
  }

  // ────────────────────────────────────────────────────────────
  // FEE STANDARDS
  // ────────────────────────────────────────────────────────────
  async function loadStandards() {
    try {
      const r = await fetch('/api/billing/fee-standards?include_inactive=true', { headers: hdr() });
      if (!r.ok) throw new Error('加载失败');
      const d = await r.json();
      const wrap = $('standardsTable');
      if (!d.standards || d.standards.length === 0) {
        wrap.innerHTML = '<div class="empty-state"><i class="fa-solid fa-tags"></i><p>暂无收费标准，请点击"新增标准"添加</p></div>';
        return;
      }
      const catMap = { bed: '床位费', care: '护理费', meal: '餐饮费', medical: '医疗费', supplies: '耗材', service: '增值服务', other: '其他' };
      const cycleMap = { monthly: '月', quarterly: '季', semi_annual: '半年', yearly: '年' };
      let html = '<div style="overflow-x:auto"><table><thead><tr><th>名称</th><th>类别</th><th>单价</th><th>周期</th><th>护理等级</th><th>房型</th><th>状态</th><th>操作</th></tr></thead><tbody>';
      d.standards.forEach(s => {
        html += '<tr>'
          + '<td><strong>' + esc(s.name) + '</strong></td>'
          + '<td>' + esc(catMap[s.category] || s.category) + '</td>'
          + '<td style="font-weight:600;color:var(--accent)">¥' + (s.unit_price || 0).toLocaleString() + '</td>'
          + '<td>' + esc(cycleMap[s.billing_cycle] || s.billing_cycle) + '</td>'
          + '<td>' + esc(s.care_level_key || '不限') + '</td>'
          + '<td>' + esc(s.room_type || '不限') + '</td>'
          + '<td>' + (s.is_active ? '<span style="color:#10b981">启用</span>' : '<span style="color:#9ca3af">停用</span>') + '</td>'
          + '<td><button class="btn btn-outline btn-sm" data-billing-del-std="' + esc(s.standard_id) + '"><i class="fa-solid fa-trash"></i></button></td>'
          + '</tr>';
      });
      html += '</tbody></table></div>';
      wrap.innerHTML = html;
      wrap.querySelectorAll('[data-billing-del-std]').forEach(btn => {
        btn.addEventListener('click', () => deleteStd(btn.dataset.billingDelStd));
      });
    } catch (e) {
      err($('standardsTable'), e.message);
    }
  }

  // ────────────────────────────────────────────────────────────
  // WeChat status
  // ────────────────────────────────────────────────────────────
  async function loadWechatStatus() {
    try {
      const r = await fetch('/api/pay/wechat/status', { headers: hdr() });
      if (!r.ok) throw new Error('加载失败');
      const d = await r.json();
      const icon = d.enabled ? 'fa-check-circle' : 'fa-info-circle';
      const color = d.enabled ? '#10b981' : '#f59e0b';
      const bg = d.enabled ? 'rgba(16,185,129,0.06)' : 'rgba(245,158,11,0.06)';
      const bd = d.enabled ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)';
      $('wechatStatus').innerHTML =
        '<div style="display:flex;align-items:center;gap:12px;padding:16px;background:' + bg + ';border-radius:12px;border:1px solid ' + bd + '">'
        + '<i class="fa-solid ' + icon + '" style="font-size:24px;color:' + color + '"></i>'
        + '<div>'
        + '<div style="font-weight:600;font-size:15px">' + esc(d.message) + '</div>'
        + '<div style="font-size:13px;color:var(--ink-3);margin-top:4px">商户号: ' + esc(d.mch_id || '未配置') + ' | AppID: ' + esc(d.app_id || '未配置') + '</div>'
        + (!d.enabled ? '<div style="font-size:12px;color:var(--ink-4);margin-top:8px">未配置时运行在模拟模式，可正常测试流程但不会真正扣款。<br>配置方法：在 .env 文件中设置 WECHAT_PAY_MCH_ID / WECHAT_PAY_APP_ID / WECHAT_PAY_API_KEY_V3 等参数。</div>' : '')
        + '</div></div>';
    } catch (e) {
      err($('wechatStatus'), e.message);
    }
  }

  // ────────────────────────────────────────────────────────────
  // Modals
  // ────────────────────────────────────────────────────────────
  function openPayModal() { const m = $('payModal'); if (m) m.classList.add('show'); }
  function closePayModal() {
    const m = $('payModal'); if (m) m.classList.remove('show');
    const qb = $('qrBox'); if (qb) qb.style.display = 'none';
  }
  function openRenewModal() { const m = $('renewModal'); if (m) m.classList.add('show'); }
  function closeRenewModal() { const m = $('renewModal'); if (m) m.classList.remove('show'); }
  function openStdModal() { const m = $('stdModal'); if (m) m.classList.add('show'); }
  function closeStdModal() { const m = $('stdModal'); if (m) m.classList.remove('show'); }
  function quickRenew(admId) {
    const el = $('renewAdmId'); if (el) el.value = admId;
    openRenewModal();
  }

  // ────────────────────────────────────────────────────────────
  // Submit handlers
  // ────────────────────────────────────────────────────────────
  async function submitPay() {
    const admId = ($('payAdmId').value || '').trim();
    const amount = parseFloat($('payAmount').value);
    if (!admId || !amount) { alert('请填写入住ID和金额'); return; }
    const catSel = $('payCat');
    const body = {
      admission_id: admId,
      amount: amount,
      fee_category: catSel.value,
      billing_cycle: $('payCycle').value,
      period_start: $('payStart').value || undefined,
      period_end: $('payEnd').value || undefined,
      description: '智护银伴-' + (catSel.selectedOptions[0] && catSel.selectedOptions[0].text || ''),
    };
    try {
      const r = await fetch('/api/pay/wechat/native', { method: 'POST', headers: hdr(), body: JSON.stringify(body) });
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || '下单失败'); }
      const d = await r.json();
      $('qrBox').style.display = 'block';
      $('qrAmount').textContent = '¥' + amount.toLocaleString();
      const qrEl = $('qrCode');
      qrEl.innerHTML = '';
      if (window.QRCode) {
        const canvas = document.createElement('canvas');
        window.QRCode.toCanvas(canvas, d.code_url, { width: 180, margin: 2 }, function () {});
        qrEl.appendChild(canvas);
      } else {
        qrEl.innerHTML = '<div style="padding:20px;background:#f9f9f9;border-radius:8px;word-break:break-all;font-size:11px">' + esc(d.code_url) + '</div>';
      }
      if (d.mock) qrEl.innerHTML += '<p style="color:#f59e0b;font-size:11px;margin-top:8px">⚠ 模拟模式（微信支付未配置）</p>';
      $('paySubmitBtn').textContent = '已生成';
    } catch (e) { alert(e.message); }
  }

  async function submitRenew() {
    const admId = ($('renewAdmId').value || '').trim();
    const amount = parseFloat($('renewAmount').value);
    const numCycles = parseInt($('renewNum').value, 10) || 1;
    if (!admId || !amount) { alert('请填写入住ID和金额'); return; }
    const body = {
      admission_id: admId,
      amount: amount,
      fee_category: $('renewCat').value,
      billing_cycle: $('renewCycle').value,
      num_cycles: numCycles,
      payment_method: $('renewMethod').value,
    };
    try {
      const r = await fetch('/api/billing/renew', { method: 'POST', headers: hdr(), body: JSON.stringify(body) });
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || '续费失败'); }
      const d = await r.json();
      alert('续费成功！\n新截止日期: ' + d.new_end_date + '\n金额: ¥' + d.amount);
      closeRenewModal();
      // 续费会同时影响总览/记录/提醒，全部刷新
      loadOverview(); loadAlerts(); loadRecords();
    } catch (e) { alert(e.message); }
  }

  async function submitStd() {
    const name = ($('stdName').value || '').trim();
    const price = parseFloat($('stdPrice').value);
    if (!name || !price) { alert('请填写名称和单价'); return; }
    const body = {
      name: name,
      category: $('stdCat').value,
      unit_price: price,
      billing_cycle: $('stdCycle').value,
      care_level_key: ($('stdLevel').value || '').trim() || null,
      room_type: ($('stdRoom').value || '').trim() || null,
      description: ($('stdDesc').value || '').trim() || null,
    };
    try {
      const r = await fetch('/api/billing/fee-standards', { method: 'POST', headers: hdr(), body: JSON.stringify(body) });
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || '创建失败'); }
      alert('收费标准创建成功');
      closeStdModal();
      loadStandards();
    } catch (e) { alert(e.message); }
  }

  async function deleteStd(id) {
    if (!confirm('确定删除该收费标准？')) return;
    try {
      const r = await fetch('/api/billing/fee-standards/' + encodeURIComponent(id), { method: 'DELETE', headers: hdr() });
      if (!r.ok) throw new Error('删除失败');
      loadStandards();
    } catch (e) { alert(e.message); }
  }

  // ────────────────────────────────────────────────────────────
  // 子 tab 切换 + 一次性事件绑定（幂等）
  // ────────────────────────────────────────────────────────────
  let _subtabsBound = false;
  function bindSubtabs(scope) {
    if (_subtabsBound) return;
    _subtabsBound = true;
    const root = scope || document;
    // 子 tab 按钮
    root.querySelectorAll('[data-billing-subtab]').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.billingSubtab;
        root.querySelectorAll('[data-billing-subtab]').forEach(b =>
          b.classList.toggle('active', b.dataset.billingSubtab === target)
        );
        root.querySelectorAll('[data-billing-panel]').forEach(p =>
          p.classList.toggle('active', p.dataset.billingPanel === target)
        );
      });
    });
    // 模态/筛选器：声明式绑定，避免内联 onclick
    root.querySelectorAll('[data-billing-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        const fn = ACTIONS[btn.dataset.billingAction];
        if (typeof fn === 'function') fn();
      });
    });
    // 记录 tab 的筛选器
    const recAdm = root.querySelector('#recFilterAdm');
    const recCat = root.querySelector('#recFilterCat');
    if (recAdm) recAdm.addEventListener('input', loadRecords);
    if (recCat) recCat.addEventListener('change', loadRecords);
  }

  // 第一次进入 billing tab 时全量加载，之后每次激活只刷快变项。
  let _firstActivated = false;
  async function activate() {
    if (!_firstActivated) {
      _firstActivated = true;
      loadOverview();
      loadRecords();
      loadAlerts();
      loadStandards();
      loadWechatStatus();
    } else {
      loadOverview();
      loadAlerts();
    }
  }

  // 强制全量刷新（外部需要时可用）
  function refresh() {
    loadOverview(); loadRecords(); loadAlerts(); loadStandards(); loadWechatStatus();
  }

  const ACTIONS = {
    openPayModal, closePayModal,
    openRenewModal, closeRenewModal,
    openStdModal, closeStdModal,
    submitPay, submitRenew, submitStd,
  };

  global.Billing = {
    activate,
    refresh,
    bindSubtabs,
    // 暴露子函数：方便宿主页调试或独立 billing.html 使用
    loadOverview, loadRecords, loadAlerts, loadStandards, loadWechatStatus,
    openPayModal, closePayModal,
    openRenewModal, closeRenewModal,
    openStdModal, closeStdModal,
    submitPay, submitRenew, submitStd, deleteStd, quickRenew,
  };

  // 兼容独立 /billing 页面：billing.html 自己会 DOMContentLoaded 触发
  // bindSubtabs() + activate()。这里不再 auto-init，避免双重加载。
})(window);
