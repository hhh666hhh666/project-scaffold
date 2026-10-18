import { createRouter, createWebHistory, type Router, type RouterHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import { installAuthGuard } from './guard'

declare module 'vue-router' {
  interface RouteMeta {
    /** 浏览器标签页标题 */
    title?: string
    /** 为 true 时要求已登录；没有 login 路由时守卫会报错（见 guard.ts） */
    requiresAuth?: boolean
  }
}

/**
 * 路由工厂：默认用浏览器历史，测试可传入内存历史。
 * 守卫随路由一起装上，避免「生产装了、测试没装」这种漂移。
 */
export function createAppRouter(history: RouterHistory = createWebHistory()): Router {
  const router = createRouter({
    history,
    routes: [
      { path: '/', name: 'home', component: HomeView, meta: { title: '首页' } }
    ]
  })

  // 路由 meta.title 同时喂浏览器标签页标题
  router.afterEach((to) => {
    const title = to.meta.title ?? ''
    document.title = title ? `${title} · ${'${PROJECT_NAME}'}` : '${PROJECT_NAME}'
  })

  installAuthGuard(router)
  return router
}

export default createAppRouter()
