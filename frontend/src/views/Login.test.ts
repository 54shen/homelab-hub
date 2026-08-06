// ============================================================
// 登录页组件测试:登录第一步 / TOTP 二次验证第二步 / 错误处理
// naive-ui / vue-router / axios 全部 mock 掉,只测组件自身逻辑
// ============================================================
import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const routerReplace = vi.hoisted(() => vi.fn())
const msgSuccess = vi.hoisted(() => vi.fn())
const msgInfo = vi.hoisted(() => vi.fn())
const axiosPost = vi.hoisted(() => vi.fn())
const axiosGet = vi.hoisted(() => vi.fn())

// ---- mock naive-ui:渲染真实 DOM 的轻量 stub ----
vi.mock('naive-ui', () => ({
  // 注意:必须声明 emits:['click'],否则 @click 会同时走自定义事件 + fallthrough
  // 到根元素的原生事件两条路径,导致处理器被调用两次
  NButton: defineComponent({
    emits: ['click'],
    setup(_, { slots, emit }) {
      return () => h('button', { onClick: () => emit('click') }, slots.default?.())
    }
  }),
  NForm: defineComponent({
    setup(_, { slots }) { return () => h('div', { class: 'n-form' }, slots.default?.()) }
  }),
  NFormItem: defineComponent({
    setup(_, { slots }) { return () => h('div', { class: 'n-form-item' }, slots.default?.()) }
  }),
  NInput: defineComponent({
    props: ['value', 'disabled', 'maxlength', 'placeholder', 'clearable', 'type', 'showPasswordOnClick'],
    emits: ['update:value', 'keyup'],
    setup(props, { emit, slots }) {
      return () =>
        h('input', {
          class: 'n-input',
          type: (props as any).type === 'password' ? 'password' : 'text',
          value: props.value,
          disabled: props.disabled,
          maxlength: props.maxlength,
          placeholder: props.placeholder,
          onInput: (e: any) => emit('update:value', e.target.value),
          onKeyup: (e: any) => emit('keyup', e)
        })
    }
  }),
  useMessage: () => ({ success: msgSuccess, info: msgInfo })
}))

vi.mock('vue-router', () => ({ useRouter: () => ({ replace: routerReplace }) }))

// axios:post(登录接口) + get(登录模式查询)
vi.mock('axios', () => ({ default: { post: axiosPost, get: axiosGet } }))

import Login from './Login.vue'

function mountLogin() {
  return mount(Login, {
    global: { stubs: { 'ion-icon': true } }
  })
}

describe('Login.vue', () => {
  beforeEach(() => {
    localStorage.clear()
    routerReplace.mockReset()
    msgSuccess.mockReset()
    msgInfo.mockReset()
    axiosPost.mockReset()
    axiosGet.mockReset()
    // 默认:登录模式查询返回"未开启仅验证码登录"
    axiosGet.mockResolvedValue({ data: { code_only: false } })
  })

  it('渲染登录表单', () => {
    const wrapper = mountLogin()
    expect(wrapper.text()).toContain('Shared Center')
    expect(wrapper.text()).toContain('登 录')
    expect(wrapper.findAll('input')).toHaveLength(2)  // 账号 + 密码
  })

  it('空表单点击登录 → 提示填写账号密码,不发请求', async () => {
    const wrapper = mountLogin()
    await wrapper.find('button').trigger('click')
    expect(wrapper.text()).toContain('请填写账号和密码')
    expect(axiosPost).not.toHaveBeenCalled()
  })

  it('登录成功 → 写入 localStorage 并跳转 dashboard', async () => {
    axiosPost.mockResolvedValue({
      data: { success: true, username: 'admin', token: 'ws-abc', permission: 'admin' }
    })
    const wrapper = mountLogin()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('admin')
    await inputs[1].setValue('admin123')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(localStorage.getItem('sc_token')).toBe('ws-abc')
    expect(localStorage.getItem('sc_username')).toBe('admin')
    expect(localStorage.getItem('sc_permission')).toBe('admin')
    expect(routerReplace).toHaveBeenCalledWith('/dashboard')
    expect(msgSuccess).toHaveBeenCalled()
  })

  it('登录失败 → 显示后端错误信息', async () => {
    axiosPost.mockRejectedValue({ response: { data: { detail: '账号或密码错误' } } })
    const wrapper = mountLogin()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('admin')
    await inputs[1].setValue('wrong')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('账号或密码错误')
    expect(routerReplace).not.toHaveBeenCalled()
  })

  it('启用 2FA 的账号 → 进入第二步(验证码输入框)', async () => {
    axiosPost.mockResolvedValue({ data: { success: false, need_2fa: true, username: 'admin' } })
    const wrapper = mountLogin()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('admin')
    await inputs[1].setValue('admin123')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('验 证')
    expect(wrapper.findAll('input')).toHaveLength(3)  // + 验证码
    expect(msgInfo).toHaveBeenCalled()
  })

  it('第二步:输入 6 位验证码自动提交并登录成功', async () => {
    // 第一次:login → need_2fa;第二次:verify-2fa → success
    axiosPost
      .mockResolvedValueOnce({ data: { success: false, need_2fa: true, username: 'admin' } })
      .mockResolvedValueOnce({ data: { success: true, username: 'admin', token: 'ws-2fa', permission: 'admin' } })

    const wrapper = mountLogin()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('admin')
    await inputs[1].setValue('admin123')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    // 输入 6 位码(触发 onCodeInput 自动提交)
    const codeInput = wrapper.findAll('input')[2]
    await codeInput.setValue('123456')
    await flushPromises()

    expect(axiosPost).toHaveBeenCalledTimes(2)
    expect(axiosPost.mock.calls[1][0]).toContain('/auth/verify-2fa')
    expect(localStorage.getItem('sc_token')).toBe('ws-2fa')
    expect(routerReplace).toHaveBeenCalledWith('/dashboard')
  })

  it('验证码错误 → 显示错误信息', async () => {
    axiosPost
      .mockResolvedValueOnce({ data: { success: false, need_2fa: true, username: 'admin' } })
      .mockRejectedValueOnce({ response: { data: { detail: '验证码错误或已过期' } } })

    const wrapper = mountLogin()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('admin')
    await inputs[1].setValue('admin123')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    await wrapper.findAll('input')[2].setValue('999999')
    await flushPromises()
    expect(wrapper.text()).toContain('验证码错误或已过期')
  })

  it('验证码输入自动过滤非数字', async () => {
    axiosPost.mockResolvedValue({ data: { success: false, need_2fa: true, username: 'admin' } })
    const wrapper = mountLogin()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('admin')
    await inputs[1].setValue('admin123')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    const codeInput = wrapper.findAll('input')[2]
    await codeInput.setValue('12ab3d')
    // onCodeInput 过滤非数字
    expect((codeInput.element as HTMLInputElement).value).toBe('123')
  })

  // ---- 仅验证码登录模式 ----

  it('仅验证码模式:登录页默认只显示验证码输入框', async () => {
    axiosGet.mockResolvedValue({ data: { code_only: true } })
    const wrapper = mountLogin()
    await flushPromises()

    expect(wrapper.findAll('input')).toHaveLength(1)  // 只有验证码框
    expect(wrapper.text()).toContain('已绑定验证码的账号,输入 6 位动态码即可登录')
    expect(wrapper.text()).toContain('使用 用户名+密码 登录')
  })

  it('仅验证码模式:输入 6 位验证码 → 调 totp-login 并登录成功', async () => {
    axiosGet.mockResolvedValue({ data: { code_only: true } })
    axiosPost.mockResolvedValue({ data: { success: true, username: 'admin', token: 'ws-totp', permission: 'admin' } })
    const wrapper = mountLogin()
    await flushPromises()

    await wrapper.find('input').setValue('123456')  // 满 6 位自动提交
    await flushPromises()

    expect(axiosPost).toHaveBeenCalledTimes(1)
    expect(axiosPost.mock.calls[0][0]).toContain('/auth/totp-login')
    expect(axiosPost.mock.calls[0][1]).toEqual({ code: '123456' })  // 无用户名密码
    expect(localStorage.getItem('sc_token')).toBe('ws-totp')
  })

  it('仅验证码模式:被锁(429)→ 自动切到 用户名+密码 表单', async () => {
    axiosGet.mockResolvedValue({ data: { code_only: true } })
    axiosPost.mockRejectedValue({ response: { status: 429, data: { detail: '纯验证码登录已锁定 30 分钟' } } })
    const wrapper = mountLogin()
    await flushPromises()

    await wrapper.find('input').setValue('123456')
    await flushPromises()

    expect(wrapper.text()).toContain('纯验证码登录已锁定 30 分钟')
    // 已切换到标准表单(账号 + 密码输入框出现)
    expect(wrapper.findAll('input')).toHaveLength(2)
  })

  it('仅验证码模式:未绑定用户可点链接切到密码登录', async () => {
    axiosGet.mockResolvedValue({ data: { code_only: true } })
    const wrapper = mountLogin()
    await flushPromises()

    await wrapper.find('a').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('input')).toHaveLength(2)  // 账号 + 密码
  })

  it('第二步:verify-2fa 请求携带 login 签发的一次性 ticket', async () => {
    axiosPost
      .mockResolvedValueOnce({ data: { success: false, need_2fa: true, username: 'admin', ticket: 'tk-abc' } })
      .mockResolvedValueOnce({ data: { success: true, username: 'admin', token: 'ws-2fa', permission: 'admin' } })

    const wrapper = mountLogin()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('admin')
    await inputs[1].setValue('admin123')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    await wrapper.findAll('input')[2].setValue('123456')
    await flushPromises()

    expect(axiosPost.mock.calls[1][0]).toContain('/auth/verify-2fa')
    expect(axiosPost.mock.calls[1][1]).toMatchObject({ username: 'admin', code: '123456', ticket: 'tk-abc' })
  })
})
