<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Btn, Field, GlassPanel } from '../components'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'

const authStore = useAuthStore()
const router = useRouter()
const { push: toast } = useToast()

const tokenInput = ref('')
const loading = ref(false)

async function handleLogin() {
  const t = tokenInput.value.trim()
  if (!t) return
  loading.value = true
  try {
    // 验证 token:尝试调一下 /health(不需要权限)或 /api/beds(需要)
    const res = await fetch('/api/beds', {
      headers: { 'X-Auth-Token': t },
    })
    if (res.status === 401) {
      toast({ tone: 'error', text: 'Token 无效,请检查后重试' })
      return
    }
    authStore.login(t)
    toast({ tone: 'success', text: '登录成功' })
    router.replace('/')
  } catch {
    toast({ tone: 'error', text: '网络错误' })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <GlassPanel variant="card" class="login-card">
      <template #header>
        <span class="title-l">智护银伴 · v2</span>
      </template>
      <p class="body-m" style="margin-bottom: var(--sp-4);">
        输入 API Token 登录管理端
      </p>
      <form @submit.prevent="handleLogin">
        <Field
          v-model="tokenInput"
          label="Auth Token"
          type="password"
          required
          placeholder="粘贴你的 AUTH_TOKEN"
        />
        <Btn
          variant="primary"
          type="submit"
          :loading="loading"
          :disabled="!tokenInput.trim()"
          style="margin-top: var(--sp-4); width: 100%;"
        >
          登录
        </Btn>
      </form>
      <p class="body-s" style="margin-top: var(--sp-3); color: var(--ink-4);">
        Token 由管理员通过环境变量 AUTH_TOKEN 或 /api/auth/users 接口配置。
      </p>
    </GlassPanel>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--sp-4, 16px);
}
.login-card {
  width: min(420px, 100%);
}
</style>
