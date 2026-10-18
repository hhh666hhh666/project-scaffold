import type { AxiosAdapter, AxiosResponse } from 'axios'
import { afterEach, describe, expect, it } from 'vitest'
import http from './request'
import { hello } from './example'

/**
 * 请求层的样例测试——它是「测试能跑起来」的活证据，也是这一层该测什么的示范。
 *
 * 只测**静默错误**：错了不报错、只会一直错下去的那种逻辑。
 * 这里测的是对调用方的承诺（拿到的数据形状、错误会不会被吞），不测拦截器内部怎么实现，
 * 所以以后重构 request.ts 不必改这些用例。
 *
 * 网络用假适配器替掉：不发出真实请求，也不需要后端或 mock 服务。
 */

const originalAdapter = http.defaults.adapter

function respondWith(envelope: unknown): AxiosAdapter {
  return async (config) =>
    ({
      data: envelope,
      status: 200,
      statusText: 'OK',
      headers: {},
      config
    }) as AxiosResponse
}

afterEach(() => {
  http.defaults.adapter = originalAdapter
})

describe('example.hello', () => {
  it('把后端信封里的 data 交给调用方', async () => {
    http.defaults.adapter = respondWith({
      code: 0,
      message: 'ok',
      data: { message: 'hello', fromBackend: true },
      timestamp: 1
    })

    await expect(hello('world')).resolves.toEqual({ message: 'hello', fromBackend: true })
  })

  it('网络错误向外抛出，不被吞掉', async () => {
    http.defaults.adapter = async () => {
      throw new Error('network down')
    }

    await expect(hello()).rejects.toThrow('network down')
  })
})
