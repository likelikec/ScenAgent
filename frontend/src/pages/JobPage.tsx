import { useState, useEffect, useRef } from 'react'
import {
  Avatar,
  Alert,
  Box,
  Button,
  Group,
  Loader,
  Paper,
  ScrollArea,
  Stack,
  Text,
  ThemeIcon,
  Center,
} from '@mantine/core'
import {
  IconPlayerPlay,
  IconPlayerStop,
  IconReportAnalytics,
  IconUser,
} from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { Link, useLocation, useParams } from 'react-router-dom'
import { downloadArtifact, getJobStatus, stopJob } from '../api/mobileV4'
import type { JobStatus } from '../api/types'
import { ApiError, getApiBaseUrl } from '../api/client'
import { blobToText } from '../utils/download'
import { DeviceEmulator } from '../components/DeviceEmulator'
import { useLogParser } from '../hooks/useLogParser'
import type { ScriptData } from '../components/ScriptTimeline'
import { JobReportPage } from './JobReportPage'
import { ErrorBoundary } from '../components/ErrorBoundary'

export function JobPage() {
  const { jobId } = useParams()
  const id = jobId || ''
  const location = useLocation()
  
  // Initial User Prompt from Home Page
  const userPrompt = location.state?.userPrompt || ''

  // State
  const [logText, setLogText] = useState('')
  const [scriptJson] = useState<ScriptData | null>(null)
  const [currentScreenshot, setCurrentScreenshot] = useState<string | undefined>(undefined)
  const [stopError, setStopError] = useState<string | null>(null)
  const viewport = useRef<HTMLDivElement>(null)
  const currentScreenshotUrlRef = useRef<string | null>(null)

  // Job Status
  const query = useQuery<JobStatus>({
    queryKey: ['job', id],
    queryFn: () => getJobStatus(id),
    enabled: !!id,
    retry: 1,
    refetchInterval: (query) => {
      if (query.state.error) return false
      const data = query.state.data
      if (!data) return 1500
      if (data.status === 'running' || data.status === 'queued') return 1500
      return false
    },
  })
  
  const status = query.data?.status
  const isRunning = status === 'running' || status === 'queued'
  const isFinished = status === 'success' || status === 'failed'
  const runDir = query.data?.run_dir

  // Parse Logs
  const timelineItems = useLogParser(logText, scriptJson?.total_plan || userPrompt)

  // Filter out thought items as requested
  const visibleItems = timelineItems.filter(item => item.type !== 'thought')

  // --- Hooks must be called before any early return ---

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (viewport.current) {
      viewport.current.scrollTo({ top: viewport.current.scrollHeight, behavior: 'smooth' })
    }
  }, [visibleItems.length])

  // Poll Logs
  useEffect(() => {
    if (!id || !runDir) return
    
    async function fetchLog() {
      try {
        const blob = await downloadArtifact({ jobId: id, filePath: 'stdout', runDir: runDir! })
        const text = await blobToText(blob)
        setLogText(text)
      } catch { /* ignore */ }
    }

    fetchLog()
    if (isRunning) {
      const timer = setInterval(fetchLog, 2000)
      return () => clearInterval(timer)
    }
  }, [id, runDir, isRunning])

  // Poll Script & Screenshot
  useEffect(() => {
    if (!id || !runDir) return

    let timer: number | undefined

    async function fetchLatestScreenshot() {
      try {
        const imgBlob = await downloadArtifact({ jobId: id, filePath: 'latest_screenshot', runDir: runDir! })
        const nextUrl = URL.createObjectURL(imgBlob)
        if (currentScreenshotUrlRef.current) {
          URL.revokeObjectURL(currentScreenshotUrlRef.current)
        }
        currentScreenshotUrlRef.current = nextUrl
        setCurrentScreenshot(nextUrl)
      } catch (e: unknown) {
        if (e instanceof ApiError && e.status === 404) {
          if (currentScreenshotUrlRef.current) {
            URL.revokeObjectURL(currentScreenshotUrlRef.current)
            currentScreenshotUrlRef.current = null
          }
          setCurrentScreenshot(undefined)
          return
        }
      }
    }

    fetchLatestScreenshot()
    if (isRunning) {
      timer = window.setInterval(fetchLatestScreenshot, 1500)
    }

    return () => {
      if (timer) window.clearInterval(timer)
    }
  }, [id, runDir, isRunning])

  // --- Early Returns ---

  // Auto-switch to Report View if finished
  if (isFinished) {
    return (
      <ErrorBoundary fallback={
        <Center h="calc(100vh - 48px)">
          <Stack align="center" gap="md">
            <Alert title="加载报告失败" color="red" maw={600}>
              任务已结束，但在生成报告视图时出错。可能是产物数据（script.json）格式不正确。
            </Alert>
            <Button variant="light" component={Link} to={`/jobs/${id}/report`}>
              尝试直接访问报告页面
            </Button>
          </Stack>
        </Center>
      }>
        <JobReportPage />
      </ErrorBoundary>
    )
  }

  if (!id) {
    return (
      <Center h="calc(100vh - 48px)">
        <Stack align="center" gap="sm">
          <Alert title="job_id 缺失" color="red" maw={560}>
            当前页面缺少 job_id 路由参数，无法查询任务状态。
          </Alert>
          <Button component={Link} to="/run" variant="light">
            返回发起任务
          </Button>
        </Stack>
      </Center>
    )
  }

  // If loading and no data yet, show centered loader
  if (query.isLoading && !query.data) {
    return (
      <Center h="calc(100vh - 48px)">
        <Stack align="center" gap="md">
          <Loader size="xl" type="dots" color="blue" />
          <Text c="dimmed" fw={500}>Connecting to Agent...</Text>
        </Stack>
      </Center>
    )
  }

  if (query.isError) {
    const apiBaseUrl = getApiBaseUrl()
    return (
      <Center h="calc(100vh - 48px)">
        <Stack gap="sm" maw={720} w="100%" px="md">
          <Alert title="无法加载任务详情" color="red">
            <Stack gap={6}>
              <Text size="sm">
                {toErrorText(query.error)}
              </Text>
              <Text size="xs" c="dimmed">
                当前 API_BASE_URL：{apiBaseUrl}
              </Text>
              <Text size="xs" c="dimmed">
                页面地址 5173 是前端；任务数据需要通过 API_BASE_URL 访问后端（例如 8000）。
              </Text>
            </Stack>
          </Alert>
          <Group justify="flex-end">
            <Button component={Link} to="/settings" variant="light">
              去设置检查 API_BASE_URL
            </Button>
            <Button variant="default" onClick={() => query.refetch()}>
              重试
            </Button>
          </Group>
        </Stack>
      </Center>
    )
  }

  if (!query.data) {
    return (
      <Center h="calc(100vh - 48px)">
        <Stack align="center" gap="sm" maw={720} w="100%" px="md">
          <Alert title="未获取到任务信息" color="yellow">
            <Stack gap={6}>
              <Text size="sm">暂时没有拿到任务状态数据。</Text>
              <Text size="xs" c="dimmed">
                如果这是刚创建的任务，请稍后重试；如果持续为空，请检查设置中的 API_BASE_URL 是否指向正确后端。
              </Text>
            </Stack>
          </Alert>
          <Group justify="flex-end">
            <Button component={Link} to="/settings" variant="light">
              去设置
            </Button>
            <Button variant="default" onClick={() => query.refetch()}>
              重试
            </Button>
          </Group>
        </Stack>
      </Center>
    )
  }

  async function onStop() {
    if (!id) return
    setStopError(null)
    try {
      await stopJob(id)
      query.refetch()
    } catch {
      setStopError('无法停止任务：后端不可访问或 API_BASE_URL 配置错误')
    }
  }

  return (
    <Box style={{ height: 'calc(100vh - 48px)', display: 'flex', overflow: 'hidden' }}>
        {/* Left Panel: Interaction Stream */}
        <Box style={{ 
            width: '42%', 
            borderRight: '1px solid rgba(255,255,255,0.1)', 
            display: 'flex', 
            flexDirection: 'column',
            overflow: 'hidden'
        }}>
            {/* Header */}
            <Box p="md" style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', flexShrink: 0 }}>
                    {stopError ? (
                      <Alert color="red" mb="sm" title="停止失败">
                        {stopError}
                      </Alert>
                    ) : null}
                    <Group justify="space-between">
                        <Stack gap={0}>
                            <Text fw={700} size="lg">Agent Interaction</Text>
                            <Group gap={6}>
                                <Box w={8} h={8} bg={isRunning ? 'green' : status === 'failed' ? 'red' : 'gray'} style={{ borderRadius: '50%' }} />
                                <Text size="xs" c="dimmed" fw={600} tt="uppercase">{status || 'Initializing...'}</Text>
                            </Group>
                        </Stack>
                        <Group>
                            {!isRunning && (
                                <Button component={Link} to={`/jobs/${id}/report`} variant="light" size="xs" leftSection={<IconReportAnalytics size={14} />}>
                                    Full Report
                                </Button>
                            )}
                            {isRunning && (
                                <Button color="red" variant="subtle" size="xs" onClick={onStop} leftSection={<IconPlayerStop size={14} />}>
                                    Stop
                                </Button>
                            )}
                        </Group>
                    </Group>
                </Box>

                {/* Chat Area */}
                <ScrollArea type="auto" p="md" viewportRef={viewport} style={{ flex: 1 }}>
                    <Stack gap="lg" pb="md">
                        {visibleItems.length === 0 && (
                            <Text c="dimmed" size="sm" ta="center" mt="xl">Initializing Environment</Text>
                        )}

                        {visibleItems.map((item) => (
                            <Group 
                                key={item.id} 
                                align="flex-start" 
                                justify={item.type === 'user' ? 'flex-end' : 'flex-start'}
                                wrap="nowrap"
                            >
                                {item.type !== 'user' && (
                                    <ThemeIcon 
                                        size={32} 
                                        radius="xl" 
                                        variant="filled"
                                        color="blue"
                                    >
                                        <IconPlayerPlay size={18} />
                                    </ThemeIcon>
                                )}
                                
                                <Paper 
                                    p="sm" 
                                    radius="lg" 
                                    shadow="sm"
                                    bg={item.type === 'user' ? 'blue.6' : 'white'}
                                    style={{ 
                                        maxWidth: '85%',
                                        borderTopLeftRadius: item.type === 'user' ? 16 : 4,
                                        borderTopRightRadius: item.type === 'user' ? 4 : 16,
                                        border: item.type !== 'user' ? '1px solid var(--kane-border)' : 'none',
                                        color: item.type === 'user' ? 'white' : 'inherit',
                                    }}
                                >
                                    <Text size="xs" c={item.type === 'user' ? 'white' : 'dimmed'} mb={4} fw={700} style={{ opacity: 0.8 }}>
                                        {item.agent || 'User'}
                                    </Text>
                                    <Text size="sm" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>
                                        {item.content}
                                    </Text>
                                </Paper>

                                {item.type === 'user' && (
                                    <Avatar radius="xl" color="blue" variant="filled">
                                        <IconUser size={20} />
                                    </Avatar>
                                )}
                            </Group>
                        ))}
                                
                        {isRunning && (
                            <Group justify="flex-start" wrap="nowrap">
                                <Loader size="xs" type="dots" ml={48} />
                            </Group>
                        )}
                    </Stack>
                </ScrollArea>
        </Box>

        {/* Right Panel: Device Mirror */}
        <Box style={{ 
            flex: 1, 
            backgroundColor: 'var(--mantine-color-gray-0)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: 'var(--mantine-spacing-md)',
            overflow: 'hidden'
        }}>
            <Box style={{ transform: 'scale(1)', transformOrigin: 'center center', maxHeight: '100%' }}>
                <DeviceEmulator 
                    screenshotUrl={currentScreenshot} 
                />
            </Box>
        </Box>
    </Box>
  )
}

function toErrorText(err: unknown): string {
  if (err instanceof Error) return err.message
  return String(err)
}