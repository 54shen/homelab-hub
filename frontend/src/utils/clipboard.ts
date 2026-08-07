// ============================================================
// 剪切板 — 内置 key 常量 + 主题/内容编解码（纯函数，便于单测）
// ============================================================

export const CLIPBOARD_KEY = '剪切板.内容'
export const CLIPBOARD_RETENTION_DAYS = 3650

// 服务器专用 key 后缀（设备上报时间，只能服务器写、不可删除）
export const REPORT_TIME_SUFFIX = '.server_received_at'

export const isClipboardKey = (key: string): boolean => key === CLIPBOARD_KEY

export const isReportTimeKey = (key: string): boolean => key.endsWith(REPORT_TIME_SUFFIX)

export interface ClipboardPayload {
  topic: string
  content: string
}

// 主题 + 内容 → 存储值（JSON，短键 t/c；主题可选，为空时 t 为 ""）
export function encodeClipboard(topic: string, content: string): string {
  return JSON.stringify({ t: topic || '', c: content })
}

// 存储值 → 主题/内容。容错：非法 JSON / 非对象 / 手写明文 → 整串视为内容
export function decodeClipboard(value: string): ClipboardPayload {
  try {
    const obj = JSON.parse(value || '')
    if (obj && typeof obj === 'object' && 'c' in obj) {
      return { topic: String(obj.t ?? ''), content: String(obj.c ?? '') }
    }
  } catch { /* fallthrough */ }
  return { topic: '', content: value || '' }
}
