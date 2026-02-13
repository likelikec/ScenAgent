export type JobHistoryItem = {
  job_id: string
  created_at?: string
}

const STORAGE_KEY = 'mobile_v4_job_history'

export function readJobHistory(): JobHistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(isJobHistoryItemLike)
      .map((x) => ({ job_id: x.job_id, created_at: x.created_at }))
      .slice(0, 50)
  } catch {
    return []
  }
}

export function addJobHistory(item: JobHistoryItem): void {
  const current = readJobHistory()
  const next = [item, ...current.filter((x) => x.job_id !== item.job_id)].slice(0, 50)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}

export function removeJobHistory(jobId: string): void {
  const current = readJobHistory()
  const next = current.filter((x) => x.job_id !== jobId)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}

function isJobHistoryItemLike(value: unknown): value is { job_id: string; created_at?: string } {
  if (!value || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  if (typeof v.job_id !== 'string') return false
  if (v.created_at !== undefined && typeof v.created_at !== 'string') return false
  return true
}
