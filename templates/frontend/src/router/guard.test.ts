import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import { installAuthGuard, resolveRedirect } from './guard'
import { useAuthStore } from '@/stores/auth'

const Blank = { render: () => null }

function makeRouter(withLogin: boolean): Router {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: Blank },
      { path: '/secret', name: 'secret', component: Blank, meta: { requiresAuth: true } },
      ...(withLogin ? [{ path: '/login', name: 'login', component: Blank }] : [])
    ]
  })
  installAuthGuard(router)
  return router
}

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

describe('resolveRedirect', () => {
  it('站内路径原样保留', () => {
    expect(resolveRedirect('/orders?page=2')).toBe('/orders?page=2')
  })

  it.each([['//evil.com'], ['https://evil.com'], [''], [null], [42]])(
    '把危险或非法值退回首页：%s',
    (value) => {
      expect(resolveRedirect(value)).toBe('/')
    },
  )
})

describe('installAuthGuard', () => {
  it('公开路由不需要登录', async () => {
    const router = makeRouter(true)
    await router.push('/')

    expect(router.currentRoute.value.name).toBe('home')
  })

  it('未登录访问受保护路由时跳到 login 并带上原地址', async () => {
    const router = makeRouter(true)
    await router.push('/secret')

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/secret')
  })

  it('已登录直接放行', async () => {
    useAuthStore().setToken('abc')
    const router = makeRouter(true)
    await router.push('/secret')

    expect(router.currentRoute.value.name).toBe('secret')
  })

  it('没有 login 路由时抛错，而不是静默失败', async () => {
    const router = makeRouter(false)
    router.onError(() => {
      // 吞掉 vue-router 自己的错误日志，断言只看导航 promise。
    })

    await expect(router.push('/secret')).rejects.toThrow(/没有名为 login 的路由/)
  })
})
