import { get } from './request'

export interface HelloVO {
  message: string
  fromBackend: boolean
}

/**
 * 示例接口：首页用它验证「前后端通了」。接手后换成你自己的领域模块，
 * 并把 example 相关的前后端代码一起删掉。
 *
 * 返回类型就是信封里的 data——解包在请求层完成了，这里不用再取 .data。
 */
export function hello(name?: string): Promise<HelloVO> {
  return get<HelloVO>('/example/hello', { params: { name } })
}
