import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView, meta: { title: '首页' } }
  ]
})

// 路由 meta.title 同时喂浏览器标签页标题
router.afterEach((to) => {
  const title = (to.meta.title as string | undefined) ?? ''
  document.title = title ? `${title} · ${'${PROJECT_NAME}'}` : '${PROJECT_NAME}'
})

export default router
