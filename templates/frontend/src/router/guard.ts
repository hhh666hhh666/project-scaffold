import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

/**
 * 登录守卫：只挡「没登录」，**不挡「没有数据权限」**——越权由服务端判定。
 *
 * 依赖前提：项目里要有一个名为 `login` 的路由。脚手架不提供登录页
 * （账号密码还是扫码完全取决于业务），但把机制留好：
 * 登录成功后调用 useAuthStore().setToken(token)，守卫就会放行。
 */

const LOGIN_ROUTE_NAME = 'login'

/**
 * 登录后要跳回的地址只允许站内路径。
 * 挡住 `//evil.com`、`https://evil.com` 这类把登录页当跳板的构造，
 * 否则登录完成后会把用户送去外站（开放重定向）。
 */
export function resolveRedirect(value: unknown): string {
  if (typeof value !== 'string') return '/'
  if (!value.startsWith('/') || value.startsWith('//')) return '/'
  return value
}

export function installAuthGuard(router: Router): void {
  router.beforeEach((to) => {
    if (!to.meta.requiresAuth) return true
    if (useAuthStore().token) return true

    if (!router.hasRoute(LOGIN_ROUTE_NAME)) {
      // 静默失败会让「点了要登录的页面没反应」，这里宁可抛错让人立刻看到。
      throw new Error(
        '路由标记了 requiresAuth，但项目里没有名为 login 的路由；请先添加登录页并在登录成功后调用 useAuthStore().setToken(token)',
      )
    }

    return { name: LOGIN_ROUTE_NAME, query: { redirect: to.fullPath } }
  })
}
