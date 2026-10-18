import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './styles/app.css'
import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from '@/api/request'

const app = createApp(App)

app.use(createPinia())
app.use(router)

/**
 * 收到「未登录」响应（信封 code = 401）后去哪：
 * token 已在请求层清掉，这里负责把用户带到登录页。
 * 登录页由使用者自己加（路由名必须是 login）；还没有就先报错，别静默失败。
 */
setUnauthorizedHandler((message) => {
  console.warn(`[auth] ${message}`)

  if (!router.hasRoute('login')) {
    console.error(
      '[auth] 收到未登录响应，但项目里没有名为 login 的路由；' +
        '请先添加登录页，并在登录成功后调用 useAuthStore().setToken(token)',
    )
    return
  }

  void router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
})

app.mount('#app')
