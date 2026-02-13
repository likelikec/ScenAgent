import { Badge, Card, Code, Grid, Group, Image, Modal, Stack, Text, ThemeIcon, Timeline, Box } from '@mantine/core'
import { IconBolt, IconCheck, IconPhoto, IconClick, IconKeyboard, IconPointer } from '@tabler/icons-react'
import { useCallback, useMemo, useState } from 'react'
import { getApiBaseUrl } from '../api/client'
import { extractFilename } from '../utils/download'

export interface ScriptSubgoal {
  subgoal: string
  info: {
    opter: string
    picture: Array<{
      last: string
      next: string
    }>
  }
}

export interface ScriptData {
  total_plan: string
  subgoals: ScriptSubgoal[]
}

interface ScriptTimelineProps {
  data: ScriptData
  jobId: string
  runDir?: string
}

// Helper to get icon based on action text
function getActionIcon(action: string) {
  const lower = action.toLowerCase()
  if (lower.includes('click') || lower.includes('tap')) return <IconPointer size={14} />
  if (lower.includes('input') || lower.includes('type')) return <IconKeyboard size={14} />
  if (lower.includes('wait')) return <IconBolt size={14} />
  return <IconCheck size={14} />
}

export function ScriptTimeline({ data, jobId, runDir }: ScriptTimelineProps) {
  const [activeStep, setActiveStep] = useState(0)
  const [modalImage, setModalImage] = useState<string | null>(null)

  // Construct image URL helper
  const getImgUrl = useCallback((absPath: string) => {
    if (!absPath) return ''
    const filename = extractFilename(absPath)
    // Use the download API to fetch the image
    // GET /api/v1/download/{jobId}/images/{filename}?run_dir={runDir}
    const base = getApiBaseUrl()
    const qp = new URLSearchParams()
    if (runDir) qp.set('run_dir', runDir)
    return `${base}/api/v1/download/${encodeURIComponent(jobId)}/images/${encodeURIComponent(filename)}?${qp.toString()}`
  }, [jobId, runDir])

  const steps = useMemo(() => {
    if (!data || !Array.isArray(data.subgoals)) return []
    
    return data.subgoals.map((sub, idx) => {
      if (!sub || !sub.info) {
        return {
          idx,
          plan: 'Unknown Step',
          action: 'Unknown Action',
          lastImg: null,
          nextImg: null,
        }
      }

      const pictures = Array.isArray(sub.info.picture) ? sub.info.picture : []
      const picPair = pictures.length > 0 ? pictures[pictures.length - 1] : null
      
      // Clean text: remove leading "1. " and trailing " 2"
      let cleanPlan = sub.subgoal || 'No description'
      cleanPlan = cleanPlan.replace(/^\d+\.\s*/, '') // Remove start number
      cleanPlan = cleanPlan.replace(/\s*\d+$/, '')   // Remove end number

      return {
        idx,
        plan: cleanPlan,
        action: sub.info.opter || 'N/A',
        lastImg: picPair?.last ? getImgUrl(picPair.last) : null,
        nextImg: picPair?.next ? getImgUrl(picPair.next) : null,
      }
    })
  }, [data, getImgUrl])

  return (
    <>
      <Box style={{ height: '100%', minHeight: 0, overflow: 'hidden' }}>
        <Grid
          gutter="md"
          style={{ height: '100%' }}
          styles={{ root: { height: '100%' }, inner: { height: '100%' } }}
        >
          {/* Left: Timeline Navigation */}
          <Grid.Col span={{ base: 12, md: 4 }} style={{ height: '100%', minHeight: 0, display: 'flex' }}>
            <Card p="md" radius="lg" withBorder shadow="sm" className="timeline-card" style={{ height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 }}>
              <Text fw={800} mb="md" size="xs" tt="uppercase" c="dimmed" style={{ letterSpacing: '1px' }}>Execution Steps</Text>
              <Box style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
                <Timeline active={activeStep} bulletSize={28} lineWidth={2} color="indigo">
                  {steps.map((s, i) => (
                    <Timeline.Item
                      key={i}
                      bullet={activeStep === i ? <IconBolt size={16} /> : getActionIcon(s.action)}
                      title={
                        <Group justify="space-between" wrap="nowrap">
                          <Text size="xs" fw={activeStep === i ? 800 : 600} c={activeStep === i ? 'indigo' : 'dark'} style={{ cursor: 'pointer' }} onClick={() => setActiveStep(i)}>
                            Step {i + 1}
                          </Text>
                          {activeStep === i && <Badge size="9px" variant="light" color="indigo" radius="xs">Active</Badge>}
                        </Group>
                      }
                    >
                      <Card
                        p="xs"
                        radius="md"
                        withBorder
                        shadow="sm"
                        style={{
                          cursor: 'pointer',
                          transition: 'background 0.2s ease, border-color 0.2s ease',
                          background: activeStep === i ? 'var(--mantine-color-indigo-0)' : 'white',
                          borderColor: activeStep === i ? 'var(--mantine-color-indigo-2)' : 'var(--kane-border)'
                        }}
                        onClick={() => setActiveStep(i)}
                      >
                        <Text c={activeStep === i ? 'indigo.9' : 'dimmed'} size="xs" lineClamp={2} fw={activeStep === i ? 700 : 500}>
                          {s.plan}
                        </Text>
                      </Card>
                    </Timeline.Item>
                  ))}
                </Timeline>
              </Box>
            </Card>
          </Grid.Col>

          {/* Right: Detail View */}
          <Grid.Col span={{ base: 12, md: 8 }} style={{ height: '100%', overflowY: 'auto', minHeight: 0 }}>
            {steps[activeStep] && (
              <Stack gap="md">
                {/* Plan & Action Card */}
                <Card radius="lg" p="md" withBorder shadow="sm" className="timeline-card" style={{ background: 'white' }}>
                  <Stack gap="sm">
                    <Group align="center" wrap="nowrap">
                      <ThemeIcon size={32} radius="md" variant="light" color="indigo">
                        <IconBolt size={20} />
                      </ThemeIcon>
                      <Stack gap={0} style={{ flex: 1 }}>
                        <Text size="10px" fw={800} c="indigo" tt="uppercase" style={{ letterSpacing: '1px' }}>Target Goal</Text>
                        <Text size="sm" fw={700} lineClamp={2}>{steps[activeStep].plan}</Text>
                      </Stack>
                    </Group>

                    <Group align="center" wrap="nowrap">
                      <ThemeIcon size={32} radius="md" variant="light" color="orange">
                        <IconClick size={20} />
                      </ThemeIcon>
                      <Stack gap={0} style={{ flex: 1 }}>
                        <Text size="10px" fw={800} c="orange" tt="uppercase" style={{ letterSpacing: '1px' }}>Action</Text>
                        <Code p="xs" style={{ 
                        fontSize: '11px',
                        wordBreak: 'break-all', 
                        background: '#f8f9fa', 
                        color: '#e67e22', 
                        border: '1px solid #e2e8f0',
                        fontFamily: 'JetBrains Mono, monospace',
                        display: 'block',
                        borderRadius: '4px'
                      }}>
                          {steps[activeStep].action}
                        </Code>
                      </Stack>
                    </Group>
                  </Stack>
                </Card>

                {/* Image Comparison */}
                <Box>
                  <Grid gutter="xs">
                    <Grid.Col span={6}>
                      <Stack gap={4}>
                        <Badge variant="outline" color="gray" fullWidth radius="xs" size="xs">BEFORE</Badge>
                        <ImageBox src={steps[activeStep].lastImg} onClick={() => setModalImage(steps[activeStep].lastImg)} height={350} />
                      </Stack>
                    </Grid.Col>
                    <Grid.Col span={6}>
                      <Stack gap={4}>
                        <Badge variant="light" color="indigo" fullWidth radius="xs" size="xs">AFTER</Badge>
                        <ImageBox src={steps[activeStep].nextImg} onClick={() => setModalImage(steps[activeStep].nextImg)} height={350} />
                      </Stack>
                    </Grid.Col>
                  </Grid>
                </Box>
              </Stack>
            )}
          </Grid.Col>
        </Grid>
      </Box>

      <Modal opened={!!modalImage} onClose={() => setModalImage(null)} size="auto" centered withCloseButton overlayProps={{ blur: 5, backgroundOpacity: 0.3 }}>
        {modalImage && <Image src={modalImage} radius="md" style={{ maxHeight: '85vh', width: 'auto' }} />}
      </Modal>
    </>
  )
}

function ImageBox({ src, onClick, height = 400 }: { src: string | null; onClick?: () => void; height?: number }) {
  if (!src) {
    return (
      <Card h={height} display="flex" style={{ alignItems: 'center', justifyContent: 'center' }} withBorder radius="md">
        <Stack align="center" gap="xs" c="dimmed">
          <IconPhoto size={24} />
          <Text size="10px">No Image</Text>
        </Stack>
      </Card>
    )
  }
  return (
    <Card
      p={0}
      radius="md"
      withBorder
      style={{ cursor: 'zoom-in', overflow: 'hidden', borderColor: 'var(--kane-border)' }}
      onClick={onClick}
    >
      <Image src={src} h={height} fit="contain" />
    </Card>
  )
}
