export type ScenarioRef =
  | { type: 'uploaded'; value: string }
  | { type: 'path'; value: string }
  | { type: 'inline'; value: Record<string, unknown> }

export type ApkRef =
  | { type: 'uploaded'; value: string }
  | { type: 'path'; value: string }

export type SimpleTaskData = {
  task_description: string
  package_name: string
  launch_activity?: string | null
  app_name?: string | null
}

export type BackendConfig = {
  api_key?: string | null
  base_url?: string | null
  model?: string | null
  summary_api_key?: string | null
  summary_base_url?: string | null
  summary_model?: string | null
}

export type RunRequest = {
  user_id?: string | null
  mode: 'single' | 'range' | 'batch'
  scenario_ref?: ScenarioRef | null
  apk_ref?: ApkRef | null
  simple_task?: SimpleTaskData | null
  app_id?: string | null
  scenario_id?: string | null
  scenario_start_id?: string | null
  scenario_end_id?: string | null
  run_config?: Array<Record<string, unknown>>
  device_profile?: string | null
  device_selector?: Record<string, unknown> | null
  model_profile?: string | null
  lang?: string | null
}

export type RunResponse = {
  job_id: string
  status: string
  created_at: string
}

export type JobStatus = {
  job_id: string
  status: 'queued' | 'running' | 'success' | 'failed' | 'stopped' | string
  created_at?: string | null
  started_at?: string | null
  finished_at?: string | null
  run_dir?: string | null
  run_dirs?: string[]
  error?: string | null
  artifacts?: Record<string, unknown>
  device_id?: string | null
  device_snapshot?: unknown
  command?: string[] | null
}
