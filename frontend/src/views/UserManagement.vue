<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Btn, Field, GlassPanel, Chip } from '../components'
import { useToast } from '../composables/useToast'
import { api } from '../api'

interface UserInfo { user_id: string; username: string; display_name?: string; role: string; active?: boolean }
interface RoleInfo { role_key: string; display_name: string; system: boolean; permissions: string[]; description?: string }

const { push: toast } = useToast()
const newUsername = ref(''); const newDisplayName = ref(''); const newRole = ref('nurse'); const creating = ref(false)
const users = ref<UserInfo[]>([]); const roles = ref<RoleInfo[]>([]); const loadingUsers = ref(false)

async function loadUsers() {
  loadingUsers.value = true
  try { const res = await api.get<any>('/auth/users'); users.value = res.users ?? res ?? [] }
  catch (e: any) { if (e.status === 403 || e.status === 401) toast({ tone: 'warning', text: '需要 admin 权限' }) }
  finally { loadingUsers.value = false }
}
async function loadRoles() {
  try { const res = await api.get<any>('/auth/roles'); roles.value = res.roles ?? [] } catch {}
}
async function createUser() {
  if (!newUsername.value.trim()) { toast({ tone: 'warning', text: '用户名不能为空' }); return }
  creating.value = true
  try {
    await api.post('/auth/users', { username: newUsername.value.trim(), display_name: newDisplayName.value.trim() || undefined, role: newRole.value })
    toast({ tone: 'success', text: `用户 ${newUsername.value} 创建成功` }); newUsername.value = ''; newDisplayName.value = ''; loadUsers()
  } catch (e: any) { toast({ tone: 'error', text: e.message ?? '创建失败' }) }
  finally { creating.value = false }
}
async function issueToken(userId: string, username: string) {
  const label = prompt(`为 ${username} 签发 Token，请输入标签：`, '默认')
  if (!label) return
  try {
    const res = await api.post<any>('/auth/tokens', { user_id: userId, label })
    alert(`Token 已签发（此后不再显示）：\n\n${res.token ?? res.plain_token ?? ''}`)
    toast({ tone: 'success', text: 'Token 已签发' })
  } catch (e: any) { toast({ tone: 'error', text: e.message ?? '签发失败' }) }
}
function roleChipTone(key: string) { if (key === 'admin') return 'warning'; if (key === 'nurse') return 'success'; return 'info' }
onMounted(() => { loadUsers(); loadRoles() })
</script>

<template>
  <div class="um-view">
    <GlassPanel variant="card">
      <template #header><span class="title-l">用户管理</span><p class="meta">管理系统用户和 API Token（admin 专属）</p></template>
      <h3 class="section-label">创建用户</h3>
      <div class="form-grid cols-3">
        <Field v-model="newUsername" label="用户名" required placeholder="wang_nurse" />
        <Field v-model="newDisplayName" label="显示名" placeholder="王护士" />
        <div class="field-group"><span class="field-label">角色 *</span>
          <select v-model="newRole" class="field">
            <option v-for="r in roles" :key="r.role_key" :value="r.role_key">{{ r.display_name }}（{{ r.role_key }}）</option>
            <option v-if="roles.length === 0" value="nurse">nurse</option>
          </select>
        </div>
      </div>
      <Btn variant="primary" size="sm" :loading="creating" @click="createUser" style="margin-top: 12px;">创建用户</Btn>

      <h3 class="section-label" style="margin-top: var(--sp-5);">已有用户</h3>
      <div v-if="users.length === 0 && !loadingUsers" class="empty"><p class="empty-title">暂无用户</p></div>
      <div v-else class="um-list">
        <div v-for="u in users" :key="u.user_id" class="um-row">
          <div class="um-info">
            <strong>{{ u.username }}</strong><span v-if="u.display_name"> · {{ u.display_name }}</span>
            <Chip :tone="roleChipTone(u.role)" style="margin-left: 6px;">{{ u.role }}</Chip>
            <Chip v-if="u.active === false" tone="danger" style="margin-left: 4px;">已停用</Chip>
          </div>
          <Btn variant="ghost" size="sm" @click="issueToken(u.user_id, u.username)">签发 Token</Btn>
        </div>
      </div>
    </GlassPanel>

    <GlassPanel v-if="roles.length > 0">
      <template #header><span class="title-s">角色权限</span></template>
      <div class="um-roles">
        <div v-for="r in roles" :key="r.role_key" class="um-role-card">
          <div class="um-role-head">
            <strong>{{ r.display_name }}</strong><span class="meta">{{ r.role_key }}</span>
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
  </div>
</template>

<style scoped>
.um-view { display: grid; gap: var(--sp-4, 16px); max-width: 900px; }
.section-label { font: 600 var(--fz-sm, 13px)/1.4 var(--font-ui); color: var(--ink-2); margin: var(--sp-3, 12px) 0 var(--sp-2, 8px); }
.form-grid { display: grid; gap: var(--sp-2, 8px); }
.form-grid.cols-3 { grid-template-columns: repeat(3, 1fr); }
.field-group { display: flex; flex-direction: column; gap: 4px; }
.field-label { font: 600 var(--fz-xs, 11px)/1.4 var(--font-ui); color: var(--ink-3); }
.um-list { display: grid; gap: 4px; }
.um-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 8px; background: rgba(15,23,42,0.02); }
.um-info { display: flex; align-items: center; flex-wrap: wrap; gap: 2px; }
.um-roles { display: grid; gap: 12px; }
.um-role-card { padding: 12px; border-radius: 10px; background: rgba(15,23,42,0.02); border-left: 3px solid var(--accent); }
.um-role-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.um-perms { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
@media (max-width: 640px) { .form-grid.cols-3 { grid-template-columns: 1fr; } }
</style>
