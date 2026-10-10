import http from './request'

export interface HelloVO {
  message: string
  fromBackend: boolean
}

/**
 * 示例接口：首页用它验证「前后端通了」。接手后换成你自己的领域模块，
 * 并把 example 相关的前后端代码一起删掉。
 */
export async function hello(name?: string): Promise<HelloVO> {
  const res = await http.get('/example/hello', { params: { name } })
  return res.data
}
