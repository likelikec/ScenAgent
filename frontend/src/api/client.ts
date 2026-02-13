export type ApiEnvelope<T> = {
  code: number
  message: string
  result?: T
  detail?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code?: number
  readonly detail?: string

  constructor(args: { message: string; status: number; code?: number; detail?: string }) {
    super(args.message)
    this.status = args.status
    this.code = args.code
    this.detail = args.detail
  }
}

const API_BASE_URL_STORAGE_KEY = 'mobile_v4_api_base_url'

export function getApiBaseUrl(): string {
  const stored = localStorage.getItem(API_BASE_URL_STORAGE_KEY)?.trim()
  const env = import.meta.env.VITE_API_BASE_URL?.trim()
  const fallback = 'http://127.0.0.1:8000'
  const raw = stored || env || fallback
  return raw.endsWith('/') ? raw.slice(0, -1) : raw
}

export function setApiBaseUrl(value: string): void {
  const v = value.trim()
  if (!v) {
    localStorage.removeItem(API_BASE_URL_STORAGE_KEY)
    return
  }
  localStorage.setItem(API_BASE_URL_STORAGE_KEY, v)
}

function requireValidApiBaseUrl(): string {
  const base = getApiBaseUrl()
  if (!base) {
    throw new ApiError({
      message: 'API_BASE_URL 未配置',
      detail: '请到 设置 填写后端地址，例如 http://127.0.0.1:8000',
      status: 0,
    })
  }
  if (!/^https?:\/\/.+/i.test(base)) {
    throw new ApiError({
      message: 'API_BASE_URL 格式错误',
      detail: `当前值：${base}；示例：http://127.0.0.1:8000`,
      status: 0,
    })
  }
  return base
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const base = requireValidApiBaseUrl()
  const url = `${base}${path.startsWith('/') ? '' : '/'}${path}`
  const resp = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })

  let payload: ApiEnvelope<T> | undefined
  try {
    payload = (await resp.json()) as ApiEnvelope<T>
  } catch {
    payload = undefined
  }

  if (!resp.ok) {
    throw new ApiError({
      message: payload?.message || `HTTP ${resp.status}`,
      status: resp.status,
      code: payload?.code,
      detail: payload?.detail,
    })
  }

  if (!payload || payload.code !== 200 || payload.result === undefined) {
    throw new ApiError({
      message: payload?.message || 'invalid response',
      status: resp.status,
      code: payload?.code,
      detail: payload?.detail,
    })
  }

  return payload.result
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const base = requireValidApiBaseUrl()
  const url = `${base}${path.startsWith('/') ? '' : '/'}${path}`
  const resp = await fetch(url, { method: 'POST', body: formData })

  const payload = (await resp.json()) as ApiEnvelope<T>
  if (!resp.ok || payload.code !== 200 || payload.result === undefined) {
    throw new ApiError({
      message: payload?.message || `HTTP ${resp.status}`,
      status: resp.status,
      code: payload?.code,
      detail: payload?.detail,
    })
  }
  return payload.result
}

export async function apiDownload(path: string): Promise<Blob> {
  const base = requireValidApiBaseUrl()
  const separator = path.includes('?') ? '&' : '?'
  const url = `${base}${path.startsWith('/') ? '' : '/'}${path}${separator}_t=${Date.now()}`
  const resp = await fetch(url)
  if (!resp.ok) {
    throw new ApiError({ message: `HTTP ${resp.status}`, status: resp.status })
  }
  return await resp.blob()
}
