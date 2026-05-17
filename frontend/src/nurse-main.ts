import { createApp } from 'vue'
import { createPinia } from 'pinia'
import NurseApp from './nurse-views/NurseApp.vue'
import nurseRouter from './nurse-router'

// 复用管理端的设计系统 —— RFC §8: 0 改动
import '@design/tokens.css'
import '@design/glass.css'
import '@design/ui.css'
import '@design/mobile.css'

const app = createApp(NurseApp)
app.use(createPinia())
app.use(nurseRouter)
app.mount('#app')
