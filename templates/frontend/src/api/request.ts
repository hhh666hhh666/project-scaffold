import axios from 'axios'

/**
 * 全局 HTTP 封装：baseURL、超时、统一解包与错误提示都收在这里，组件不直接碰 axios。
 *
 * ⚠️ 响应拦截器直接返回「信封里的 data」——调用方拿到的是业务数据，
 *    信封（code / message / timestamp）在这里就被剥掉了。
 */
const http = axios.create({
  baseURL: '/api',
  timeout: 15000
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => Promise.reject(error)
)

export default http
