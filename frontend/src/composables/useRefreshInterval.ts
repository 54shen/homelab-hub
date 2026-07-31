import { useUINumber } from './useUISetting'

const envDefault = parseFloat(import.meta.env.VITE_REFRESH_INTERVAL || '0') || 0

const globalInterval = useUINumber('refresh_interval', envDefault)

/**
 * 全局自动刷新间隔 — localStorage 即时 + 服务端同步
 */
export function useRefreshInterval() {
  return globalInterval
}
