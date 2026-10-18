import axios, { type AxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from './error'

/**
 * 全局 HTTP 封装：baseURL、超时、token 注入、响应解包与参数序列化都收在这里，
 * 组件不直接碰 axios。
 *
 * ⚠️ 后端的约定是「成功和失败都是 HTTP 200，成败只看信封里的 code」。
 *    所以这里不能只看 HTTP 状态码：code 不是 0 就抛 ApiError，调用方 await 就会 reject。
 *    真正的网络错误（断网、超时）保持 axios 原生错误原样抛出，不被包装。
 */

/** 与后端 ResultCode 保持一致；改这里之前先改后端枚举与 API.md。 */
const SUCCESS_CODE = 0
const UNAUTHORIZED_CODE = 401
const INVALID_RESPONSE_CODE = -1

interface Envelope<T = unknown> {
  code: number
  message?: string
  data?: T
  timestamp?: number
}

type UnauthorizedHandler = (message: string) => void

let unauthorizedHandler: UnauthorizedHandler | null = null

/** 由 main.ts 注册「收到未登录响应后去哪里」；注册前 401 只清 token、不跳转。 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler
}

/**
 * 数组参数必须摊成重复参数名（`tagIds=1&tagIds=2`），后端才认。
 * axios 默认会序列化成 `tagIds[]=1&tagIds[]=2`，筛选条件会**静默失效**。
 * null / undefined 直接跳过，不产生空参数。
 */
export function serializeParams(params: Record<string, unknown>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== undefined && item !== null) search.append(key, String(item))
      }
    } else {
      search.append(key, String(value))
    }
  }
  return search.toString()
}

const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
  paramsSerializer: { serialize: (params) => serializeParams(params as Record<string, unknown>) }
})

http.interceptors.request.use((config) => {
  const token = useAuthStore().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  // axios 的类型把拦截器声明成「返回 AxiosResponse」，但这里刻意把响应换成业务数据；
  // 返回类型只能放宽为 any，再由下面的 get/post 等泛型封装把真实类型告诉调用方。
  (response): any => {
    const raw = response.data

    // 下载类响应（blob / arraybuffer）不是信封，原样交给调用方。
    if (raw instanceof Blob || raw instanceof ArrayBuffer) {
      return raw
    }

    const envelope = raw as Envelope | null
    if (!envelope || typeof envelope !== 'object' || typeof envelope.code !== 'number') {
      // 反代 / 网关出错时可能返回 HTML 或空对象。宁可报错，也不要静默返回 undefined。
      throw new ApiError(INVALID_RESPONSE_CODE, '响应不是统一信封：可能被网关或反向代理改写了')
    }

    if (envelope.code === SUCCESS_CODE) {
      return envelope.data ?? null
    }

    if (envelope.code === UNAUTHORIZED_CODE) {
      useAuthStore().clearToken()
      unauthorizedHandler?.(envelope.message ?? '未登录或登录已过期')
    }

    throw new ApiError(envelope.code, envelope.message ?? '请求失败')
  },
  // HTTP 层的错误（断网、超时、CORS）原样抛出，页面用 axios.isAxiosError 判断。
  (error) => Promise.reject(error)
)

/** 类型化薄封装：拦截器已经把 data 解包出来，这里把返回类型如实告诉调用方。 */
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return (await http.get(url, config)) as unknown as T
}

export async function post<T>(url: string, body?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return (await http.post(url, body, config)) as unknown as T
}

export async function put<T>(url: string, body?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return (await http.put(url, body, config)) as unknown as T
}

export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return (await http.delete(url, config)) as unknown as T
}

/** 原始实例：测试用它替换适配器；业务代码请用上面的类型化封装。 */
export default http
