/* billing.js — 缴费管理前端逻辑 */
const AUTH_KEY='zhyb_auth_token';
function getToken(){return localStorage.getItem(AUTH_KEY)||''}
function hdr(extra={}){const h={'Content-Type':'application/json',...extra};const t=getToken();if(t)h['X-Auth-Token']=t;return h}

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-'+btn.dataset.panel).classList.add('active');
  });
});

// ========== OVERVIEW ==========
async function loadOverview(){
  try{
    const r=await fetch('/api/billing/overview',{headers:hdr()});
    if(!r.ok)throw new Error('加载失败');
    const d=await r.json();
    document.getElementById('sNormal').textContent=d.summary.normal||0;
    document.getElementById('sExpiring').textContent=d.summary.expiring_soon||0;
    document.getElementById('sOverdue').textContent=d.summary.overdue||0;
    // Calculate total paid
    let totalPaid=0;
    (d.residents||[]).forEach(x=>totalPaid+=x.total_paid||0);
    document.getElementById('sTotalPaid').textContent=totalPaid.toLocaleString();
    // Update alert badge
    document.getElementById('alertBadge').textContent=(d.summary.expiring_soon||0)+(d.summary.overdue||0);
    // Render table
    if(!d.residents||d.residents.length===0){
      document.getElementById('overviewTable').innerHTML='<div class="empty-state"><i class="fa-solid fa-inbox"></i><p>暂无缴费数据</p></div>';
      return;
    }
    let html='<div style="overflow-x:auto"><table><thead><tr><th>老人姓名</th><th>床位</th><th>护理等级</th><th>缴费状态</th><th>截止日期</th><th>剩余天数</th><th>累计缴费</th></tr></thead><tbody>';
    d.residents.forEach(r=>{
      const sc=r.billing_status==='normal'?'normal':r.billing_status==='expiring_soon'?'expiring':'overdue';
      const sl=r.billing_status==='normal'?'正常':r.billing_status==='expiring_soon'?'即将到期':'已欠费';
      const days=r.days_remaining!=null?(r.days_remaining>=0?r.days_remaining+'天':'欠'+Math.abs(r.days_remaining)+'天'):'-';
      html+=`<tr><td>${esc(r.patient_name||'-')}</td><td>${esc(r.bed_number||'-')}</td><td>${esc(r.care_level_key||'-')}</td><td><span class="status-tag ${sc}"><i class="fa-solid fa-circle" style="font-size:6px"></i>${sl}</span></td><td>${r.latest_period_end||'-'}</td><td>${days}</td><td>¥${(r.total_paid||0).toLocaleString()}</td></tr>`;
    });
    html+='</tbody></table></div>';
    document.getElementById('overviewTable').innerHTML=html;
  }catch(e){
    document.getElementById('overviewTable').innerHTML=`<div class="empty-state"><i class="fa-solid fa-exclamation-triangle"></i><p>${e.message}</p></div>`;
  }
}

// ========== RECORDS ==========
async function loadRecords(){
  const admId=document.getElementById('recFilterAdm').value.trim();
  const cat=document.getElementById('recFilterCat').value;
  let url='/api/billing/records?limit=200';
  if(admId)url+=`&admission_id=${encodeURIComponent(admId)}`;
  if(cat)url+=`&fee_category=${cat}`;
  try{
    const r=await fetch(url,{headers:hdr()});
    if(!r.ok)throw new Error('加载失败');
    const d=await r.json();
    if(!d.records||d.records.length===0){
      document.getElementById('recordsTable').innerHTML='<div class="empty-state"><i class="fa-solid fa-receipt"></i><p>暂无缴费记录</p></div>';
      return;
    }
    let html='<div style="overflow-x:auto"><table><thead><tr><th>缴费时间</th><th>老人</th><th>类别</th><th>金额</th><th>周期</th><th>起始</th><th>截止</th><th>方式</th><th>收据号</th><th>操作</th></tr></thead><tbody>';
    d.records.forEach(r=>{
      const catMap={bed:'床位费',care:'护理费',meal:'餐饮费',medical:'医疗费',supplies:'耗材',service:'服务',other:'其他'};
      html+=`<tr><td>${(r.paid_at||'').slice(0,16)}</td><td>${esc(r.patient_name||r.admission_id)}</td><td>${catMap[r.fee_category]||r.fee_category}</td><td style="font-weight:600;color:var(--accent)">¥${r.amount.toLocaleString()}</td><td>${r.billing_cycle}</td><td>${r.period_start}</td><td>${r.period_end}</td><td>${r.payment_method}</td><td>${esc(r.receipt_number||'-')}</td><td><button class="btn btn-outline btn-sm" onclick="printReceiptPdf('${r.record_id}')"><i class="fa-solid fa-print"></i>打印收据</button></td></tr>`;
    });
    html+='</tbody></table></div>';
    document.getElementById('recordsTable').innerHTML=html;
  }catch(e){
    document.getElementById('recordsTable').innerHTML=`<div class="empty-state"><i class="fa-solid fa-exclamation-triangle"></i><p>${e.message}</p></div>`;
  }
}

// ========== ALERTS ==========
async function loadAlerts(){
  try{
    const r=await fetch('/api/billing/alerts?days=14',{headers:hdr()});
    if(!r.ok)throw new Error('加载失败');
    const d=await r.json();
    document.getElementById('alertBadge').textContent=d.total||0;
    if(!d.alerts||d.alerts.length===0){
      document.getElementById('alertsTable').innerHTML='<div class="empty-state"><i class="fa-solid fa-check-circle" style="color:#10b981"></i><p>无到期提醒，所有老人缴费正常</p></div>';
      return;
    }
    let html='<div style="overflow-x:auto"><table><thead><tr><th>老人姓名</th><th>床位</th><th>状态</th><th>截止日期</th><th>剩余/欠费天数</th><th>联系人</th><th>联系电话</th><th>操作</th></tr></thead><tbody>';
    d.alerts.forEach(a=>{
      const sc=a.billing_status==='overdue'?'overdue':'expiring';
      const sl=a.billing_status==='overdue'?'已欠费':'即将到期';
      const days=a.days_remaining>=0?a.days_remaining+'天':'欠'+Math.abs(a.days_remaining)+'天';
      html+=`<tr><td><strong>${esc(a.patient_name)}</strong></td><td>${esc(a.bed_number||'-')}</td><td><span class="status-tag ${sc}"><i class="fa-solid fa-circle" style="font-size:6px"></i>${sl}</span></td><td>${a.latest_period_end}</td><td style="font-weight:600;${a.days_remaining<0?'color:#ef4444':''}">${days}</td><td>${esc(a.contact_name||'-')}</td><td>${esc(a.contact_phone||'-')}</td><td><button class="btn btn-primary btn-sm" onclick="quickRenew('${a.admission_id}')"><i class="fa-solid fa-rotate"></i>续费</button></td></tr>`;
    });
    html+='</tbody></table></div>';
    document.getElementById('alertsTable').innerHTML=html;
  }catch(e){
    document.getElementById('alertsTable').innerHTML=`<div class="empty-state"><i class="fa-solid fa-exclamation-triangle"></i><p>${e.message}</p></div>`;
  }
}

// ========== FEE STANDARDS ==========
async function loadStandards(){
  try{
    const r=await fetch('/api/billing/fee-standards?include_inactive=true',{headers:hdr()});
    if(!r.ok)throw new Error('加载失败');
    const d=await r.json();
    if(!d.standards||d.standards.length===0){
      document.getElementById('standardsTable').innerHTML='<div class="empty-state"><i class="fa-solid fa-tags"></i><p>暂无收费标准，请点击"新增标准"添加</p></div>';
      return;
    }
    const catMap={bed:'床位费',care:'护理费',meal:'餐饮费',medical:'医疗费',supplies:'耗材',service:'增值服务',other:'其他'};
    const cycleMap={monthly:'月',quarterly:'季',semi_annual:'半年',yearly:'年'};
    let html='<div style="overflow-x:auto"><table><thead><tr><th>名称</th><th>类别</th><th>单价</th><th>周期</th><th>护理等级</th><th>房型</th><th>状态</th><th>操作</th></tr></thead><tbody>';
    d.standards.forEach(s=>{
      html+=`<tr><td><strong>${esc(s.name)}</strong></td><td>${catMap[s.category]||s.category}</td><td style="font-weight:600;color:var(--accent)">¥${s.unit_price.toLocaleString()}</td><td>${cycleMap[s.billing_cycle]||s.billing_cycle}</td><td>${esc(s.care_level_key||'不限')}</td><td>${esc(s.room_type||'不限')}</td><td>${s.is_active?'<span style="color:#10b981">启用</span>':'<span style="color:#9ca3af">停用</span>'}</td><td><button class="btn btn-outline btn-sm" onclick="deleteStd('${s.standard_id}')"><i class="fa-solid fa-trash"></i></button></td></tr>`;
    });
    html+='</tbody></table></div>';
    document.getElementById('standardsTable').innerHTML=html;
  }catch(e){
    document.getElementById('standardsTable').innerHTML=`<div class="empty-state"><i class="fa-solid fa-exclamation-triangle"></i><p>${e.message}</p></div>`;
  }
}

// ========== WECHAT STATUS ==========
async function loadWechatStatus(){
  try{
    const r=await fetch('/api/pay/wechat/status',{headers:hdr()});
    if(!r.ok)throw new Error('加载失败');
    const d=await r.json();
    const icon=d.enabled?'fa-check-circle':'fa-info-circle';
    const color=d.enabled?'#10b981':'#f59e0b';
    document.getElementById('wechatStatus').innerHTML=`
      <div style="display:flex;align-items:center;gap:12px;padding:16px;background:${d.enabled?'rgba(16,185,129,0.06)':'rgba(245,158,11,0.06)'};border-radius:12px;border:1px solid ${d.enabled?'rgba(16,185,129,0.15)':'rgba(245,158,11,0.15)'}">
        <i class="fa-solid ${icon}" style="font-size:24px;color:${color}"></i>
        <div>
          <div style="font-weight:600;font-size:15px">${d.message}</div>
          <div style="font-size:13px;color:var(--ink-3);margin-top:4px">
            商户号: ${d.mch_id||'未配置'} | AppID: ${d.app_id||'未配置'}
          </div>
          ${!d.enabled?'<div style="font-size:12px;color:var(--ink-4);margin-top:8px">未配置时运行在模拟模式，可正常测试流程但不会真正扣款。<br>配置方法：在 .env 文件中设置 WECHAT_PAY_MCH_ID / WECHAT_PAY_APP_ID / WECHAT_PAY_API_KEY_V3 等参数。</div>':''}
        </div>
      </div>`;
  }catch(e){
    document.getElementById('wechatStatus').innerHTML=`<div class="empty-state"><i class="fa-solid fa-exclamation-triangle"></i><p>${e.message}</p></div>`;
  }
}

// ========== MODALS ==========
function openPayModal(){document.getElementById('payModal').classList.add('show')}
function closePayModal(){document.getElementById('payModal').classList.remove('show');document.getElementById('qrBox').style.display='none'}
function openRenewModal(){document.getElementById('renewModal').classList.add('show')}
function closeRenewModal(){document.getElementById('renewModal').classList.remove('show')}
function openStdModal(){document.getElementById('stdModal').classList.add('show')}
function closeStdModal(){document.getElementById('stdModal').classList.remove('show')}

function quickRenew(admId){
  document.getElementById('renewAdmId').value=admId;
  openRenewModal();
}

// ========== SUBMIT: WeChat Pay ==========
async function submitPay(){
  const admId=document.getElementById('payAdmId').value.trim();
  const amount=parseFloat(document.getElementById('payAmount').value);
  if(!admId||!amount){alert('请填写入住ID和金额');return}
  const body={
    admission_id:admId,
    amount:amount,
    fee_category:document.getElementById('payCat').value,
    billing_cycle:document.getElementById('payCycle').value,
    period_start:document.getElementById('payStart').value||undefined,
    period_end:document.getElementById('payEnd').value||undefined,
    description:`智护银伴-${document.getElementById('payCat').selectedOptions[0].text}`,
  };
  try{
    const r=await fetch('/api/pay/wechat/native',{method:'POST',headers:hdr(),body:JSON.stringify(body)});
    if(!r.ok){const e=await r.json();throw new Error(e.detail||'下单失败')}
    const d=await r.json();
    // Show QR
    document.getElementById('qrBox').style.display='block';
    document.getElementById('qrAmount').textContent='¥'+amount.toLocaleString();
    const qrEl=document.getElementById('qrCode');
    qrEl.innerHTML='';
    if(window.QRCode){
      const canvas=document.createElement('canvas');
      QRCode.toCanvas(canvas,d.code_url,{width:180,margin:2},function(err){});
      qrEl.appendChild(canvas);
    }else{
      qrEl.innerHTML=`<div style="padding:20px;background:#f9f9f9;border-radius:8px;word-break:break-all;font-size:11px">${d.code_url}</div>`;
    }
    if(d.mock)qrEl.innerHTML+='<p style="color:#f59e0b;font-size:11px;margin-top:8px">⚠ 模拟模式（微信支付未配置）</p>';
    document.getElementById('paySubmitBtn').textContent='已生成';
  }catch(e){alert(e.message)}
}

// ========== SUBMIT: Renew ==========
async function submitRenew(){
  const admId=document.getElementById('renewAdmId').value.trim();
  const amount=parseFloat(document.getElementById('renewAmount').value);
  const numCycles=parseInt(document.getElementById('renewNum').value)||1;
  if(!admId||!amount){alert('请填写入住ID和金额');return}
  const body={
    admission_id:admId,
    amount:amount,
    fee_category:document.getElementById('renewCat').value,
    billing_cycle:document.getElementById('renewCycle').value,
    num_cycles:numCycles,
    payment_method:document.getElementById('renewMethod').value,
  };
  try{
    const r=await fetch('/api/billing/renew',{method:'POST',headers:hdr(),body:JSON.stringify(body)});
    if(!r.ok){const e=await r.json();throw new Error(e.detail||'续费失败')}
    const d=await r.json();
    alert(`续费成功！\n新截止日期: ${d.new_end_date}\n金额: ¥${d.amount}`);
    closeRenewModal();
    loadOverview();loadAlerts();loadRecords();
  }catch(e){alert(e.message)}
}

// ========== SUBMIT: Fee Standard ==========
async function submitStd(){
  const name=document.getElementById('stdName').value.trim();
  const price=parseFloat(document.getElementById('stdPrice').value);
  if(!name||!price){alert('请填写名称和单价');return}
  const body={
    name:name,
    category:document.getElementById('stdCat').value,
    unit_price:price,
    billing_cycle:document.getElementById('stdCycle').value,
    care_level_key:document.getElementById('stdLevel').value.trim()||null,
    room_type:document.getElementById('stdRoom').value.trim()||null,
    description:document.getElementById('stdDesc').value.trim()||null,
  };
  try{
    const r=await fetch('/api/billing/fee-standards',{method:'POST',headers:hdr(),body:JSON.stringify(body)});
    if(!r.ok){const e=await r.json();throw new Error(e.detail||'创建失败')}
    alert('收费标准创建成功');
    closeStdModal();loadStandards();
  }catch(e){alert(e.message)}
}

async function deleteStd(id){
  if(!confirm('确定删除该收费标准？'))return;
  try{
    const r=await fetch(`/api/billing/fee-standards/${id}`,{method:'DELETE',headers:hdr()});
    if(!r.ok)throw new Error('删除失败');
    loadStandards();
  }catch(e){alert(e.message)}
}

// ========== UTILS ==========
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

// ========== PRINT RECEIPT PDF ==========
async function printReceiptPdf(recordId){
  try{
    const r=await fetch(`/api/export/billing/receipt/${encodeURIComponent(recordId)}`,{headers:hdr()});
    if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.detail||'打印失败')}
    const blob=await r.blob();
    const url=URL.createObjectURL(blob);
    const w=window.open(url,'_blank');
    if(!w){const a=document.createElement('a');a.href=url;a.download=`收据_${recordId}.pdf`;a.click()}
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  }catch(e){alert('打开收据失败: '+e.message)}
}

// ========== INIT ==========
document.addEventListener('DOMContentLoaded',()=>{
  loadOverview();
  loadRecords();
  loadAlerts();
  loadStandards();
  loadWechatStatus();
});
