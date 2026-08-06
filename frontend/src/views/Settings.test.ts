// ============================================================
// Settings 设置页测试
// naive-ui / qrcode / API 全部 mock
// 覆盖:初始加载 / 修改密码 / 2FA 启用与关闭 / 用户增删改 / Token 增删与复制 / 会话管理 / 备份恢复
// ============================================================
import { defineComponent, h } from 'vue'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

// http 默认导出(Settings 直接用它请求 /users /tokens /sessions /auth/password)
const httpMock = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }))
const authApiMock = vi.hoisted(() => ({ twofaStatus: vi.fn(), twofaSetup: vi.fn(), twofaConfirm: vi.fn(), twofaDisable: vi.fn() }))
const dashboardApiMock = vi.hoisted(() => ({ dbStatus: vi.fn() }))
const settingsApiMock = vi.hoisted(() => ({ exportBackup: vi.fn(), restoreBackup: vi.fn() }))
const qrMock = vi.hoisted(() => vi.fn(() => Promise.resolve('data:image/png;base64,QR')))
const clipboardMock = vi.hoisted(() => vi.fn())
const msgSuccess = vi.hoisted(() => vi.fn())
const msgError = vi.hoisted(() => vi.fn())
const msgWarning = vi.hoisted(() => vi.fn())

vi.mock('../api', () => ({
  default: httpMock,
  authApi: authApiMock,
  dashboardApi: dashboardApiMock,
  settingsApi: settingsApiMock
}))
vi.mock('qrcode', () => ({ default: { toDataURL: qrMock } }))

// ---- naive-ui 轻量 stub ----
vi.mock('naive-ui', () => ({
  NButton: defineComponent({
    emits: ['click'],
    setup(_, { slots, emit }) {
      return () => h('button', { onClick: () => emit('click') }, slots.default?.())
    }
  }),
  NCard: defineComponent({
    props: ['title', 'size'],
    setup(props, { slots }) {
      // 注意:模板里 #header-extra 编译出的插槽名是 kebab-case,不是 camelCase
      return () => h('div', { class: 'n-card' }, [
        h('div', { class: 'n-card-title' }, props.title),
        slots['header-extra']?.(),
        slots.default?.()
      ])
    }
  }),
  NForm: defineComponent({ setup(_, { slots }) { return () => h('div', { class: 'n-form' }, slots.default?.()) } }),
  NFormItem: defineComponent({ props: ['label'], setup(props, { slots }) { return () => h('div', { class: 'n-form-item' }, [h('span', {}, props.label), slots.default?.()]) } }),
  NInput: defineComponent({
    props: ['value', 'disabled', 'placeholder', 'type', 'maxlength'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('input', {
        value: props.value ?? '',
        placeholder: props.placeholder,
        disabled: props.disabled,
        maxlength: props.maxlength,
        type: props.type || 'text',
        onInput: (e: any) => emit('update:value', e.target.value)
      })
    }
  }),
  NInputNumber: defineComponent({
    props: ['value', 'min', 'max'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('input', {
        type: 'number',
        value: props.value,
        onInput: (e: any) => emit('update:value', Number(e.target.value))
      })
    }
  }),
  NSelect: defineComponent({
    props: ['value', 'options'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('select', {
        value: props.value ?? '',
        onChange: (e: any) => emit('update:value', (e.target as HTMLSelectElement).value || null)
      }, (props.options || []).map((o: any) => h('option', { value: o.value }, o.label)))
    }
  }),
  // 表格 stub:对每行调用 columns 的 render 渲染单元格(编辑/删除按钮可点)
  NDataTable: defineComponent({
    props: ['data', 'columns'],
    setup(props) {
      return () => h('div', { class: 'n-data-table' }, [
        ...(props.data || []).map((r: any, i: number) =>
          h('div', { class: 'table-row', key: i }, [
            ...(props.columns || []).map((c: any, j: number) =>
              h('div', { class: `cell-${c.key}`, key: j }, c.render ? [c.render(r)] : [String(r[c.key] ?? '')])
            )
          ])
        )
      ])
    }
  }),
  NEmpty: defineComponent({ props: ['description'], setup(props) { return () => h('div', { class: 'n-empty' }, props.description) } }),
  NModal: defineComponent({
    props: ['show', 'title'],
    emits: ['update:show'],
    setup(props, { slots }) {
      // 必须在 render 内求值 props.show,弹窗打开后才重新渲染
      return () =>
        props.show
          ? h('div', { class: 'n-modal' }, [
              h('div', { class: 'modal-title' }, props.title),
              slots.default?.(),
              slots.footer?.()
            ])
          : null
    }
  }),
  NPopconfirm: defineComponent({
    emits: ['positive-click'],
    setup(_, { slots, emit }) {
      return () => h('div', { class: 'n-popconfirm' }, [
        slots.trigger?.(),
        h('button', { class: 'confirm-btn', onClick: () => emit('positive-click') }, '确定')
      ])
    }
  }),
  NSpace: defineComponent({ setup(_, { slots }) { return () => h('div', { class: 'n-space' }, slots.default?.()) } }),
  NSwitch: defineComponent({
    props: ['value'],
    emits: ['update:value'],
    setup(props, { emit }) {
      return () => h('button', {
        class: 'n-switch',
        onClick: () => emit('update:value', !props.value)
      })
    }
  }),
  NUpload: defineComponent({
    props: ['showFileList'],
    emits: ['change'],
    setup(_, { emit, slots }) {
      return () => h('div', { class: 'n-upload' }, [
        slots.default?.(),
        h('button', {
          class: 'upload-trigger',
          onClick: () => emit('change', { file: { file: new File(['{}'], 'backup.json', { type: 'application/json' }) } })
        }, '选择备份文件')
      ])
    }
  }),
  NDescriptions: defineComponent({ setup(_, { slots }) { return () => h('div', { class: 'n-descriptions' }, slots.default?.()) } }),
  NDescriptionsItem: defineComponent({ props: ['label'], setup(props, { slots }) { return () => h('div', { class: 'n-descriptions-item' }, [h('span', {}, props.label), slots.default?.()]) } }),
  useMessage: () => ({ success: msgSuccess, error: msgError, warning: msgWarning })
}))

import Settings from './Settings.vue'

// jsdom 没有 URL.createObjectURL / navigator.clipboard
beforeAll(() => {
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:test')
  globalThis.URL.revokeObjectURL = vi.fn()
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: clipboardMock },
    configurable: true
  })
})
enableAutoUnmount(afterEach)

function mockDefaultData() {
  httpMock.get.mockImplementation((url: string) => {
    if (url === '/users') {
      return Promise.resolve({ data: [{ id: 1, username: 'admin', permission: 'admin', created_at: '2026-01-01' }] })
    }
    if (url === '/tokens') {
      return Promise.resolve({ data: [{ id: 2, user_id: null, name: 'agent-1', token: 'tk...', token_full: '', permission: 'write', created_at: '2026-01-01' }] })
    }
    if (url === '/sessions') {
      return Promise.resolve({ data: [{ id: 3, username: 'admin', permission: 'admin', ip: '127.0.0.1', created_at: '2026-01-01', last_active: '2026-08-01' }] })
    }
    return Promise.resolve({ data: [] })
  })
  authApiMock.twofaStatus.mockResolvedValue({ data: { enabled: false } })
  dashboardApiMock.dbStatus.mockResolvedValue({ data: { file_size: '1.2 MB', total_keys: 100, active_keys_24h: 5, history_count: 0 } })
}

function mountPage() {
  return mount(Settings, { global: { stubs: { 'ion-icon': true } } })
}

function cardByTitle(wrapper: ReturnType<typeof mountPage>, title: string) {
  const c = wrapper.findAll('.n-card').find((c) => c.find('.n-card-title').text() === title)
  return c!
}

describe('Settings.vue', () => {
  beforeEach(() => {
    Object.values(httpMock).forEach((m) => (m as any).mockReset())
    Object.values(authApiMock).forEach((m) => (m as any).mockReset())
    Object.values(dashboardApiMock).forEach((m) => (m as any).mockReset())
    Object.values(settingsApiMock).forEach((m) => (m as any).mockReset())
    qrMock.mockReset()
    qrMock.mockImplementation(() => Promise.resolve('data:image/png;base64,QR'))
    clipboardMock.mockReset()
    msgSuccess.mockReset(); msgError.mockReset(); msgWarning.mockReset()
    localStorage.clear()
    localStorage.setItem('sc_username', 'admin')
    mockDefaultData()
    httpMock.put.mockResolvedValue({ data: {} })
    httpMock.post.mockResolvedValue({ data: {} })
    httpMock.delete.mockResolvedValue({ data: {} })
    authApiMock.twofaSetup.mockResolvedValue({ data: { uri: 'otpauth://totp/SharedCenter:admin?secret=ABC123', secret: 'ABC123' } })
    authApiMock.twofaConfirm.mockResolvedValue({ data: {} })
    authApiMock.twofaDisable.mockResolvedValue({ data: {} })
    settingsApiMock.exportBackup.mockResolvedValue({ data: new Blob(['{}']) })
    settingsApiMock.restoreBackup.mockResolvedValue({ data: { success: true, message: '恢复完成' } })
  })

  it('挂载后加载用户/Token/会话/2FA/数据库状态并渲染', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(httpMock.get).toHaveBeenCalledWith('/users')
    expect(httpMock.get).toHaveBeenCalledWith('/tokens')
    expect(httpMock.get).toHaveBeenCalledWith('/sessions')
    expect(authApiMock.twofaStatus).toHaveBeenCalled()
    expect(dashboardApiMock.dbStatus).toHaveBeenCalled()
    // Token + 用户 + 会话三张表各 1 行
    expect(wrapper.findAll('.table-row')).toHaveLength(3)
    expect(wrapper.text()).toContain('admin')
    expect(wrapper.text()).toContain('agent-1')
    // 数据库状态
    expect(wrapper.text()).toContain('1.2 MB')
    expect(wrapper.text()).toContain('100')
  })

  it('无数据时显示各空状态', async () => {
    httpMock.get.mockResolvedValue({ data: [] })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.n-empty').map((e) => e.text())).toEqual(
      expect.arrayContaining(['暂无 Token', '暂无用户', '暂无活跃会话'])
    )
  })

  it('修改密码:填写后调用接口并清空表单', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const card = cardByTitle(wrapper, '修改密码')
    const inputs = card.findAll('input')
    await inputs[0].setValue('old123')
    await inputs[1].setValue('new1234')
    await card.findAll('button').find((b) => b.text().includes('修改密码'))!.trigger('click')
    await flushPromises()
    expect(httpMock.put).toHaveBeenCalledWith('/auth/password', {
      username: 'admin', old_password: 'old123', new_password: 'new1234'
    })
    expect(msgSuccess).toHaveBeenCalledWith('密码已修改，下次登录生效')
    // 表单清空
    expect(card.findAll('input')[0].element.value).toBe('')
    expect(card.findAll('input')[1].element.value).toBe('')
  })

  it('修改密码:空表单或新密码过短 → 警告且不请求', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const card = cardByTitle(wrapper, '修改密码')
    await card.findAll('button').find((b) => b.text().includes('修改密码'))!.trigger('click')
    await flushPromises()
    expect(msgWarning).toHaveBeenCalledWith('请填写旧密码和新密码')
    expect(httpMock.put).not.toHaveBeenCalled()

    const inputs = card.findAll('input')
    await inputs[0].setValue('old123')
    await inputs[1].setValue('abc')
    await card.findAll('button').find((b) => b.text().includes('修改密码'))!.trigger('click')
    await flushPromises()
    expect(msgWarning).toHaveBeenCalledWith('新密码至少 4 位')
    expect(httpMock.put).not.toHaveBeenCalled()
  })

  it('2FA:启用流程(生成密钥/二维码 → 输入验证码确认)', async () => {
    authApiMock.twofaSetup.mockResolvedValue({ data: { uri: 'otpauth://totp/SharedCenter:admin?secret=ABC123', secret: 'ABC123' } })
    const wrapper = mountPage()
    await flushPromises()
    const twofaCard = cardByTitle(wrapper, '二次验证')
    await twofaCard.findAll('button').find((b) => b.text().includes('启用'))!.trigger('click')
    await flushPromises()
    expect(authApiMock.twofaSetup).toHaveBeenCalled()
    expect(qrMock).toHaveBeenCalledWith('otpauth://totp/SharedCenter:admin?secret=ABC123')
    // 密钥与二维码展示
    expect(twofaCard.text()).toContain('ABC123')
    expect(twofaCard.find('img').exists()).toBe(true)
    // 输入 6 位验证码确认
    const codeInput = twofaCard.findAll('input').find((i) => i.attributes('placeholder')?.includes('6 位'))!
    await codeInput.setValue('123456')
    await twofaCard.findAll('button').find((b) => b.text().includes('确认启用'))!.trigger('click')
    await flushPromises()
    expect(authApiMock.twofaConfirm).toHaveBeenCalledWith('123456')
    expect(msgSuccess).toHaveBeenCalledWith('二次验证已启用')
    expect(wrapper.text()).toContain('已启用')
  })

  it('2FA:验证码不足 6 位 → 警告且不请求', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const twofaCard = cardByTitle(wrapper, '二次验证')
    await twofaCard.findAll('button').find((b) => b.text().includes('启用'))!.trigger('click')
    await flushPromises()
    const codeInput = twofaCard.findAll('input').find((i) => i.attributes('placeholder')?.includes('6 位'))!
    await codeInput.setValue('123')
    await twofaCard.findAll('button').find((b) => b.text().includes('确认启用'))!.trigger('click')
    await flushPromises()
    expect(msgWarning).toHaveBeenCalledWith('请输入 6 位验证码')
    expect(authApiMock.twofaConfirm).not.toHaveBeenCalled()
  })

  it('2FA:已启用状态下关闭流程', async () => {
    authApiMock.twofaStatus.mockResolvedValue({ data: { enabled: true } })
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.text()).toContain('已启用')
    const twofaCard = cardByTitle(wrapper, '二次验证')
    await twofaCard.findAll('button').find((b) => b.text().includes('关闭'))!.trigger('click')
    await flushPromises()
    const codeInput = twofaCard.findAll('input').find((i) => i.attributes('placeholder')?.includes('确认关闭'))!
    await codeInput.setValue('654321')
    await twofaCard.findAll('button').find((b) => b.text().includes('确认关闭'))!.trigger('click')
    await flushPromises()
    expect(authApiMock.twofaDisable).toHaveBeenCalledWith('654321')
    expect(msgSuccess).toHaveBeenCalledWith('二次验证已关闭')
    // 回到未启用状态
    expect(twofaCard.text()).toContain('启用')
  })

  it('新增用户:校验 → 保存调用接口并关闭弹窗', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const userCard = cardByTitle(wrapper, '用户管理')
    await userCard.findAll('button').find((b) => b.text().includes('新增用户'))!.trigger('click')
    await flushPromises()
    const modal = wrapper.find('.n-modal')
    expect(modal.exists()).toBe(true)
    expect(modal.text()).toContain('新增用户')
    // 空用户名 → 警告
    await modal.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
    await flushPromises()
    expect(msgWarning).toHaveBeenCalledWith('请输入用户名')
    // 填用户名但密码过短 → 警告
    const inputs = modal.findAll('input')
    await inputs[0].setValue('bob')
    await inputs[1].setValue('abc')
    await modal.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
    await flushPromises()
    expect(msgWarning).toHaveBeenCalledWith('密码至少4位')
    expect(httpMock.post).not.toHaveBeenCalled()
    // 合法提交
    await inputs[1].setValue('bob1234')
    await modal.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
    await flushPromises()
    expect(httpMock.post).toHaveBeenCalledWith('/users', { username: 'bob', password: 'bob1234', permission: 'read' })
    expect(msgSuccess).toHaveBeenCalledWith('已保存')
    // 保存后重新加载用户
    expect(httpMock.get.mock.calls.filter((c) => c[0] === '/users').length).toBeGreaterThanOrEqual(2)
    expect(wrapper.find('.n-modal').exists()).toBe(false)
  })

  it('编辑用户:预填表单,保存调用 put', async () => {
    const wrapper = mountPage()
    await flushPromises()
    // 表格渲染顺序:Token 表(1 行) → 用户表(1 行) → 会话表(1 行),用户行是第 2 行
    const row = wrapper.findAll('.table-row')[1]
    await row.findAll('button').find((b) => b.text().includes('编辑'))!.trigger('click')
    await flushPromises()
    const modal = wrapper.find('.n-modal')
    expect(modal.text()).toContain('编辑用户')
    const usernameInput = modal.findAll('input')[0]
    expect((usernameInput.element as HTMLInputElement).disabled).toBe(true)
    await modal.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
    await flushPromises()
    expect(httpMock.put).toHaveBeenCalledWith('/users/1', { password: undefined, permission: 'admin' })
  })

  it('删除用户:确认后调用 delete 并重新加载', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const row = wrapper.findAll('.table-row')[1]  // 用户行
    await row.find('.confirm-btn').trigger('click')
    await flushPromises()
    expect(httpMock.delete).toHaveBeenCalledWith('/users/1')
    expect(msgSuccess).toHaveBeenCalledWith('已删除')
  })

  it('新增 Token:保存后展示生成值,可复制;取消关闭弹窗', async () => {
    httpMock.post.mockResolvedValue({ data: { token: 'tk-abc123' } })
    const wrapper = mountPage()
    await flushPromises()
    const tokenCard = cardByTitle(wrapper, 'Token 管理')
    await tokenCard.findAll('button').find((b) => b.text().includes('新增 Token'))!.trigger('click')
    await flushPromises()
    const modal = wrapper.find('.n-modal')
    expect(modal.text()).toContain('新增 Token')
    await modal.findAll('input')[0].setValue('win-agent')
    await modal.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
    await flushPromises()
    expect(httpMock.post).toHaveBeenCalledWith('/tokens', { name: 'win-agent', permission: 'read' })
    expect(msgSuccess).toHaveBeenCalledWith('Token 已生成，请复制保存！')
    // 弹窗不关闭,展示生成的 Token(input 的 value 不体现在 text() 里,需读元素值)
    expect(wrapper.find('.n-modal').exists()).toBe(true)
    const tokenInput = modal.findAll('input').find((i) => (i.element as HTMLInputElement).value === 'tk-abc123')
    expect(tokenInput).toBeTruthy()
    // 复制
    await modal.findAll('button').find((b) => b.text().includes('复制'))!.trigger('click')
    expect(clipboardMock).toHaveBeenCalledWith('tk-abc123')
    expect(msgSuccess).toHaveBeenCalledWith('已复制到剪贴板')
    // 取消关闭
    await modal.findAll('button').find((b) => b.text().includes('取消'))!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.n-modal').exists()).toBe(false)
  })

  it('编辑 Token:保存调用 put 并重新加载', async () => {
    const wrapper = mountPage()
    await flushPromises()
    // Token 表在模板中位于用户表之前,Token 行是第 1 行
    const tokenRow = wrapper.findAll('.table-row')[0]
    await tokenRow.findAll('button').find((b) => b.text().includes('编辑'))!.trigger('click')
    await flushPromises()
    const modal = wrapper.find('.n-modal')
    expect(modal.text()).toContain('编辑 Token')
    await modal.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
    await flushPromises()
    expect(httpMock.put).toHaveBeenCalledWith('/tokens/2', { name: 'agent-1', permission: 'write' })
    expect(msgSuccess).toHaveBeenCalledWith('已更新')
  })

  it('删除 Token:确认后调用 delete', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const tokenRow = wrapper.findAll('.table-row')[0]
    await tokenRow.find('.confirm-btn').trigger('click')
    await flushPromises()
    expect(httpMock.delete).toHaveBeenCalledWith('/tokens/2')
  })

  it('会话管理:踢掉所有会话与踢掉单个会话', async () => {
    httpMock.get.mockImplementation((url: string) => {
      if (url === '/users') return Promise.resolve({ data: [{ id: 1, username: 'admin', permission: 'admin', created_at: '2026-01-01' }] })
      if (url === '/tokens') return Promise.resolve({ data: [{ id: 2, user_id: null, name: 'agent-1', token: 'tk...', token_full: '', permission: 'write', created_at: '2026-01-01' }] })
      if (url === '/sessions') {
        return Promise.resolve({
          data: [
            { id: 3, username: 'admin', permission: 'admin', ip: '127.0.0.1', created_at: '2026-01-01', last_active: '2026-08-01' },
            { id: 4, username: 'bob', permission: 'read', ip: '192.168.1.5', created_at: '2026-02-01', last_active: '2026-08-01' }
          ]
        })
      }
      return Promise.resolve({ data: [] })
    })
    httpMock.post.mockResolvedValue({ data: { deleted: 1 } })
    const wrapper = mountPage()
    await flushPromises()
    // 会话 >1 时出现"踢掉所有"
    const sessionCard = cardByTitle(wrapper, '活跃会话')
    const kickAllBtn = sessionCard.findAll('button').find((b) => b.text().includes('踢掉所有'))
    expect(kickAllBtn).toBeTruthy()
    await sessionCard.find('.confirm-btn').trigger('click')
    await flushPromises()
    expect(httpMock.post).toHaveBeenCalledWith('/sessions/kick-all')
    expect(msgSuccess).toHaveBeenCalledWith('已踢掉 1 个其他会话')
    // 踢掉单个会话(全表第 3 行 = 第一个会话)
    const sessionRow = wrapper.findAll('.table-row')[2]
    await sessionRow.find('.confirm-btn').trigger('click')
    await flushPromises()
    expect(httpMock.delete).toHaveBeenCalledWith('/sessions/3')
    expect(msgSuccess).toHaveBeenCalledWith('已踢掉')
  })

  it('导出完整备份 → 调用接口并触发下载', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const dbCard = cardByTitle(wrapper, '数据库维护')
    await dbCard.findAll('button').find((b) => b.text().includes('导出完整备份'))!.trigger('click')
    await flushPromises()
    expect(settingsApiMock.exportBackup).toHaveBeenCalled()
    expect(globalThis.URL.createObjectURL).toHaveBeenCalled()
  })

  it('恢复备份成功 → 提示并重新加载数据', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const dbCard = cardByTitle(wrapper, '数据库维护')
    await dbCard.find('.upload-trigger').trigger('click')
    await flushPromises()
    expect(settingsApiMock.restoreBackup).toHaveBeenCalledWith(expect.any(File))
    expect(msgSuccess).toHaveBeenCalledWith('恢复完成')
    // 恢复后重新加载用户/Token/数据库状态
    expect(httpMock.get.mock.calls.filter((c) => c[0] === '/users').length).toBeGreaterThanOrEqual(2)
    expect(dashboardApiMock.dbStatus).toHaveBeenCalledTimes(2)
  })

  it('恢复备份失败 → 错误提示', async () => {
    settingsApiMock.restoreBackup.mockRejectedValue(new Error('bad file'))
    const wrapper = mountPage()
    await flushPromises()
    const dbCard = cardByTitle(wrapper, '数据库维护')
    await dbCard.find('.upload-trigger').trigger('click')
    await flushPromises()
    expect(msgError).toHaveBeenCalledWith('恢复失败，请检查文件格式')
  })
})
