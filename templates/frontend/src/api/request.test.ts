import { AxiosError, type AxiosAdapter, type AxiosResponse } from 'axios'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import http, { get, serializeParams, setUnauthorizedHandler } from './request'
import { ApiError, isApiError } from './error'
import { hello } from './example'
import { useAuthStore } from '@/stores/auth'

/**
 * 请求层的样例测试——它是「测试能跑起来」的活证据，也是这一层该测什么的示范。
 *
 * 只测**静默错误**：错了不报错、只会一直错下去的那种逻辑。
 * 这里测的是对调用方的承诺（拿到的数据形状、错误会不会被吞），不测拦截器内部怎么实现。
 *
 * 网络用假适配器替掉：不发出真实请求，也不需要后端或 mock 服务。
 */

const originalAdapter = http.defaults.adapter

function envelope(code: number, data: unknown = null, message = 'ok'): Record<string, unknown> {
  return { code, message, data, timestamp: 1 }
}

function respondWith(payload: unknown): AxiosAdapter {
  return async (config) =>
    ({
      data: payload,
      status: 200,
      statusText: 'OK',
      headers: {},
      config
    }) as AxiosResponse
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  setUnauthorizedHandler(null)
})

afterEach(() => {
  http.defaults.adapter = originalAdapter
  setUnauthorizedHandler(null)
})

describe('example.hello', () => {
  it('把后端信封里的 data 交给调用方', async () => {
    http.defaults.adapter = respondWith(envelope(0, { message: 'hello', fromBackend: true }))

    await expect(hello('world')).resolves.toEqual({ message: 'hello', fromBackend: true })
  })

  it('网络错误向外抛出，不被吞掉', async () => {
    http.defaults.adapter = async () => {
      throw new Error('network down')
    }

    await expect(hello()).rejects.toThrow('network down')
  })
})

describe('响应信封', () => {
  it('code 非 0 时抛出带业务码的 ApiError', async () => {
    http.defaults.adapter = respondWith(envelope(400, null, 'name 不能为空'))

    const error = await get('/x').catch((e: unknown) => e)
    expect(isApiError(error)).toBe(true)
    expect((error as ApiError).code).toBe(400)
    expect((error as ApiError).message).toBe('name 不能为空')
  })

  it('不是信封形状的响应直接报错，不静默返回 undefined', async () => {
    http.defaults.adapter = respondWith('<html>502 Bad Gateway</html>')

    await expect(get('/x')).rejects.toThrow('响应不是统一信封')
  })

  it('下载类响应原样返回', async () => {
    const blob = new Blob(['csv'])
    http.defaults.adapter = respondWith(blob)

    await expect(get('/export')).resolves.toBe(blob)
  })

  it('超时错误保持 axios 原生类型，不被包装成 ApiError', async () => {
    http.defaults.adapter = async () => {
      throw new AxiosError('timeout of 15000ms exceeded', 'ECONNABORTED')
    }

    const error = await get('/slow').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(AxiosError)
    expect(isApiError(error)).toBe(false)
  })
})

describe('未登录（code = 401）', () => {
  it('清掉 token、触发回调，并抛出 ApiError', async () => {
    const auth = useAuthStore()
    auth.setToken('stale-token')
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    http.defaults.adapter = respondWith(envelope(401, null, '登录已过期'))

    const error = await get('/secret').catch((e: unknown) => e)

    expect((error as ApiError).code).toBe(401)
    expect(auth.token).toBe('')
    expect(onUnauthorized).toHaveBeenCalledWith('登录已过期')
  })
})

describe('token 注入', () => {
  it('登录后请求自动带 Authorization 头', async () => {
    useAuthStore().setToken('abc')
    let captured = ''
    http.defaults.adapter = async (config) => {
      captured = String(config.headers.Authorization ?? '')
      return { data: envelope(0, null), status: 200, statusText: 'OK', headers: {}, config } as AxiosResponse
    }

    await get('/me')
    expect(captured).toBe('Bearer abc')
  })

  it('没有 token 时不带 Authorization 头', async () => {
    let captured: unknown = 'unset'
    http.defaults.adapter = async (config) => {
      captured = config.headers.Authorization
      return { data: envelope(0, null), status: 200, statusText: 'OK', headers: {}, config } as AxiosResponse
    }

    await get('/me')
    expect(captured).toBeUndefined()
  })
})

describe('serializeParams', () => {
  it('数组摊成重复参数名，后端才认', () => {
    const query = new URLSearchParams(serializeParams({ tagIds: [1, 2], name: 'demo' }))

    expect(query.getAll('tagIds')).toEqual(['1', '2'])
    expect(query.get('name')).toBe('demo')
  })

  it('跳过 null / undefined，不产生空参数', () => {
    expect(serializeParams({ a: null, b: undefined, c: 0 })).toBe('c=0')
  })
})
