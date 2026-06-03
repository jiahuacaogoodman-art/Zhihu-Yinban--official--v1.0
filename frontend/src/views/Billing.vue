<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Btn, Chip, Dialog, Field, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'
import { ApiError } from '../api/types'

type SubTab = 'overview' | 'records' | 'alerts' | 'standards'
type BillingStatus = 'normal' | 'expiring_soon' | 'overdue' | 'settled' | string
type FeeCategory = 'bed' | 'care' | 'meal' | 'medical' | 'supplies' | 'service' | 'other'
type BillingCycle = 'monthly' | 'quarterly' | 'semi_annual' | 'yearly'
type PaymentMethod = 'cash' | 'bank_transfer' | 'wechat' | 'alipay' | 'pos' | 'other'

interface OverviewItem {
  admission_id: string
  patient_name: string
  bed_number?: string | null
  care_level_key?: string | null
  admission_date?: string | null
  billing_status: BillingStatus
  latest_period_end?: string | null
  days_remaining?: number | null
  total_paid: number
  total_records: number
}

interface BillingRecord {
  record_id: string
  admission_id: string
  patient_name?: string | null
  fee_standard_name?: string | null
  fee_category: FeeCategory | string
  amount: number
  billing_cycle: BillingCycle | string
  period_start: string
  period_end: string
  payment_method: PaymentMethod | string
  receipt_number?: string | null
  payer?: string | null
  paid_at: string
  created_at: string
}

interface AlertItem {
  admission_id: string
  patient_name: string
  bed_number?: string | null
  billing_status: BillingStatus
  latest_period_end: string
  days_remaining: number
  contact_name?: string | null
  contact_phone?: string | null
}

interface FeeStandard {
  standard_id: string
  name: string
  category: FeeCategory | string
  care_level_key?: string | null
  room_type?: string | null
  unit_price: number
  billing_cycle: BillingCycle | string
  description?: string | null
  is_required: boolean
  is_active: boolean
}

interface AdmissionOption {
  admission_id: string
  applicant_name: string
  status: string
  bed_number?: string
  care_level_key?: string
}

interface OverviewResponse {
  residents: OverviewItem[]
  summary: Partial<Record<'normal' | 'expiring_soon' | 'overdue', number>>
}

interface RecordsResponse { records: BillingRecord[] }
interface AlertsResponse { alerts: AlertItem[] }
interface StandardsResponse { standards: FeeStandard[] }
interface AdmissionsResponse { admissions: AdmissionOption[] }

const CATEGORY_LABEL: Record<string, string> = {
  bed: '床位费',
  care: '护理费',
  meal: '餐饮费',
  medical: '医疗费',
  supplies: '耗材费',
  service: '增值服务',
  other: '其他',
}

const CYCLE_LABEL: Record<string, string> = {
  monthly: '月付',
  quarterly: '季付',
  semi_annual: '半年付',
  yearly: '年付',
}

const METHOD_LABEL: Record<string, string> = {
  cash: '现金',
  bank_transfer: '银行转账',
  wechat: '微信支付',
  alipay: '支付宝',
  pos: 'POS',
  other: '其他',
}

const STATUS_LABEL: Record<string, string> = {
  normal: '正常',
  expiring_soon: '即将到期',
  overdue: '已欠费',
  settled: '已结清',
}

const { push: toast } = useToast()
const activeTab = ref<SubTab>('overview')
const loading = ref(false)
const admissionsLoading = ref(false)

const overview = ref<OverviewItem[]>([])
const billingRecords = ref<BillingRecord[]>([])
const alerts = ref<AlertItem[]>([])
const standards = ref<FeeStandard[]>([])
const admissions = ref<AdmissionOption[]>([])

const stats = reactive({
  normal: 0,
  expiringSoon: 0,
  overdue: 0,
  totalPaid: 0,
})

const receiveOpen = ref(false)
const receiveSaving = ref(false)
const receiveForm = reactive({
  admission_id: '',
  amount: '',
  fee_category: 'care' as FeeCategory,
  billing_cycle: 'monthly' as BillingCycle,
  period_start: '',
  period_end: '',
  payment_method: 'cash' as PaymentMethod,
  receipt_number: '',
  payer: '',
  notes: '',
})

const renewOpen = ref(false)
const renewing = ref(false)
const renewForm = reactive({
  admission_id: '',
  amount: '',
  fee_category: 'care' as FeeCategory,
  billing_cycle: 'monthly' as BillingCycle,
  num_cycles: '1',
  payment_method: 'cash' as PaymentMethod,
  receipt_number: '',
  payer: '',
  notes: '',
})

const standardOpen = ref(false)
const standardSaving = ref(false)
const standardForm = reactive({
  name: '',
  category: 'care' as FeeCategory,
  care_level_key: '',
  room_type: '',
  unit_price: '',
  billing_cycle: 'monthly' as BillingCycle,
  description: '',
  is_required: true,
})

const activeAdmissions = computed(() =>
  admissions.value.filter((a) =>
    ['paid', 'moving_in', 'active'].includes(a.status),
  ),
)

function errMsg(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.message
  if (e instanceof Error) return e.message
  return fallback
}

function money(value?: number | null): string {
  return `¥${Number(value ?? 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`
}

function statusTone(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'normal' || status === 'settled') return 'success'
  if (status === 'expiring_soon') return 'warning'
  if (status === 'overdue') return 'danger'
  return 'info'
}

function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status
}

function categoryLabel(category: string): string {
  return CATEGORY_LABEL[category] ?? category
}

function cycleLabel(cycle: string): string {
  return CYCLE_LABEL[cycle] ?? cycle
}

function methodLabel(method: string): string {
  return METHOD_LABEL[method] ?? method
}

function daysText(days?: number | null): string {
  if (days == null) return '未记录到期日'
  if (days < 0) return `已逾期 ${Math.abs(days)} 天`
  if (days === 0) return '今天到期'
  return `${days} 天后到期`
}

function resetReceiveForm() {
  Object.assign(receiveForm, {
    admission_id: '',
    amount: '',
    fee_category: 'care',
    billing_cycle: 'monthly',
    period_start: '',
    period_end: '',
    payment_method: 'cash',
    receipt_number: '',
    payer: '',
    notes: '',
  })
}

function resetStandardForm() {
  Object.assign(standardForm, {
    name: '',
    category: 'care',
    care_level_key: '',
    room_type: '',
    unit_price: '',
    billing_cycle: 'monthly',
    description: '',
    is_required: true,
  })
}

async function loadAdmissions() {
  admissionsLoading.value = true
  try {
    const res = await api.get<AdmissionsResponse>('/admissions?limit=500')
    admissions.value = res.admissions ?? []
  } catch (e: unknown) {
    admissions.value = []
    toast({ tone: 'warning', text: errMsg(e, '入住列表加载失败，可手动输入入住 ID') })
  } finally {
    admissionsLoading.value = false
  }
}

async function loadOverview() {
  loading.value = true
  try {
    const res = await api.get<OverviewResponse>('/billing/overview')
    overview.value = res.residents ?? []
    stats.normal = res.summary?.normal ?? 0
    stats.expiringSoon = res.summary?.expiring_soon ?? 0
    stats.overdue = res.summary?.overdue ?? 0
    stats.totalPaid = overview.value.reduce((sum, item) => sum + Number(item.total_paid ?? 0), 0)
  } catch (e: unknown) {
    overview.value = []
    toast({ tone: 'error', text: errMsg(e, '缴费总览加载失败') })
  } finally {
    loading.value = false
  }
}

async function loadRecords() {
  loading.value = true
  try {
    const res = await api.get<RecordsResponse>('/billing/records')
    billingRecords.value = res.records ?? []
  } catch (e: unknown) {
    billingRecords.value = []
    toast({ tone: 'error', text: errMsg(e, '缴费记录加载失败') })
  } finally {
    loading.value = false
  }
}

async function loadAlerts() {
  loading.value = true
  try {
    const res = await api.get<AlertsResponse>('/billing/alerts')
    alerts.value = res.alerts ?? []
  } catch (e: unknown) {
    alerts.value = []
    toast({ tone: 'error', text: errMsg(e, '到期提醒加载失败') })
  } finally {
    loading.value = false
  }
}

async function loadStandards() {
  loading.value = true
  try {
    const res = await api.get<StandardsResponse>('/billing/fee-standards')
    standards.value = res.standards ?? []
  } catch (e: unknown) {
    standards.value = []
    toast({ tone: 'error', text: errMsg(e, '收费标准加载失败') })
  } finally {
    loading.value = false
  }
}

function switchSubTab(tab: SubTab) {
  activeTab.value = tab
  if (tab === 'overview') loadOverview()
  if (tab === 'records') loadRecords()
  if (tab === 'alerts') loadAlerts()
  if (tab === 'standards') loadStandards()
}

function openReceive() {
  resetReceiveForm()
  receiveOpen.value = true
  if (!admissions.value.length && !admissionsLoading.value) loadAdmissions()
}

function openRenew(admissionId = '') {
  Object.assign(renewForm, {
    admission_id: admissionId,
    amount: '',
    fee_category: 'care',
    billing_cycle: 'monthly',
    num_cycles: '1',
    payment_method: 'cash',
    receipt_number: '',
    payer: '',
    notes: '',
  })
  renewOpen.value = true
  if (!admissions.value.length && !admissionsLoading.value) loadAdmissions()
}

function openStandard() {
  resetStandardForm()
  standardOpen.value = true
}

async function submitReceive() {
  if (!receiveForm.admission_id.trim() || !receiveForm.amount || !receiveForm.period_start || !receiveForm.period_end) {
    toast({ tone: 'warning', text: '请填写入住 ID、金额和费用周期' })
    return
  }
  receiveSaving.value = true
  try {
    await api.post('/billing/records', {
      admission_id: receiveForm.admission_id.trim(),
      amount: Number(receiveForm.amount),
      fee_category: receiveForm.fee_category,
      billing_cycle: receiveForm.billing_cycle,
      period_start: receiveForm.period_start,
      period_end: receiveForm.period_end,
      payment_method: receiveForm.payment_method,
      receipt_number: receiveForm.receipt_number || null,
      payer: receiveForm.payer || null,
      notes: receiveForm.notes || null,
    })
    toast({ tone: 'success', text: '收款登记成功' })
    receiveOpen.value = false
    await Promise.all([loadOverview(), loadRecords()])
    activeTab.value = 'records'
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '收款登记失败') })
  } finally {
    receiveSaving.value = false
  }
}

async function submitRenew() {
  if (!renewForm.admission_id.trim() || !renewForm.amount) {
    toast({ tone: 'warning', text: '请填写入住 ID 和金额' })
    return
  }
  renewing.value = true
  try {
    await api.post('/billing/renew', {
      admission_id: renewForm.admission_id.trim(),
      amount: Number(renewForm.amount),
      fee_category: renewForm.fee_category,
      billing_cycle: renewForm.billing_cycle,
      num_cycles: Number(renewForm.num_cycles || 1),
      payment_method: renewForm.payment_method,
      receipt_number: renewForm.receipt_number || null,
      payer: renewForm.payer || null,
      notes: renewForm.notes || null,
    })
    toast({ tone: 'success', text: '续费成功' })
    renewOpen.value = false
    await Promise.all([loadOverview(), loadRecords(), loadAlerts()])
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '续费失败') })
  } finally {
    renewing.value = false
  }
}

async function submitStandard() {
  if (!standardForm.name.trim() || !standardForm.unit_price) {
    toast({ tone: 'warning', text: '请填写标准名称和单价' })
    return
  }
  standardSaving.value = true
  try {
    await api.post('/billing/fee-standards', {
      name: standardForm.name.trim(),
      category: standardForm.category,
      care_level_key: standardForm.care_level_key || null,
      room_type: standardForm.room_type || null,
      unit_price: Number(standardForm.unit_price),
      billing_cycle: standardForm.billing_cycle,
      description: standardForm.description || null,
      is_required: standardForm.is_required,
      is_active: true,
    })
    toast({ tone: 'success', text: '收费标准已创建' })
    standardOpen.value = false
    await loadStandards()
    activeTab.value = 'standards'
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '收费标准创建失败') })
  } finally {
    standardSaving.value = false
  }
}

onMounted(() => {
  loadOverview()
  loadAdmissions()
})
</script>

<template>
  <div class="bl-view">
    <header class="bl-hero">
      <div>
        <p class="eyebrow">运营收款台</p>
        <h1 class="title-l">缴费管理</h1>
        <p class="meta">
          对齐后端真实接口：收费标准、收款登记、续费、欠费提醒和支付方式全部闭环。
        </p>
      </div>
      <div class="bl-hero-actions">
        <Btn variant="outline" size="sm" @click="openStandard">新增收费标准</Btn>
        <Btn variant="outline" size="sm" @click="openRenew()">续费</Btn>
        <Btn variant="primary" size="sm" @click="openReceive">登记收款</Btn>
      </div>
    </header>

    <div class="bl-stats">
      <GlassPanel class="bl-stat success">
        <div class="num">{{ stats.normal }}</div>
        <div class="lbl">正常缴费</div>
      </GlassPanel>
      <GlassPanel class="bl-stat warning">
        <div class="num">{{ stats.expiringSoon }}</div>
        <div class="lbl">即将到期</div>
      </GlassPanel>
      <GlassPanel class="bl-stat danger">
        <div class="num">{{ stats.overdue }}</div>
        <div class="lbl">已欠费</div>
      </GlassPanel>
      <GlassPanel class="bl-stat info">
        <div class="num">{{ money(stats.totalPaid) }}</div>
        <div class="lbl">累计收款</div>
      </GlassPanel>
    </div>

    <GlassPanel variant="card">
      <template #header>
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
      </template>

      <div v-if="loading" class="empty">
        <div class="skel" style="height: 180px; width: 100%"></div>
      </div>

      <div v-else-if="activeTab === 'overview'">
        <div v-if="overview.length === 0" class="empty">
          <p class="empty-title">暂无缴费总览</p>
          <p class="empty-sub">登记第一笔收款后，这里会显示老人缴费状态。</p>
        </div>
        <div v-else class="bl-list">
          <div v-for="o in overview" :key="o.admission_id" class="bl-row">
            <div>
              <strong>{{ o.patient_name || o.admission_id }}</strong>
              <p class="meta">
                {{ o.bed_number || '未分配床位' }}
                <span v-if="o.care_level_key"> · {{ o.care_level_key }}</span>
                · {{ daysText(o.days_remaining) }}
              </p>
            </div>
            <Chip :tone="statusTone(o.billing_status)">{{ statusLabel(o.billing_status) }}</Chip>
            <strong>{{ money(o.total_paid) }}</strong>
            <Btn variant="ghost" size="sm" @click="openRenew(o.admission_id)">续费</Btn>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'records'">
        <div v-if="billingRecords.length === 0" class="empty">
          <p class="empty-title">暂无缴费记录</p>
          <p class="empty-sub">可通过右上角“登记收款”录入现金、转账、POS、微信或支付宝收款。</p>
        </div>
        <div v-else class="bl-list">
          <div v-for="r in billingRecords" :key="r.record_id" class="bl-row">
            <div>
              <strong>{{ r.patient_name || r.admission_id }}</strong>
              <p class="meta">
                {{ categoryLabel(r.fee_category) }} · {{ methodLabel(r.payment_method) }}
                · {{ r.period_start }} 至 {{ r.period_end }}
              </p>
            </div>
            <Chip tone="accent">{{ cycleLabel(r.billing_cycle) }}</Chip>
            <strong>{{ money(r.amount) }}</strong>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'alerts'">
        <div v-if="alerts.length === 0" class="empty">
          <p class="empty-title">暂无到期提醒</p>
          <p class="empty-sub">7 天内到期或已欠费的在住老人会出现在这里。</p>
        </div>
        <div v-else class="bl-list">
          <div v-for="a in alerts" :key="a.admission_id" class="bl-row">
            <div>
              <strong>{{ a.patient_name || a.admission_id }}</strong>
              <p class="meta">
                {{ a.bed_number || '未分配床位' }} · 截止 {{ a.latest_period_end }}
                <span v-if="a.contact_name"> · 联系 {{ a.contact_name }}</span>
              </p>
            </div>
            <Chip :tone="statusTone(a.billing_status)">{{ statusLabel(a.billing_status) }}</Chip>
            <strong>{{ daysText(a.days_remaining) }}</strong>
          </div>
        </div>
      </div>

      <div v-else>
        <div v-if="standards.length === 0" class="empty">
          <p class="empty-title">暂无收费标准</p>
          <p class="empty-sub">建议先配置床位费、护理费、餐饮费等常规项目。</p>
        </div>
        <div v-else class="bl-list">
          <div v-for="s in standards" :key="s.standard_id" class="bl-row">
            <div>
              <strong>{{ s.name }}</strong>
              <p class="meta">
                {{ categoryLabel(s.category) }}
                <span v-if="s.care_level_key"> · 等级 {{ s.care_level_key }}</span>
                <span v-if="s.room_type"> · {{ s.room_type }}</span>
              </p>
            </div>
            <Chip :tone="s.is_active ? 'success' : 'info'">
              {{ s.is_active ? '启用' : '停用' }}
            </Chip>
            <strong>{{ money(s.unit_price) }} / {{ cycleLabel(s.billing_cycle) }}</strong>
          </div>
        </div>
      </div>
    </GlassPanel>

    <datalist id="billing-admission-options">
      <option
        v-for="a in activeAdmissions"
        :key="a.admission_id"
        :value="a.admission_id"
      >
        {{ a.applicant_name }} {{ a.bed_number ? `· ${a.bed_number}` : '' }}
      </option>
    </datalist>

    <Dialog v-model="receiveOpen" title="登记收款">
      <div class="bl-form-grid">
        <Field
          v-model="receiveForm.admission_id"
          label="入住 ID *"
          placeholder="adm_xxxxx"
          list="billing-admission-options"
          :hint="admissionsLoading ? '正在加载入住列表…' : '可输入或选择已缴费/在住老人'"
        />
        <Field v-model="receiveForm.amount" label="金额(元) *" type="number" inputmode="decimal" placeholder="3000" />
        <Field v-model="receiveForm.period_start" label="费用开始 *" type="date" />
        <Field v-model="receiveForm.period_end" label="费用截止 *" type="date" />
        <Field v-model="receiveForm.fee_category" label="费用类别" type="select">
          <option v-for="(label, key) in CATEGORY_LABEL" :key="key" :value="key">{{ label }}</option>
        </Field>
        <Field v-model="receiveForm.billing_cycle" label="计费周期" type="select">
          <option v-for="(label, key) in CYCLE_LABEL" :key="key" :value="key">{{ label }}</option>
        </Field>
        <Field v-model="receiveForm.payment_method" label="支付方式" type="select">
          <option v-for="(label, key) in METHOD_LABEL" :key="key" :value="key">{{ label }}</option>
        </Field>
        <Field v-model="receiveForm.receipt_number" label="收据/流水号" placeholder="可选" />
        <Field v-model="receiveForm.payer" label="缴费人" placeholder="家属姓名，可选" />
        <Field v-model="receiveForm.notes" label="备注" type="textarea" :rows="2" class="full" />
      </div>
      <template #actions>
        <Btn variant="ghost" :disabled="receiveSaving" @click="receiveOpen = false">取消</Btn>
        <Btn variant="primary" :loading="receiveSaving" @click="submitReceive">确认登记</Btn>
      </template>
    </Dialog>

    <Dialog v-model="renewOpen" title="续费">
      <div class="bl-form-grid">
        <Field
          v-model="renewForm.admission_id"
          label="入住 ID *"
          placeholder="adm_xxxxx"
          list="billing-admission-options"
          :hint="admissionsLoading ? '正在加载入住列表…' : '续费会自动从最近截止日的次日开始'"
        />
        <Field v-model="renewForm.amount" label="金额(元) *" type="number" inputmode="decimal" placeholder="3000" />
        <Field v-model="renewForm.num_cycles" label="续费周期数" type="number" inputmode="numeric" />
        <Field v-model="renewForm.fee_category" label="费用类别" type="select">
          <option v-for="(label, key) in CATEGORY_LABEL" :key="key" :value="key">{{ label }}</option>
        </Field>
        <Field v-model="renewForm.billing_cycle" label="计费周期" type="select">
          <option v-for="(label, key) in CYCLE_LABEL" :key="key" :value="key">{{ label }}</option>
        </Field>
        <Field v-model="renewForm.payment_method" label="支付方式" type="select">
          <option v-for="(label, key) in METHOD_LABEL" :key="key" :value="key">{{ label }}</option>
        </Field>
        <Field v-model="renewForm.receipt_number" label="收据/流水号" placeholder="可选" />
        <Field v-model="renewForm.payer" label="缴费人" placeholder="家属姓名，可选" />
        <Field v-model="renewForm.notes" label="备注" type="textarea" :rows="2" class="full" />
      </div>
      <template #actions>
        <Btn variant="ghost" :disabled="renewing" @click="renewOpen = false">取消</Btn>
        <Btn variant="primary" :loading="renewing" @click="submitRenew">确认续费</Btn>
      </template>
    </Dialog>

    <Dialog v-model="standardOpen" title="新增收费标准">
      <div class="bl-form-grid">
        <Field v-model="standardForm.name" label="标准名称 *" placeholder="二级护理费" />
        <Field v-model="standardForm.unit_price" label="单价(元) *" type="number" inputmode="decimal" placeholder="2500" />
        <Field v-model="standardForm.category" label="费用类别" type="select">
          <option v-for="(label, key) in CATEGORY_LABEL" :key="key" :value="key">{{ label }}</option>
        </Field>
        <Field v-model="standardForm.billing_cycle" label="计费周期" type="select">
          <option v-for="(label, key) in CYCLE_LABEL" :key="key" :value="key">{{ label }}</option>
        </Field>
        <Field v-model="standardForm.care_level_key" label="适用护理等级" placeholder="空=不限" />
        <Field v-model="standardForm.room_type" label="适用房型" placeholder="空=不限" />
        <label class="bl-check">
          <input v-model="standardForm.is_required" type="checkbox" />
          <span>入住必缴项目</span>
        </label>
        <Field v-model="standardForm.description" label="说明" type="textarea" :rows="2" class="full" />
      </div>
      <template #actions>
        <Btn variant="ghost" :disabled="standardSaving" @click="standardOpen = false">取消</Btn>
        <Btn variant="primary" :loading="standardSaving" @click="submitStandard">保存标准</Btn>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.bl-view {
  display: grid;
  gap: var(--sp-4, 16px);
  max-width: 1080px;
}

.bl-hero {
  display: flex;
  align-items: flex-end;
  gap: var(--sp-3, 12px);
  justify-content: space-between;
  padding: 18px;
  border: 1px solid rgba(20, 184, 166, 0.18);
  border-radius: var(--r-l, 18px);
  background:
    radial-gradient(circle at 12% 0%, rgba(20, 184, 166, 0.18), transparent 32%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.88), rgba(241, 245, 249, 0.74));
}

.eyebrow {
  margin: 0 0 4px;
  font: 700 11px / 1 var(--font-ui);
  color: var(--accent-ink);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.bl-hero-actions {
  display: flex;
  gap: var(--sp-2, 8px);
  flex-wrap: wrap;
  justify-content: flex-end;
}

.bl-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--sp-3, 12px);
}

.bl-stat {
  padding: 14px !important;
  text-align: center;
}

.bl-stat .num {
  font: 800 22px / 1.2 var(--font-ui);
}

.bl-stat .lbl {
  margin-top: 4px;
  font: 500 var(--fz-xs, 11px) / 1.4 var(--font-ui);
  color: var(--ink-3);
}

.bl-stat.success { background: rgba(16, 185, 129, 0.08); }
.bl-stat.warning { background: rgba(245, 158, 11, 0.08); }
.bl-stat.danger { background: rgba(239, 68, 68, 0.08); }
.bl-stat.info { background: rgba(59, 130, 246, 0.08); }

.bl-tabs {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.bl-tab-btn {
  padding: 10px 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.58);
  color: var(--ink-2);
  cursor: pointer;
  font: 650 var(--fz-sm, 13px) / 1 var(--font-ui);
  white-space: nowrap;
}

.bl-tab-btn.active {
  color: var(--accent-ink);
  border-color: rgba(20, 184, 166, 0.34);
  background: rgba(20, 184, 166, 0.12);
}

.bl-list {
  display: grid;
  gap: 8px;
}

.bl-row {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--r-s, 10px);
  background: rgba(255, 255, 255, 0.64);
}

.bl-row .meta {
  margin: 3px 0 0;
}

.bl-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-3, 12px);
  min-width: min(620px, calc(100vw - 48px));
}

.bl-form-grid .full {
  grid-column: 1 / -1;
}

.bl-check {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 24px;
  color: var(--ink-2);
  font: 600 var(--fz-sm, 13px) / 1.4 var(--font-ui);
}

@media (max-width: 760px) {
  .bl-hero {
    align-items: stretch;
    flex-direction: column;
  }

  .bl-hero-actions {
    justify-content: stretch;
  }

  .bl-hero-actions .btn {
    flex: 1;
  }

  .bl-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .bl-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .bl-form-grid {
    grid-template-columns: 1fr;
    min-width: 0;
  }
}
</style>
