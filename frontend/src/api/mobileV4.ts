import { apiDownload, apiJson, apiUpload } from './client'
import type { BackendConfig, JobStatus, RunRequest, RunResponse } from './types'

export async function uploadScenario(file: File): Promise<{ scenario_token: string; filename: string }> {
  const form = new FormData()
  form.append('file', file, file.name)
  const res = await apiUpload<{ token: string; filename: string }>('/api/v1/upload', form)
  return {
    scenario_token: res.token,
    filename: res.filename
  }
}

export async function uploadFile(file: File): Promise<{ type: 'scenario' | 'apk'; token: string; filename: string }> {
  const form = new FormData()
  form.append('file', file, file.name)
  return await apiUpload<{ type: 'scenario' | 'apk'; token: string; filename: string }>('/api/v1/upload', form)
}

export async function runJob(req: RunRequest): Promise<RunResponse> {
  return await apiJson('/api/v1/run', { method: 'POST', body: JSON.stringify(req) })
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  return await apiJson(`/api/v1/status/${encodeURIComponent(jobId)}`)
}

export async function setBackendConfig(cfg: Partial<BackendConfig>): Promise<BackendConfig> {
  return await apiJson('/api/v1/config', { method: 'POST', body: JSON.stringify(cfg) })
}

export async function stopJob(jobId: string): Promise<JobStatus> {
  return await apiJson(`/api/v1/stop/${encodeURIComponent(jobId)}`, { method: 'POST' })
}

export async function downloadArtifact(args: {
  jobId: string
  filePath: string
  runDir?: string
}): Promise<Blob> {
  const qp = new URLSearchParams()
  if (args.runDir) qp.set('run_dir', args.runDir)
  const suffix = qp.toString() ? `?${qp.toString()}` : ''
  return await apiDownload(
    `/api/v1/download/${encodeURIComponent(args.jobId)}/${args.filePath}${suffix}`,
  )
}
