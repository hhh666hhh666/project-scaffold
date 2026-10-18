import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from './auth'

const STORAGE_KEY = '${PROJECT_NAME}:token'

beforeEach(() => {
  localStorage.clear()
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('auth store', () => {
  it('初始化时从 localStorage 读取已有 token', () => {
    localStorage.setItem(STORAGE_KEY, 'saved')
    setActivePinia(createPinia())

    expect(useAuthStore().token).toBe('saved')
  })

  it('setToken 同时更新内存与存储', () => {
    const auth = useAuthStore()
    auth.setToken('abc')

    expect(auth.token).toBe('abc')
    expect(auth.isLoggedIn).toBe(true)
    expect(localStorage.getItem(STORAGE_KEY)).toBe('abc')
  })

  it('clearToken 同时清掉内存与存储', () => {
    const auth = useAuthStore()
    auth.setToken('abc')
    auth.clearToken()

    expect(auth.token).toBe('')
    expect(auth.isLoggedIn).toBe(false)
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('空串不当作登录态', () => {
    localStorage.setItem(STORAGE_KEY, '')
    setActivePinia(createPinia())

    expect(useAuthStore().isLoggedIn).toBe(false)
  })

  it('存储不可用时退化为仅内存，不崩溃', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    const auth = useAuthStore()

    expect(() => auth.setToken('abc')).not.toThrow()
    expect(auth.token).toBe('abc')
  })
})
