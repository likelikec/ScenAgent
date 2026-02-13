import {
  Badge,
  Button,
  Card,
  Group,
  Stack,
  Text,
  Tabs,
  Code,
  Grid,
  ThemeIcon,
  Loader,
  Container,
  Center,
  ActionIcon,
  Slider,
  Box,
  Select,
  ScrollArea,
} from '@mantine/core'
import {
  IconDownload,
  IconPlayerStop,
  IconRefresh,
  IconTerminal2,
  IconTimeline,
  IconPlayerPlay,
  IconPlayerPause,
  IconPlayerSkipBack,
  IconPlayerSkipForward,
  IconFileText,
  IconFileCode,
  IconFileZip,
  IconDeviceTv,
} from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { downloadArtifact, getJobStatus, stopJob } from '../api/mobileV4'
import type { JobStatus } from '../api/types'
import { ApiError, getApiBaseUrl } from '../api/client'
import { blobToText, extractFilename, saveBlobAs } from '../utils/download'
import { useI18n } from '../useI18n'
import { ScriptTimeline, type ScriptData } from '../components/ScriptTimeline'
import { ChatLogPreview } from '../components/ChatLogPreview'
import { useCallback, useMemo, useState, useEffect } from 'react'

const aliasList = [
  { key: 'task_results', filename: 'task_results.json', labelKey: 'job.artifacts.taskResults', icon: IconFileText, color: 'blue' },
  { key: 'script', filename: 'script.json', labelKey: 'job.artifacts.script', icon: IconFileCode, color: 'violet' },
  { key: 'zip', filename: 'run.zip', labelKey: 'job.artifacts.zip', icon: IconFileZip, color: 'teal' },
]

export function JobReportPage() {
  const { jobId } = useParams()
  const id = jobId || ''
  const { t } = useI18n()

  const defaultChatLog = `{"step": 1, "role": "planner", "output": "1. Click the \\"+ 新习惯\\" button at the bottom right to start creating a new habit. 2. Input the habit name \\"Drink water daily\\" into the habit name field. 3. Click the confirmation or save button (typically labeled \\"Save\\", \\"Add\\", or a checkmark icon) to create the habit. 4. If the app navigates away from the main page after saving, return to the main habit list page (e.g., via back button or home icon). 5. Observe the habit list and verify that \\"Drink water daily\\" appears as a new entry (expected to be the last item, i.e., fourth habit). 6. Execute the \`answer\` action."}
{"step": 1, "role": "operator", "output": "### Thought ###\\nThe current screen shows the main habit list with three existing habits. The subgoal is to start creating a new habit by clicking the \\"+ 新习惯\\" button at the bottom right. This button is clearly visible and labeled appropriately for adding a new habit, matching step 1 of the global plan. Clicking it will likely navigate to the habit creation interface.\\n\\n### Action ###\\n{\\"action\\": \\"click\\", \\"coordinate\\": [826, 944]}\\n\\n### Description ###\\nClick the \\"+ 新习惯\\" button at the bottom right to initiate creating a new habit."}
{"step": 1, "role": "action_reflector", "output": "S"}
{"step": 2, "role": "planner", "output": "1. Type \\"Drink water daily\\" into the habit name field. 2. Click the confirmation or save button (typically labeled \\"Save\\", \\"Add\\", or a checkmark icon) to create the habit. 3. If the app navigates away from the main page after saving, return to the main habit list page (e.g., via back button or home icon). 4. Observe the habit list and verify that \\"Drink water daily\\" appears as a new entry (expected to be the last item, i.e., fourth habit). 5. Execute the \`answer\` action."}
{"step": 2, "role": "operator", "output": "### Thought ###\\nThe current screen shows the habit creation interface with the habit name field (\\"习惯名称...\\") visible and the soft keyboard already open. Since the ADB Keyboard is active (indicated by the visible keyboard), I can directly type into the input field. The next step in the global plan is to enter \\"Drink water daily\\" into the habit name field. Therefore, the most appropriate action is to type the specified text.\\n\\n### Action ###\\n{\\"action\\": \\"type\\", \\"text\\": \\"Drink water daily\\"}\\n\\n### Description ###\\nType \\"Drink water daily\\" into the currently active habit name input field."}
{"step": 2, "role": "action_reflector", "output": "S"}
{"step": 3, "role": "planner", "output": "1. Click the \\"保存\\" button at the top right to save the new habit. 2. If the app navigates back to the main habit list automatically, proceed to step 3; otherwise, press the back button or tap the home/list icon to return to the main habit list page. 3. Observe the habit list and verify that \\"Drink water daily\\" appears as a new entry (expected to be the last item, i.e., fourth habit). 4. Execute the \`answer\` action."}
{"step": 3, "role": "operator", "output": "### Thought ###\\nThe habit name \\"Drink water daily\\" has been successfully entered. The next step in the global plan is to save the new habit by clicking the \\"保存\\" button located at the top right of the screen. This action will commit the habit creation and likely navigate back to the main habit list, enabling verification of its position.\\n\\n### Action ###\\n{\\"action\\": \\"click\\", \\"coordinate\\": [911, 77]}\\n\\n### Description ###\\nClick the \\"保存\\" button at the top right to save the newly created habit."}
{"step": 3, "role": "action_reflector", "output": "S"}
{"step": 4, "role": "planner", "output": "Finished"}
{"step": 4, "role": "task_judge", "output": "Task Status: Success\\nStatus Reason: The habit 'Drink water daily' was successfully created and appears in the habit list on the main page, confirming its position as the last item."}`

  const [activeTab, setActiveTab] = useState<string | null>('playback')
  const [logText, setLogText] = useState('')
  const [logLoading, setLogLoading] = useState(false)
  
  // Script Data for Timeline
  const [scriptJson, setScriptJson] = useState<ScriptData | null>(null)
  // Task Results for Goal
  const [taskResults, setTaskResults] = useState<{ goal?: string } | null>(null)

  const [chatLogText, setChatLogText] = useState(defaultChatLog)
  
  const query = useQuery<JobStatus, ApiError>({
    queryKey: ['job', id],
    queryFn: () => getJobStatus(id),
    enabled: !!id,
    refetchInterval: (q) => {
      const status = q.state.data?.status
      if (!status) return 1500
      if (status === 'running' || status === 'queued') return 1500
      return false
    },
  })

  const status = query.data?.status
  const isRunning = status === 'running' || status === 'queued'
  const runDir = query.data?.run_dir ?? undefined

  // Auto-switch to Terminal if running and script not ready
  useEffect(() => {
    if (isRunning && !scriptJson && activeTab === 'playback') {
      // Keep playback active but show loader, OR switch to terminal
      // Let's keep playback active but show a "Waiting" state
    }
  }, [isRunning, scriptJson, activeTab])

  // Poll for stdout log if active tab is terminal
  useEffect(() => {
    let timer: number | undefined
    async function fetchLog() {
      if (!id || !runDir) return
      try {
        setLogLoading(true)
        const blob = await downloadArtifact({ jobId: id, filePath: 'stdout', runDir })
        const text = await blobToText(blob)
        setLogText(text)
      } catch {
        // ignore 404
      } finally {
        setLogLoading(false)
      }
    }

    if (activeTab === 'terminal') {
      fetchLog()
      if (isRunning) {
        timer = window.setInterval(fetchLog, 2000)
      }
    }
    return () => {
      if (timer) window.clearInterval(timer)
    }
  }, [id, runDir, activeTab, isRunning])

  // Fetch Script JSON & Task Results
  useEffect(() => {
    async function fetchScript() {
      if (!id || !runDir) return
      try {
        const blob = await downloadArtifact({ jobId: id, filePath: 'script', runDir })
        const text = await blobToText(blob)
        const json = JSON.parse(text) as ScriptData
        setScriptJson(json)
      } catch {
        // ignore
      }
    }

    async function fetchTaskResults() {
      if (!id || !runDir) return
      try {
        const blob = await downloadArtifact({ jobId: id, filePath: 'task_results', runDir })
        const text = await blobToText(blob)
        const json = JSON.parse(text)
        setTaskResults(json)
      } catch {
        // ignore
      }
    }

    if (activeTab === 'playback') {
      if (!scriptJson) fetchScript()
      if (!taskResults) fetchTaskResults()
      
      // Retry if running
      if (isRunning) {
        const interval = setInterval(() => {
           if (!scriptJson) fetchScript()
           if (!taskResults) fetchTaskResults()
        }, 3000)
        return () => clearInterval(interval)
      }
    }
  }, [id, runDir, activeTab, isRunning, scriptJson, taskResults])

  useEffect(() => {
    async function fetchChatLog() {
      if (!id || !runDir) return
      try {
        const blob = await downloadArtifact({ jobId: id, filePath: 'chat_log', runDir })
        const text = await blobToText(blob)
        setChatLogText(text)
      } catch {
        // ignore 404
      }
    }

    if (activeTab === 'playback') {
      fetchChatLog()
    }
  }, [id, runDir, activeTab])

  async function onStop() {
    if (!id) return
    try {
      await stopJob(id)
      query.refetch()
    } catch (e) {
      console.error(e)
    }
  }

  async function onDownload(key: string, filename: string) {
    if (!id || !runDir) return
    try {
      const blob = await downloadArtifact({ jobId: id, filePath: key, runDir })
      await saveBlobAs(blob, filename)
    } catch (e) {
      console.error(e)
    }
  }

  const getImgUrl = useCallback((absPath: string) => {
    if (!absPath) return ''
    const filename = extractFilename(absPath)
    const base = getApiBaseUrl()
    const qp = new URLSearchParams()
    if (runDir) qp.set('run_dir', runDir)
    return `${base}/api/v1/download/${encodeURIComponent(id)}/images/${encodeURIComponent(filename)}?${qp.toString()}`
  }, [id, runDir])

  const playbackImages = useMemo(() => {
    if (!scriptJson || !scriptJson.subgoals) return []
    const images: string[] = []
    try {
      scriptJson.subgoals.forEach(sub => {
        if (sub && sub.info && Array.isArray(sub.info.picture)) {
          sub.info.picture.forEach(pic => {
            if (pic) {
              if (pic.last) images.push(getImgUrl(pic.last))
              if (pic.next) images.push(getImgUrl(pic.next))
            }
          })
        }
      })
    } catch (e) {
      console.error('Error processing playback images:', e)
    }
    // Deduplicate consecutive identical URLs
    return images.filter((url, i) => url !== images[i - 1])
  }, [scriptJson, getImgUrl])

  // Playback Player State
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [playbackSpeed, setPlaybackSpeed] = useState(800) // ms per frame

  useEffect(() => {
    let timer: number | undefined
    if (isPlaying && playbackImages.length > 0) {
      timer = window.setInterval(() => {
        setCurrentIndex((prev) => {
          if (prev >= playbackImages.length - 1) {
            setIsPlaying(false)
            return prev
          }
          return prev + 1
        })
      }, playbackSpeed)
    }
    return () => {
      if (timer) clearInterval(timer)
    }
  }, [isPlaying, playbackImages.length, playbackSpeed])

  return (
    <Container fluid px="xl" py="sm" style={{ height: 'calc(100vh - 48px)', display: 'flex', flexDirection: 'column' }}>
      <Stack gap="sm" style={{ flex: 1, minHeight: 0 }}>
        {/* Header */}
        <Group justify="space-between" align="flex-end">
          <Stack gap={0}>
            <Group gap="xs">
              <Text fw={800} size="lg" style={{ letterSpacing: '-0.5px' }}>{t('job.title')}</Text>
              <Badge 
                size="sm" 
                variant="light"
                color={
                  status === 'success' ? 'teal' : 
                  status === 'failed' ? 'red' : 
                  'indigo'
                }
                radius="sm"
              >
                {status || 'loading...'}
              </Badge>
            </Group>
            <Text c="dimmed" style={{ fontSize: '10px' }} ff="JetBrains Mono">ID: {id}</Text>
          </Stack>
          
          <Group gap="xs">
            <Button variant="light" color="gray" size="xs" radius="md" leftSection={<IconRefresh size={12} />} onClick={() => query.refetch()}>
              {t('job.refresh')}
            </Button>
            {isRunning && (
              <Button color="red" variant="light" size="xs" radius="md" leftSection={<IconPlayerStop size={12} />} onClick={onStop}>
                {t('artifacts.stop')}
              </Button>
            )}
          </Group>
        </Group>

        <Tabs
          value={activeTab}
          onChange={setActiveTab}
          variant="pills"
          radius="md"
          style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}
          styles={{
            root: { display: 'flex', flexDirection: 'column', minHeight: 0 },
            panel: { flex: 1, minHeight: 0, paddingTop: '12px' }
          }}
        >
          <Tabs.List style={{ display: 'flex', gap: '8px' }}>
            <Tabs.Tab value="playback" leftSection={<IconDeviceTv size={14} />} py={4} styles={{ tabLabel: { fontSize: '12px' } }}>
              {t('job.testRecord')}
            </Tabs.Tab>
            <Tabs.Tab value="smart_playback" leftSection={<IconTimeline size={14} />} py={4} styles={{ tabLabel: { fontSize: '12px' } }}>
              {t('job.smartTimeline')}
            </Tabs.Tab>
            <Tabs.Tab value="terminal" leftSection={<IconTerminal2 size={14} />} py={4} styles={{ tabLabel: { fontSize: '12px' } }}>
              {t('job.liveTerminal')}
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="playback" style={{ height: '100%', minHeight: 0 }}>
            <Grid gutter="sm" style={{ height: '100%', minHeight: 0 }}>
              {/* Left: Playback Player */}
              <Grid.Col span={{ base: 12, lg: 7 }} style={{ height: '100%', minHeight: 0 }}>
                {playbackImages.length > 0 ? (
                  <Center h="100%">
                    <Stack gap="xs" align="center" style={{ width: '100%', height: '100%', justifyContent: 'center' }}>
                      <Card 
                        radius="xl" 
                        p={0} 
                        withBorder 
                        shadow="xl" 
                        bg="black"
                        style={{ 
                          width: '100%',
                          maxWidth: 260, // Further reduced width
                          flex: 1,
                          maxHeight: 'calc(100% - 10px)',
                          borderColor: '#2D3748',
                          overflow: 'hidden',
                          position: 'relative',
                          display: 'flex',
                          flexDirection: 'column'
                        }}
                      >
                        <Box style={{ position: 'relative', width: '100%', flex: 1, overflow: 'hidden' }}>
                          <img 
                            src={playbackImages[currentIndex]} 
                            alt={`Frame ${currentIndex}`} 
                            style={{ width: '100%', height: '100%', objectFit: 'contain' }} 
                          />
                          
                          <Box 
                            p="xs"
                            style={{ 
                              position: 'absolute', 
                              bottom: 0, 
                              left: 0, 
                              right: 0, 
                              background: 'linear-gradient(transparent, rgba(0,0,0,0.98))',
                              zIndex: 10
                            }}
                          >
                            <Stack gap={4}>
                              <Slider
                                value={currentIndex}
                                onChange={setCurrentIndex}
                                max={playbackImages.length - 1}
                                color="indigo"
                                size="xs"
                                label={null}
                              />
                              
                              <Group justify="space-between">
                                <Group gap={2}>
                                  <ActionIcon 
                                    variant="subtle" 
                                    color="white" 
                                    size="xs"
                                    onClick={() => setCurrentIndex(0)}
                                  >
                                    <IconPlayerSkipBack size={14} />
                                  </ActionIcon>
                                  
                                  <ActionIcon 
                                    variant="filled" 
                                    color="indigo" 
                                    radius="xl" 
                                    size="sm"
                                    onClick={() => setIsPlaying(!isPlaying)}
                                  >
                                    {isPlaying ? <IconPlayerPause size={16} /> : <IconPlayerPlay size={16} />}
                                  </ActionIcon>
                                  
                                  <ActionIcon 
                                    variant="subtle" 
                                    color="white" 
                                    size="xs"
                                    onClick={() => setCurrentIndex((p) => Math.min(p + 1, playbackImages.length - 1))}
                                  >
                                    <IconPlayerSkipForward size={14} />
                                  </ActionIcon>
                                </Group>
                                
                                <Select
                                  size="xs"
                                  w={60}
                                  variant="unstyled"
                                  value={playbackSpeed.toString()}
                                  onChange={(v: string | null) => setPlaybackSpeed(parseInt(v || '800'))}
                                  data={[
                                    { label: '0.5x', value: '1500' },
                                    { label: '1.0x', value: '800' },
                                    { label: '2.0x', value: '400' },
                                  ]}
                                  allowDeselect={false}
                                  styles={{ input: { color: 'white', fontSize: '9px', textAlign: 'right', minHeight: 20 } }}
                                />
                              </Group>
                            </Stack>
                          </Box>
                        </Box>
                      </Card>
                    </Stack>
                  </Center>
                ) : (
                  <Center h="100%">
                    <Stack align="center" gap="xs" c="dimmed">
                      <Loader size="xs" />
                      <Text style={{ fontSize: '10px' }}>Awaiting frames...</Text>
                    </Stack>
                  </Center>
                )}
              </Grid.Col>

              {/* Right: Artifact Cards & Chat */}
              <Grid.Col span={{ base: 12, lg: 5 }} style={{ height: '100%', minHeight: 0 }}>
                <ScrollArea h="100%" type="auto" offsetScrollbars>
                  <Stack gap="sm" pr="md">
                    <Text fw={800} size="xs" tt="uppercase" c="dimmed" style={{ letterSpacing: '1px' }}>
                      {t('job.artifacts.desc')}
                    </Text>
                    {aliasList.map((item) => (
                      <Card 
                        key={item.key}
                        radius="md" 
                        p="xs" 
                        className="artifact-card"
                        style={{ 
                          border: '1px solid var(--kane-border)',
                          background: 'white'
                        }}
                      >
                        <Group justify="space-between" wrap="nowrap">
                          <Group gap="xs" wrap="nowrap">
                            <ThemeIcon 
                              variant="light" 
                              size={32} 
                              radius="md" 
                              color={item.color}
                            >
                              <item.icon size={18} stroke={1.5} />
                            </ThemeIcon>
                            <Stack gap={0}>
                              <Text fw={700} size="xs" lineClamp={1}>{t(item.labelKey)}</Text>
                              <Text style={{ fontSize: '9px' }} c="dimmed" ff="JetBrains Mono" lineClamp={1}>{item.filename}</Text>
                            </Stack>
                          </Group>
                          <ActionIcon 
                            variant="light" 
                            size="sm" 
                            radius="md"
                            onClick={() => onDownload(item.key, item.filename)} 
                            color={item.color}
                          >
                            <IconDownload size={14} />
                          </ActionIcon>
                        </Group>
                      </Card>
                    ))}
                    
                    <Card radius="md" p="xs" withBorder style={{ flex: 1, minHeight: 260, display: 'flex', flexDirection: 'column' }}>
                       <Group gap="xs" mb={4}>
                          <IconFileText size={14} color="indigo" />
                          <Text style={{ fontSize: '10px' }} fw={800} c="dimmed" tt="uppercase">Chat Log</Text>
                       </Group>
                       <Box p="xs" style={{ borderRadius: 8 }}>
                         {chatLogText ? <ChatLogPreview jsonl={chatLogText} maxHeight={300} /> : <Text size="xs" c="dimmed" ta="center" py="xl">No data</Text>}
                       </Box>
                    </Card>
                  </Stack>
                </ScrollArea>
              </Grid.Col>
            </Grid>
          </Tabs.Panel>

          <Tabs.Panel value="smart_playback" style={{ height: '100%', minHeight: 0 }}>
            <Stack gap="md" style={{ height: '100%', minHeight: 0 }}>
              <Card radius="lg" p="md" style={{ borderLeft: '4px solid var(--kane-accent)', background: 'white' }}>
                <Text fw={800} mb={4} c="indigo" size="xs" tt="uppercase" style={{ letterSpacing: '1px' }}>{t('run.targetTask')}</Text>
                <Text size="md" fw={600} style={{ lineHeight: 1.4 }}>
                  {taskResults?.goal || scriptJson?.total_plan}
                </Text>
              </Card>
              {scriptJson && (
                <Box style={{ flex: 1, minHeight: 0 }}>
                  <ScriptTimeline data={scriptJson} jobId={id} runDir={runDir} />
                </Box>
              )}
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="terminal" style={{ height: '100%', minHeight: 0 }}>
             <Card radius="lg" p="md" bg="#1A1B1E" h="100%" style={{ border: '1px solid #2D3748', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <Group justify="space-between" mb="xs">
                  <Text c="dimmed" fw={800} size="xs" tt="uppercase" style={{ letterSpacing: '1px' }}>stdout.log</Text>
                  <ActionIcon variant="subtle" color="indigo" onClick={() => onDownload('stdout', 'stdout.log')}>
                    <IconDownload size={18} />
                  </ActionIcon>
                </Group>
                <ScrollArea style={{ flex: 1 }} type="auto" offsetScrollbars>
                  <Code block bg="transparent" c="indigo.1" style={{ fontSize: '12px', whiteSpace: 'pre-wrap', fontFamily: 'JetBrains Mono, monospace' }}>
                    {logText || (logLoading ? 'Streaming...' : 'No logs.')}
                  </Code>
                </ScrollArea>
             </Card>
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Container>
  )
}
