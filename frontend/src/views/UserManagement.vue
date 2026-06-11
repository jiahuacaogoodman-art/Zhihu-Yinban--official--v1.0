<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Btn, Field, GlassPanel, Chip, Dialog } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

interface UserInfo {
  user_id: string
  username: string
  display_name?: string
  role: string
  active?: boolean
}

interface RoleInfo {
  role_key: string
  display_name: string
  system: boolean
  permissions: string[]
  description?: string
}

interface ApiKeyInfo {
  key_id: string
  user_id: string
  username: string
  label: string
  token_prefix: string
  created_at: string
  last_used_at: string
  revoked_at: string
}

interface UserListResponse {
  users: UserInfo[]
}

interface RoleListResponse {
  roles: RoleInfo[]
}

interface TokenListResponse {
  keys: ApiKeyInfo[]
}

interface CreateTokenResponse {
  token?: string
  plain_token?: string
  key?: ApiKeyInfo
}

const { push: toast } = useToast()

const newUsername = ref('')
const newDisplayName = ref('')
const newRole = ref('nurse')
const creating = ref(false)

const users = ref<UserInfo[]>([])
const roles = ref<RoleInfo[]>([])
const tokens = ref<ApiKeyInfo[]>([])
const loadingUsers = ref(false)
const loadingTokens = ref(false)
const busyUserId = ref<string | null>(null)
const busyTokenId = ref<string | null>(null)

const tokenOpen = ref(false)
const tokenUser = ref<UserInfo | null>(null)
const tokenLabel = ref('默认')
const tokenSaving = ref(false)
const issuedToken = ref('')

const activeTokenCount = computed(() => tokens.value.filter((t) => !t.revoked_at).length)
const activeUserCount = computed(() => users.value.filter((u) => u.active !== false).length)

function errMsg(e: unknown, fallback: string): string {
  if (e instanceof Error) return e.message
  return fallback
}

function roleChipTone(key: string): 'success' | 'warning' | 'info' {
  if (key === 'admin') return 'warning'
  if (key === 'nurse') return 'success'
  return 'info'
}

function roleName(key: string): string {
  return roles.value.find((r) => r.role_key === key)?.display_name ?? key
}

function fmtTime(value?: string): string {
  if (!value) return '从未'
  return value.replace('T', ' ').slice(0, 16)
}

async function loadUsers() {
  loadingUsers.value = true
  try {
    const res = await api.get<UserListResponse>('/auth/users?include_inactive=true')
    users.value = res.users ?? []
  } catch (e: unknown) {
    users.value = []
    toast({ tone: 'warning', text: errMsg(e, '需要 users.manage 权限') })
  } finally {
    loadingUsers.value = false
  }
}

async function loadRoles() {
  try {
    const res = await api.get<RoleListResponse>('/auth/roles')
    roles.value = res.roles ?? []
  } catch {
    roles.value = []
  }
}

async function loadTokens() {
  loadingTokens.value = true
  try {
    const res = await api.get<TokenListResponse>('/auth/tokens?include_revoked=true')
    tokens.value = res.keys ?? []
  } catch (e: unknown) {
    tokens.value = []
    toast({ tone: 'warning', text: errMsg(e, '需要 tokens.manage 权限') })
  } finally {
    loadingTokens.value = false
  }
}

async function createUser() {
  if (!newUsername.value.trim()) {
    toast({ tone: 'warning', text: '用户名不能为空' })
    return
  }
  creating.value = true
  try {
    const username = newUsername.value.trim()
    await api.post('/auth/users', {
      username,
      display_name: newDisplayName.value.trim() || undefined,
      role: newRole.value,
    })
    toast({ tone: 'success', text: `用户 ${username} 创建成功` })
    newUsername.value = ''
    newDisplayName.value = ''
    await loadUsers()
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '创建失败') })
  } finally {
    creating.value = false
  }
}

function openIssueToken(user: UserInfo) {
  tokenUser.value = user
  tokenLabel.value = '默认'
  issuedToken.value = ''
  tokenOpen.value = true
}

function closeIssueToken() {
  tokenOpen.value = false
  tokenUser.value = null
  issuedToken.value = ''
}

async function submitIssueToken() {
  if (!tokenUser.value) return
  tokenSaving.value = true
  try {
    const res = await api.post<CreateTokenResponse>('/auth/tokens', {
      user_id: tokenUser.value.user_id,
      label: tokenLabel.value.trim() || '默认',
    })
    issuedToken.value = res.token ?? res.plain_token ?? ''
    toast({ tone: 'success', text: 'Token 已签发' })
    await loadTokens()
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '签发失败') })
  } finally {
    tokenSaving.value = false
  }
}

async function copyIssuedToken() {
  if (!issuedToken.value) return
  try {
    await navigator.clipboard?.writeText(issuedToken.value)
    toast({ tone: 'success', text: 'Token 已复制' })
  } catch {
    toast({ tone: 'warning', text: '复制失败，请手动选中文本' })
  }
}

async function deactivateUser(user: UserInfo) {
  if (user.active === false) return
  if (typeof window !== 'undefined' && !window.confirm(`确定停用用户 ${user.username} 吗？其 Token 会同步吊销。`)) {
    return
  }
  busyUserId.value = user.user_id
  try {
    await api.delete(`/auth/users/${encodeURIComponent(user.user_id)}`)
    toast({ tone: 'success', text: '用户已停用' })
    await Promise.all([loadUsers(), loadTokens()])
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '停用失败') })
  } finally {
    busyUserId.value = null
  }
}

async function revokeToken(token: ApiKeyInfo) {
  if (token.revoked_at) return
  if (typeof window !== 'undefined' && !window.confirm(`确定吊销 ${token.username} 的 Token 吗？`)) {
    return
  }
  busyTokenId.value = token.key_id
  try {
    await api.delete(`/auth/tokens/${encodeURIComponent(token.key_id)}`)
    toast({ tone: 'success', text: 'Token 已吊销' })
    await loadTokens()
  } catch (e: unknown) {
    toast({ tone: 'error', text: errMsg(e, '吊销失败') })
  } finally {
    busyTokenId.value = null
  }
}

onMounted(() => {
  loadUsers()
  loadRoles()
  loadTokens()
})
</script>

<template>
  <div class="um-view">
    <GlassPanel variant="card">
      <template #header>
        <div class="um-panel-head">
          <div>
            <span class="title-l">用户管理</span>
            <p class="meta">管理系统用户和 API Token（admin 专属）</p>
          </div>
          <div class="um-head-chips">
            <Chip tone="success">启用用户 {{ activeUserCount }}</Chip>
            <Chip tone="info">有效 Token {{ activeTokenCount }}</Chip>
          </div>
        </div>
      </template>

      <h3 class="section-label">创建用户</h3>
      <div class="form-grid cols-3">
        <Field v-model="newUsername" label="用户名" required placeholder="wang_nurse" />
        <Field v-model="newDisplayName" label="显示名" placeholder="王护士" />
        <Field v-model="newRole" label="角色 *" type="select">
          <option v-for="r in roles" :key="r.role_key" :value="r.role_key">
            {{ r.display_name }}（{{ r.role_key }}）
          </option>
          <option v-if="roles.length === 0" value="nurse">nurse</option>
        </Field>
      </div>
      <Btn variant="primary" size="sm" :loading="creating" class="um-create" @click="createUser">
        创建用户
      </Btn>

      <div class="um-section-head">
        <h3 class="section-label">已有用户</h3>
        <Btn variant="ghost" size="sm" :loading="loadingUsers" @click="loadUsers">刷新</Btn>
      </div>
      <div v-if="users.length === 0 && !loadingUsers" class="empty">
        <p class="empty-title">暂无用户</p>
      </div>
      <div v-else class="um-list">
        <div v-for="u in users" :key="u.user_id" class="um-row">
          <div class="um-info">
            <strong>{{ u.username }}</strong>
            <span v-if="u.display_name"> · {{ u.display_name }}</span>
            <Chip :tone="roleChipTone(u.role)" class="um-chip">{{ roleName(u.role) }}</Chip>
            <Chip v-if="u.active === false" tone="danger" class="um-chip">已停用</Chip>
          </div>
          <div class="um-row-actions">
            <Btn
              variant="ghost"
              size="sm"
              :disabled="u.active === false"
              @click="openIssueToken(u)"
            >
              签发 Token
            </Btn>
            <Btn
              variant="danger"
              size="sm"
              :disabled="u.active === false"
              :loading="busyUserId === u.user_id"
              @click="deactivateUser(u)"
            >
              停用
            </Btn>
          </div>
        </div>
      </div>
    </GlassPanel>

    <GlassPanel variant="card">
      <template #header>
        <div class="um-panel-head">
          <span class="title-s">API Token</span>
          <Btn variant="ghost" size="sm" :loading="loadingTokens" @click="loadTokens">刷新</Btn>
        </div>
      </template>
      <div v-if="tokens.length === 0 && !loadingTokens" class="empty">
        <p class="empty-title">暂无 Token</p>
      </div>
      <div v-else class="um-list">
        <div v-for="t in tokens" :key="t.key_id" class="um-row token-row">
          <div class="um-info">
            <strong>{{ t.label || '未命名 Token' }}</strong>
            <span class="meta"> · {{ t.username }} · {{ t.token_prefix }}…</span>
            <Chip :tone="t.revoked_at ? 'danger' : 'success'" class="um-chip">
              {{ t.revoked_at ? '已吊销' : '有效' }}
            </Chip>
          </div>
          <div class="um-token-meta">
            <span>创建 {{ fmtTime(t.created_at) }}</span>
            <span>最近使用 {{ fmtTime(t.last_used_at) }}</span>
          </div>
          <Btn
            variant="danger"
            size="sm"
            :disabled="!!t.revoked_at"
            :loading="busyTokenId === t.key_id"
            @click="revokeToken(t)"
          >
            吊销
          </Btn>
        </div>
      </div>
    </GlassPanel>

    <GlassPanel v-if="roles.length > 0">
      <template #header><span class="title-s">角色权限</span></template>
      <div class="um-roles">
        <div v-for="r in roles" :key="r.role_key" class="um-role-card">
          <div class="um-role-head">
            <strong>{{ r.display_name }}</strong>
            <span class="meta">{{ r.role_key }}</span>
            <Chip :tone="r.system ? 'warning' : 'info'">{{ r.system ? '系统内置' : '自定义' }}</Chip>
          </div>
          <p v-if="r.description" class="meta">{{ r.description }}</p>
          <div class="um-perms">
            <Chip v-for="p in r.permissions" :key="p" tone="accent">{{ p }}</Chip>
            <span v-if="r.permissions.length === 0" class="meta">（无权限）</span>
          </div>
        </div>
      </div>
    </GlassPanel>

    <Dialog v-model="tokenOpen" :title="tokenUser ? `签发 Token · ${tokenUser.username}` : '签发 Token'">
      <div class="um-token-dialog">
        <Field
          v-model="tokenLabel"
          label="标签"
          placeholder="护工端 / 管理后台"
          :disabled="!!issuedToken"
        />
        <div v-if="issuedToken" class="um-token-secret">
          <p class="meta">Token 明文仅显示一次</p>
          <code>{{ issuedToken }}</code>
          <Btn variant="outline" size="sm" @click="copyIssuedToken">复制</Btn>
        </div>
      </div>
      <template #actions>
        <Btn variant="ghost" :disabled="tokenSaving" @click="closeIssueToken">
          {{ issuedToken ? '完成' : '取消' }}
        </Btn>
        <Btn
          v-if="!issuedToken"
          variant="primary"
          :loading="tokenSaving"
          @click="submitIssueToken"
        >
          签发
        </Btn>
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.um-view {
  display: grid;
  gap: var(--sp-4, 16px);
  max-width: 980px;
}

.um-panel-head,
.um-section-head,
.um-row-actions,
.um-head-chips,
.um-token-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.um-panel-head {
  justify-content: space-between;
  width: 100%;
}

.um-section-head {
  justify-content: space-between;
  margin-top: var(--sp-5, 20px);
}

.section-label {
  font: 600 var(--fz-sm, 13px) / 1.4 var(--font-ui);
  color: var(--ink-2);
  margin: var(--sp-3, 12px) 0 var(--sp-2, 8px);
}

.um-section-head .section-label {
  margin: 0;
}

.form-grid {
  display: grid;
  gap: var(--sp-2, 8px);
}

.form-grid.cols-3 {
  grid-template-columns: repeat(3, 1fr);
}

.um-create {
  margin-top: 12px;
}

.um-list {
  display: grid;
  gap: 6px;
}

.um-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.02);
}

.token-row {
  grid-template-columns: minmax(0, 1.1fr) minmax(180px, auto) auto;
}

.um-info {
  display: flex;
  align-items: center;
  min-width: 0;
  flex-wrap: wrap;
  gap: 2px;
}

.um-chip {
  margin-left: 4px;
}

.um-token-meta {
  justify-content: flex-end;
  color: var(--ink-3);
  font: 500 var(--fz-xs, 11px) / 1.4 var(--font-ui);
}

.um-roles {
  display: grid;
  gap: 12px;
}

.um-role-card {
  padding: 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.02);
  border-left: 3px solid var(--accent);
}

.um-role-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.um-perms {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.um-token-dialog {
  display: grid;
  gap: 12px;
  min-width: min(520px, 72vw);
}

.um-token-secret {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.04);
}

.um-token-secret code {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: 600 12px / 1.5 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: var(--ink-1);
}

@media (max-width: 760px) {
  .form-grid.cols-3,
  .um-row,
  .token-row {
    grid-template-columns: 1fr;
  }

  .um-row-actions,
  .um-token-meta {
    justify-content: flex-start;
  }

  .um-token-dialog {
    min-width: 0;
  }
}
</style>