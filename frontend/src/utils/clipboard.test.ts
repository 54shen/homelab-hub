// ============================================================
// 剪切板编解码纯函数测试
// ============================================================
import { describe, expect, it } from 'vitest'
import {
  CLIPBOARD_KEY, decodeClipboard, encodeClipboard, isClipboardKey,
} from './clipboard'

describe('clipboard 编解码', () => {
  it('编码:主题+内容 → {"t":"主题","c":"内容"}', () => {
    expect(encodeClipboard('购物', '买牛奶')).toBe('{"t":"购物","c":"买牛奶"}')
  })

  it('编码:空主题 → t 为 ""', () => {
    expect(encodeClipboard('', 'hi')).toBe('{"t":"","c":"hi"}')
    expect(encodeClipboard(undefined as any, 'hi')).toBe('{"t":"","c":"hi"}')
  })

  it('解码:往返一致', () => {
    const v = encodeClipboard('主题A', '内容B')
    expect(decodeClipboard(v)).toEqual({ topic: '主题A', content: '内容B' })
  })

  it('解码:无主题 JSON → topic 为空', () => {
    expect(decodeClipboard('{"t":"","c":"x"}')).toEqual({ topic: '', content: 'x' })
  })

  it('解码:非法 JSON → 整串作内容(兼容手写明文)', () => {
    expect(decodeClipboard('随便写点什么')).toEqual({ topic: '', content: '随便写点什么' })
    expect(decodeClipboard('')).toEqual({ topic: '', content: '' })
    expect(decodeClipboard('123')).toEqual({ topic: '', content: '123' })
  })

  it('解码:JSON 但不是对象(数组/数字) → 整串作内容', () => {
    expect(decodeClipboard('"hello"')).toEqual({ topic: '', content: '"hello"' })
    expect(decodeClipboard('42')).toEqual({ topic: '', content: '42' })
  })

  it('解码:缺 c 字段的 JSON → 整串作内容', () => {
    expect(decodeClipboard('{"t":"x"}')).toEqual({ topic: '', content: '{"t":"x"}' })
  })

  it('isClipboardKey:精确匹配内置 key', () => {
    expect(isClipboardKey(CLIPBOARD_KEY)).toBe(true)
    expect(isClipboardKey('剪切板.其他')).toBe(false)
    expect(isClipboardKey('clipboard')).toBe(false)
  })
})
