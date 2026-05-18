<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Btn, Chip, Dialog, Field, GlassPanel } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'
import { ApiError } from '../api/types'

/**
 * PaymentChannels — 多支付渠道管理(管理员后台)
 *
 * 后端 routers/payment_channels.py 早就实现了:
 *   GET    /api/payment/channels                列表 + 元数据
 *   GET    /api/payment/channels/{key}          单个详情
 *   PATCH  /api/payment/channels/{key}          启停 / 改配置
 *   POST   /api/payment/channels/{key}/test     连通性测试
 *
 * 但前端没有任何 UI 调它，导致用户"看不到多支付渠道接口"。本页解决这个问题。
 *
 * 注意:
 *   1) 后端对密码型字段(password type)做了脱敏返回 "●●●●●●"，编辑时必须不能
 *      把这串黑点回传 —— 配置 Dialog 里 password 字段始终从空开始，提示"留空
 *      则保持当前值"。提交时会过滤掉空 password 字段不发到后端。
 *   2) 后端 update_channel 收到空字符串会"删除字段"。所以普通 text 字段为空也
 *      不发(避免误删已有配置)。
 *   3) FontAwesome 在 v2 没加载，因此用 emoji 兜底渲染图标。
 */

interface ConfigField {
  key: string
  label: string
  type: 'text' | 'password'
  required: boolean
  hint?: string
}

interface Channel {
  channel_key: string
  name: string
  icon: string
  color: string
  requires_network: boolean
  requires_config: boolean
  description: string
  config_fields: ConfigField[]
  is_enabled: boolean
  config_complete: boolean
  config: Record<string, string>
  updated_at: string
  updated_by: string
}

interface ChannelsResponse {
  code: number
  channels: Channel[]
  summary: {
    total: number
    enabled: number
    online_channels: string[]
    offline_channels: string[]
  }
}

interface TestResponse {
  code: number
  channel_key: string
  test_result: 'success' | 'failed' | 'incomplete' | 'warning' | 'unknown'
  message: string
}

// 渠道 → emoji 兜底
const ICON_FALLBACK: Record<string, string> = {
  cash: '💵',
  bank_transfer: '🏦',
  pos: '💳',
  wechat: '💬',
  alipay: '🅰',
}

const { push: toast } = useToast()
const channels = ref<Channel[]>([])
const summary = ref<ChannelsResponse['summary'] | null>(null)
const loading = ref(false)
const togglingKey = ref<string | null>(null)
const testingKey = ref<string | null>(null)

// 配置 Dialog
const configOpen = ref(false)
const configChannel = ref<Channel | null>(null)
const configSaving = ref(false)
const configForm = reactive<Record<string, string>>({})

const fmtUpdated = (iso: string) => (iso || '').replace('T', ' ').slice(0, 16)

function errMsg(e: unknown, fallback: string): string {
  if (e instanceof ApiError) return e.message
  if (e instanceof Error) return e.message
  return fallback
}

async function fetchChannels() {
  loading.value = true
  try {
    const res = await api.get<ChannelsResponse>('/payment/channels')
    channels.value = res.channels ?? []
    summary.value = res.summary ?? null
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '加载支付渠道失败') })
  } finally {
    loading.value = false
  }
}

// ── 启用/停用切换 ─────────────────────────────────
async function toggleEnabled(c: Channel) {
  if (c.requires_config && !c.is_enabled && !c.config_complete) {
    toast({
      tone: 'error',
      text: `启用 ${c.name} 前请先填写完整配置`,
    })
    openConfig(c)
    return
  }
  togglingKey.value = c.channel_key
  try {
    await api.patch(`/payment/channels/${c.channel_key}`, {
      is_enabled: !c.is_enabled,
    })
    toast({
      tone: 'success',
      text: `${c.name}已${!c.is_enabled ? '启用' : '停用'}`,
    })
    await fetchChannels()
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '切换失败') })
  } finally {
    togglingKey.value = null
  }
}

// ── 配置编辑 ───────────────────────────────────────
function openConfig(c: Channel) {
  configChannel.value = c
  // 重置表单:非 password 字段从当前值预填,password 字段统一留空
  // (后端返回的是 ●●●●●● 脱敏值,直接回传会破坏配置)
  Object.keys(configForm).forEach((k) => delete configForm[k])
  for (const f of c.config_fields) {
    if (f.type === 'password') {
      configForm[f.key] = ''
    } else {
      configForm[f.key] = c.config[f.key] || ''
    }
  }
  configOpen.value = true
}

async function saveConfig() {
  if (!configChannel.value) return
  const c = configChannel.value
  // 拼 patch payload:
  //   - password 字段:空 = 不改(完全不发,后端会保留旧值)
  //   - 其他字段:完整发(后端用空字符串删字段,已填的覆盖旧值)
  const config: Record<string, string> = {}
  for (const f of c.config_fields) {
    const v = (configForm[f.key] || '').trim()
    if (f.type === 'password' && !v) {
      // 空密码字段 = 保持当前值,跳过
      continue
    }
    config[f.key] = v
  }
  configSaving.value = true
  try {
    await api.patch(`/payment/channels/${c.channel_key}`, { config })
    toast({ tone: 'success', text: `${c.name}配置已保存` })
    configOpen.value = false
    await fetchChannels()
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '保存配置失败') })
  } finally {
    configSaving.value = false
  }
}

// ── 连通性测试 ───────────────────────────────────
async function testChannel(c: Channel) {
  testingKey.value = c.channel_key
  try {
    const res = await api.post<TestResponse>(`/payment/channels/${c.channel_key}/test`)
    const tone =
      res.test_result === 'success'
        ? 'success'
        : res.test_result === 'warning' || res.test_result === 'incomplete'
        ? 'info'
        : 'error'
    toast({ tone, text: `${c.name}: ${res.message}` })
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '测试失败') })
  } finally {
    testingKey.value = null
  }
}

// ── 派生展示 ───────────────────────────────────────
const onlineCount = computed(
  () => channels.value.filter((c) => c.requires_network).length,
)
const offlineCount = computed(
  () => channels.value.filter((c) => !c.requires_network).length,
)

onMounted(fetchChannels)
</script>

<template>
  <div class="pc-view">
    <header class="pc-header">
      <h1 class="title-l">支付渠道</h1>
      <Chip v-if="summary">
        共 {{ summary.total }} 个 · 已启用 {{ summary.enabled }}
      </Chip>
      <Chip tone="info">在线 {{ onlineCount }}</Chip>
      <Chip tone="accent">离线 {{ offlineCount }}</Chip>
    </header>

    <p class="meta pc-tip">
      离线渠道(现金 / 银行转账 / POS)无需配置即可使用。在线渠道(微信 / 支付宝)
      需先填写商户密钥才能启用。
    </p>

    <div v-if="loading" class="empty">
      <div class="skel" style="height: 240px; width: 100%"></div>
    </div>

    <div v-else class="pc-grid">
      <GlassPanel
        v-for="c in channels"
        :key="c.channel_key"
        variant="card"
        class="pc-card"
        :class="{ 'pc-card--enabled': c.is_enabled }"
      >
        <template #header>
          <span class="pc-icon" :style="{ background: c.color || '#64748b' }">
            {{ ICON_FALLBACK[c.channel_key] || '•' }}
          </span>
          <span class="title-s">{{ c.name }}</span>
          <Chip
            v-if="c.is_enabled"
            tone="success"
            style="margin-left: auto"
          >
            已启用
          </Chip>
          <Chip v-else style="margin-left: auto">未启用</Chip>
        </template>

        <p class="body-s pc-desc">{{ c.description }}</p>

        <div class="pc-flags">
          <Chip :tone="c.requires_network ? 'info' : 'accent'">
            {{ c.requires_network ? '需联网' : '无需联网' }}
          </Chip>
          <Chip v-if="c.requires_config" :tone="c.config_complete ? 'success' : 'danger'">
            {{ c.config_complete ? '配置完整' : '配置缺失' }}
          </Chip>
        </div>

        <p v-if="c.updated_at" class="meta pc-updated">
          上次更新 {{ fmtUpdated(c.updated_at) }}<span v-if="c.updated_by"> · 由 {{ c.updated_by }}</span>
        </p>

        <div class="pc-actions">
          <Btn
            size="sm"
            :variant="c.is_enabled ? 'outline' : 'primary'"
            :loading="togglingKey === c.channel_key"
            @click="toggleEnabled(c)"
          >
            {{ c.is_enabled ? '停用' : '启用' }}
          </Btn>
          <Btn
            v-if="c.requires_config"
            size="sm"
            variant="ghost"
            @click="openConfig(c)"
          >
            {{ c.config_complete ? '修改配置' : '填写配置' }}
          </Btn>
          <Btn
            size="sm"
            variant="ghost"
            :loading="testingKey === c.channel_key"
            @click="testChannel(c)"
          >
            测试连通性
          </Btn>
        </div>
      </GlassPanel>
    </div>

    <!-- ─────── 配置 Dialog ─────── -->
    <Dialog
      v-model="configOpen"
      :title="configChannel ? `配置 · ${configChannel.name}` : '配置'"
    >
      <div v-if="configChannel" class="pc-config">
        <p class="meta">{{ configChannel.description }}</p>

        <div v-if="configChannel.requires_network" class="pc-warn">
          <strong>提示</strong>：此渠道需联网调用第三方 API。请确保服务器
          可访问公网，且回调地址(notify_url)是外网可达的 HTTPS。
        </div>

        <Field
          v-for="f in configChannel.config_fields"
          :key="f.key"
          v-model="configForm[f.key]"
          :label="f.label + (f.required ? ' *' : '')"
          :type="f.type"
          :hint="f.type === 'password' && configChannel.config[f.key] ? '已配置·留空保持当前值' : f.hint"
          :placeholder="f.type === 'password' ? '••••••••(已配置)' : ''"
        />
      </div>
      <template #actions>
        <Btn variant="ghost" :disabled="configSaving" @click="configOpen = false">
          取消
        </Btn>
        <Btn variant="primary" :loading="configSaving" @click="saveConfig">
          保存配置
        </Btn>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.pc-view { display: grid; gap: var(--sp-4, 16px); }
.pc-header { display: flex; align-items: center; gap: var(--sp-2, 8px); flex-wrap: wrap; }
.pc-tip { margin: 0; }

.pc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--sp-3, 12px);
}

.pc-card {
  display: grid;
  gap: var(--sp-2, 8px);
  transition: border-color 120ms ease, box-shadow 120ms ease;
}
.pc-card--enabled {
  border-color: rgba(20, 184, 166, 0.4);
  box-shadow: 0 8px 24px rgba(20, 184, 166, 0.08);
}

.pc-icon {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.pc-desc { margin: 0; color: var(--ink-3); }
.pc-flags { display: flex; flex-wrap: wrap; gap: 6px; }
.pc-updated { margin: 0; }

.pc-actions {
  display: flex;
  gap: var(--sp-2, 8px);
  flex-wrap: wrap;
  margin-top: var(--sp-2, 8px);
}

.pc-config { display: grid; gap: var(--sp-3, 12px); max-width: 480px; }
.pc-warn {
  padding: var(--sp-2, 8px) var(--sp-3, 12px);
  border-radius: var(--r-s, 10px);
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  font: 400 var(--fz-sm, 13px) / 1.5 var(--font-ui);
}

@media (max-width: 640px) {
  .pc-header { flex-wrap: wrap; }
  .pc-header .title-l { font-size: 22px; }
  .pc-grid { grid-template-columns: 1fr; gap: 10px; }
  .pc-card { padding: 14px !important; }
  .pc-actions { flex-wrap: wrap; }
  .pc-actions .btn {
    flex: 1 1 calc(50% - 4px);
    min-width: 0;
  }
}
</style>
