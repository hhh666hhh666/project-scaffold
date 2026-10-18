/**
 * 后端业务错误：HTTP 状态码是 200，但信封里的 code 不是 0 时抛出。
 *
 * 与网络错误区分开：断网、超时等由 axios 抛原生错误（不带 code），
 * 用 isApiError 判断，页面才能区分「请求没发出去」和「后端说不行」。
 */
export class ApiError extends Error {
  readonly code: number

  constructor(code: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}
