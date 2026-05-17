import { getApiBaseUrl, getSessionId } from './api/client'

const SESSION_KEY = 'session_id'

/**
 * Extract session_id from URL query params and persist it in sessionStorage.
 * Should be called once on app mount.
 */
export function bootstrapSession(): void {
  const params = new URLSearchParams(window.location.search)
  const sid = params.get(SESSION_KEY)
  if (sid) {
    sessionStorage.setItem(SESSION_KEY, sid)
    // Remove session_id from URL to keep it clean
    params.delete(SESSION_KEY)
    const qs = params.toString()
    const newUrl = window.location.pathname + (qs ? `?${qs}` : '') + window.location.hash
    window.history.replaceState({}, '', newUrl)
  }
}

export interface AuthUser {
  id?: string
  username?: string
  email?: string
  [key: string]: unknown
}

/**
 * Fetch the current user's info from backend (proxied to central auth).
 * Returns null if not authenticated.
 */
export async function fetchUser(): Promise<AuthUser | null> {
  const sid = getSessionId()
  if (!sid) return null
  try {
    const base = getApiBaseUrl()
    const resp = await fetch(`${base}/api/auth/user`, {
      headers: { 'X-Session-Id': sid },
    })
    if (!resp.ok) return null
    const data = await resp.json()
    // Java backend returns flat { id, username, email } — no envelope
    if (data && data.username) return data as AuthUser
    return null
  } catch {
    return null
  }
}

/**
 * Clear local session and optionally redirect.
 */
export function handleLogout(): void {
  sessionStorage.removeItem(SESSION_KEY)
  redirectToLogin()
}

/**
 * Resolve the portal (main site) origin.
 * The main site runs on port 5173 by default.
 */
export function resolvePortalOrigin(): string {
  const { protocol, hostname } = window.location
  return `${protocol}//${hostname}:5173`
}

/**
 * Redirect browser to the main site login page.
 */
export function redirectToLogin(): void {
  const portal = resolvePortalOrigin()
  window.location.href = `${portal}/login`
}
