import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import HomeView from './HomeView.vue'
import { hello } from '@/api/example'

// 把真实请求层整个替换掉：组件测试只关心「拿到什么就显示什么」，
// 网络、token、401 跳转由 request.test.ts 那一层负责，这里不重复测。
vi.mock('@/api/example', () => ({ hello: vi.fn() }))

const helloMock = vi.mocked(hello)

describe('HomeView', () => {
  beforeEach(() => {
    helloMock.mockReset()
  })

  it('请求还没回来时显示加载中', () => {
    // 返回一个永远不 resolve 的 Promise，把「加载中」这个瞬间固定住。
    helloMock.mockReturnValue(new Promise(() => {}))
    const wrapper = mount(HomeView)

    expect(wrapper.text()).toContain('加载中')
  })

  it('请求成功后显示后端返回的文字', async () => {
    helloMock.mockResolvedValue({ message: 'hello, world', fromBackend: true })
    const wrapper = mount(HomeView)

    await flushPromises()

    expect(helloMock).toHaveBeenCalledWith('world')
    expect(wrapper.text()).toContain('hello, world')
    expect(wrapper.text()).not.toContain('加载中')
  })

  it('请求失败后显示错误文案，而不是一直转圈', async () => {
    helloMock.mockRejectedValue(new Error('connect ECONNREFUSED'))
    const wrapper = mount(HomeView)

    await flushPromises()

    expect(wrapper.text()).toContain('connect ECONNREFUSED')
    expect(wrapper.find('.error').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('加载中')
  })

  it('非 Error 的抛出物也给出兜底文案', async () => {
    // 请求层理论上只抛 ApiError，但组件不能假设上游一定守规矩。
    helloMock.mockRejectedValue('boom')
    const wrapper = mount(HomeView)

    await flushPromises()

    expect(wrapper.text()).toContain('请求失败')
    expect(wrapper.find('.error').exists()).toBe(true)
  })
})
