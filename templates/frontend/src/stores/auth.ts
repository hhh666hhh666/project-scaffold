import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/**
 * 登录态的唯一真相源：token 只从这里读、往这里写。
 *
 * ⚠️ 存在 localStorage 意味着任何页面脚本都能读到它——**页面一旦有 XSS，token 就会被拿走**。
 *    这是无状态 JWT 方案的固有取舍（后端没有刷新机制与 HttpOnly cookie）；
 *    要更进一步，得让后端改发 HttpOnly cookie。
 *
 * ⚠️ 存储键带项目名前缀：本机开发时几个脚手架项目常常共用 localhost:5173，
 *    同源共享 localStorage，键名写死会让 A 项目的 token 被 B 项目读到。
 */
const STORAGE_KEY = '${PROJECT_NAME}:token'

function readToken(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? ''
  } catch {
    // 隐私模式等场景下存储不可用：退化为仅内存，不在这里崩溃。
    return ''
  }
}

function writeToken(value: string): void {
  try {
    if (value) {
      localStorage.setItem(STORAGE_KEY, value)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // 同上：写不进去就只保留内存里的值，本次会话仍然可用。
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(readToken())
  const isLoggedIn = computed(() => token.value !== '')

  function setToken(value: string): void {
    token.value = value
    writeToken(value)
  }

  function clearToken(): void {
    token.value = ''
    writeToken('')
  }

  return { token, isLoggedIn, setToken, clearToken }
})
