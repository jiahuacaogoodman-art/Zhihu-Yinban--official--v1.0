<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Btn, Field, GlassPanel, Chip, Dialog } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

/**
 * Billing — 缴费管理
 *
 * 对应旧版 index.html 的 tab-billing + static/billing.js：
 *   - 缴费总览 GET /api/billing/overview
 *   - 缴费记录 GET /api/billing/records
 *   - 到期提醒 GET /api/billing/alerts
 *   - 收费标准 GET /api/billing/standards
 *   - 续费 POST /api/billing/renew
 */

type SubTab = 'overview' | 'records' | 'alerts' | 'standards'

interface OverviewItem {
  admission_id: string
  patient_name?: string
  status: string
  paid_until?: string
  total_paid?: number
}

interface BillingRecord {
  record_id: string
  admission_id: string
  amount: number
  category: string
  payment_method?: string
  created_at: string
}

interface Alert {
  admission_id: string
  patient_name?: string
  status: string
  paid_until?: string
  days_remaining?: number
}

interface Standard {
  standard_id: string
  name: string
  category: string
  price: number
  cycle: string
}

const { push: toast } = useToast()
const activeTab = ref<SubTab>('overview')

// ── Data ──
const overview = ref<OverviewItem[]>([])
const billingRecords = ref<BillingRecord[]>([])
const alerts = ref<Alert[]>([])
const standards = ref<Standard[]>([])
const loading = ref(false)
const stats = ref({ normal: 0, expiring: 0, overdue: 0, totalPaid: 0 })

// ── Renew dialog ──
const renewOpen = ref(false)
const renewForm = ref({ admission_id: '', amount: '', category: 'care', cycle: 'monthly', payment_method: 'cash' })
const renewing = ref(false)

async function loadOverview() {
  loading.value = true
  try {
    const res = await api.get<any>('/billing/overview')
    overview.value = res.items ?? res.overview ?? []
    stats.value = res.summary ?? { normal: 0, expiring: 0, overdue: 0, totalPaid: 0 }
  } catch (e: any) {
    // billing API might not exist in all deployments
    overview.value = []
  } finally {
    loading.value = false
  }
}

async function loadRecords() {
  try {
    const res = await api.get<any>('/billing/records')
    billingRecords.value = res.records ?? []
  } catch {
    billingRecords.value = []
  }
}

async function loadAlerts() {
  try {
    const res = await api.get<any>('/billing/alerts')
    alerts.value = res.alerts ?? []
  } catch {
    alerts.value = []
  }
}

async function loadStandards() {
  try {
    const res = await api.get<any>('/billing/standards')
    standards.value = res.standards ?? []
  } catch {
    standards.value = []
  }
}

function switchSubTab(tab: SubTab) {
  activeTab.value = tab
  if (tab === 'overview') loadOverview()
  else if (tab === 'records') loadRecords()
  else if (tab === 'alerts') loadAlerts()
  else if (tab === 'standards') loadStandards()
}

async function submitRenew() {
  if (!renewForm.value.admission_id || !renewForm.value.amount) {
    toast({ tone: 'warning', text: '请填写入住 ID 和金额' })
    return
  }
  renewing.value = true
  try {
    await api.post('/billing/renew', {
      admission_id: renewForm.value.admission_id,
      amount: parseFloat(renewForm.value.amount),
      category: renewForm.value.category,
      cycle: renewForm.value.cycle,
      payment_method: renewForm.value.payment_method,
    })
    toast({ tone: 'success', text: '续费成功' })
    renewOpen.value = false
    loadOverview()
  } catch (e: any) {
    toast({ tone: 'error', text: e.message ?? '续费失败' })
  } finally {
    renewing.value = false
  }
}

function statusTone(s: string) {
  if (s === 'normal' || s === '正常') return 'success'
  if (s === 'expiring' || s === '即将到期') return 'warning'
  return 'danger'
}

onMounted(loadOverview)
</script>

<template>
  <div class="bl-view">
    <GlassPanel variant="card">
      <template #header>
        <span class="title-l">缴费管理</span>
        <Btn variant="primary" size="sm" @click="renewOpen = true" style="margin-left: auto;">续费</Btn>
      </template>

      <!-- Sub tabs -->
      <div class="bl-tabs">
        <button
          v-for="t in (['overview', 'records', 'alerts', 'standards'] as SubTab[])"
          :key="t"
          class="bl-tab-btn"
          :class="{ active: activeTab === t }"
          @click="switchSubTab(t)"
        >
          {{ { overview: '缴费总览', records: '缴费记录', alerts: '到期提醒', standards: '收费标准' }[t] }}
        </button>
      </div>

      <!-- Overview -->
      <div v-if="activeTab === 'overview'">
        <div class="bl-stats">
          <div class="bl-stat success"><div class="num">{{ stats.normal }}</div><div class="lbl">正常缴费</div></div>
          <div class="bl-stat warning"><div class="num">{{ stats.expiring }}</div><div class="lbl">即将到期</div></div>
          <div class="bl-stat danger"><div class="num">{{ stats.overdue }}</div><div class="lbl">已欠费</div></div>
          <div class="bl-stat info"><div class="num">{{ stats.totalPaid }}</div><div class="lbl">累计收款(元)</div></div>
        </div>
        <div v-if="overview.length === 0 && !loading" class="empty"><p>暂无数据</p></div>
        <div v-else class="bl-list">
          <div v-for="o in overview" :key="o.admission_id" class="bl-row">
            <span class="body-s"><strong>{{ o.patient_name ?? o.admission_id }}</strong></span>
            <Chip :tone="statusTone(o.status)">{{ o.status }}</Chip>
            <span class="meta">到期: {{ o.paid_until ?? '—' }}</span>
          </div>
        </div>
      </div>

      <!-- Records -->
      <div v-if="activeTab === 'records'">
        <div v-if="billingRecords.length === 0" class="empty"><p>暂无记录</p></div>
        <div v-else class="bl-list">
          <div v-for="r in billingRecords" :key="r.record_id" class="bl-row">
            <span class="body-s">{{ r.admission_id }} · {{ r.category }}</span>
            <strong>¥{{ r.amount }}</strong>
            <span class="meta">{{ r.payment_method }} · {{ r.created_at }}</span>
          </div>
        </div>
      </div>

      <!-- Alerts -->
      <div v-if="activeTab === 'alerts'">
        <div v-if="alerts.length === 0" class="empty"><p>暂无提醒</p></div>
        <div v-else class="bl-list">
          <div v-for="a in alerts" :key="a.admission_id" class="bl-row">
            <span class="body-s"><strong>{{ a.patient_name ?? a.admission_id }}</strong></span>
            <Chip :tone="statusTone(a.status)">{{ a.status }}</Chip>
            <span class="meta">
              {{ a.days_remaining != null ? `${a.days_remaining} 天后到期` : '' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Standards -->
      <div v-if="activeTab === 'standards'">
        <div v-if="standards.length === 0" class="empty"><p>暂无收费标准</p></div>
        <div v-else class="bl-list">
          <div v-for="s in standards" :key="s.standard_id" class="bl-row">
            <span class="body-s"><strong>{{ s.name }}</strong></span>
            <Chip tone="accent">{{ s.category }}</Chip>
            <strong>¥{{ s.price }} / {{ s.cycle }}</strong>
          </div>
        </div>
      </div>
    </GlassPanel>

    <!-- 续费对话框 -->
    <Dialog v-model="renewOpen" title="续费">
      <div class="bl-renew-form">
        <Field v-model="renewForm.admission_id" label="入住老人 ID *" placeholder="adm_xxxxx" />
        <Field v-model="renewForm.amount" label="金额(元) *" type="number" placeholder="3000" />
        <div class="field-group">
          <span class="field-label">费用类别</span>
          <select v-model="renewForm.category" class="field">
            <option value="care">护理费</option>
            <option value="bed">床位费</option>
            <option value="meal">餐饮费</option>
            <option value="other">其他</option>
          </select>
        </div>
        <div class="field-group">
          <span class="field-label">支付方式</span>
          <select v-model="renewForm.payment_method" class="field">
            <option value="cash">现金</option>
            <option value="wechat">微信</option>
            <option value="bank_transfer">银行转账</option>
            <option value="alipay">支付宝</option>
          </select>
        </div>
      </div>
      <template #actions>
        <Btn variant="ghost" @click="renewOpen = false">取消</Btn>
        <Btn variant="primary" :loading="renewing" @click="submitRenew">确认续费</Btn>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.bl-view {
  max-width: 900px;
}
.bl-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: var(--sp-4, 16px);
  overflow-x: auto;
  padding-bottom: 4px;
}
.bl-tab-btn {
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: transparent;
  font: 500 var(--fz-sm, 13px) / 1 var(--font-ui);
  color: var(--ink-2);
  cursor: pointer;
  white-space: nowrap;
}
.bl-tab-btn.active {
  background: rgba(20, 184, 166, 0.12);
  color: var(--accent-ink);
  border-color: rgba(20, 184, 166, 0.3);
  font-weight: 600;
}
.bl-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-2, 8px);
  margin-bottom: var(--sp-4, 16px);
}
.bl-stat {
  padding: 12px;
  border-radius: var(--r-s, 10px);
  text-align: center;
}
.bl-stat.success { background: rgba(16, 185, 129, 0.1); }
.bl-stat.warning { background: rgba(245, 158, 11, 0.1); }
.bl-stat.danger { background: rgba(239, 68, 68, 0.1); }
.bl-stat.info { background: rgba(99, 102, 241, 0.1); }
.bl-stat .num { font: 700 22px/1.2 var(--font-ui); }
.bl-stat .lbl { font: 400 var(--fz-xs, 11px) / 1.4 var(--font-ui); color: var(--ink-3); margin-top: 4px; }
.bl-list {
  display: grid;
  gap: 4px;
}
.bl-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.02);
}
.bl-row .meta { margin-left: auto; }
.bl-renew-form {
  display: grid;
  gap: var(--sp-2, 8px);
}
.field-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-label {
  font: 600 var(--fz-xs, 11px) / 1.4 var(--font-ui);
  color: var(--ink-3);
}
@media (max-width: 640px) {
  .bl-stats { grid-template-columns: repeat(2, 1fr); }
  .bl-row { flex-wrap: wrap; }
}
</style>
