export type ScenarioHistoryItem = {
  scenario_token: string
  filename: string
  uploaded_at: string
  api_base_url?: string
}

const STORAGE_KEY = 'mobile_v4_scenario_history'

export function readScenarioHistory(): ScenarioHistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isScenarioHistoryItemLike).slice(0, 20)
  } catch {
    return []
  }
}

export function addScenarioHistory(item: ScenarioHistoryItem): void {
  const current = readScenarioHistory()
  const next = [
    item,
    ...current.filter((x) => x.scenario_token !== item.scenario_token),
  ].slice(0, 20)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}

export function removeScenarioHistory(token: string): void {
  const current = readScenarioHistory()
  const next = current.filter((x) => x.scenario_token !== token)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}

export function clearScenarioHistory(): void {
  localStorage.removeItem(STORAGE_KEY)
}

function isScenarioHistoryItemLike(value: unknown): value is ScenarioHistoryItem {
  if (!value || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  if (typeof v.scenario_token !== 'string') return false
  if (typeof v.filename !== 'string') return false
  if (typeof v.uploaded_at !== 'string') return false
  if (v.api_base_url !== undefined && typeof v.api_base_url !== 'string') return false
  return true
}

