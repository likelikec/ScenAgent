import { AppShell, Group, NavLink, ScrollArea, Stack, Text, ThemeIcon, Tooltip, UnstyledButton, Badge, Loader, ActionIcon, Burger } from '@mantine/core'
import { IconLayoutDashboard, IconSettings, IconHistory, IconChevronLeft, IconChevronRight, IconCheck, IconAlertCircle, IconTrash, IconTimelineEvent, IconLanguage } from '@tabler/icons-react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { readJobHistory, removeJobHistory, type JobHistoryItem } from './state/jobHistory'
import { getJobStatus } from './api/mobileV4'
import { RunPage } from './pages/RunPage'
import { JobPage } from './pages/JobPage'
import { JobReportPage } from './pages/JobReportPage'
import { SettingsPage } from './pages/SettingsPage'
import { useI18n } from './useI18n'
import { ErrorBoundary } from './components/ErrorBoundary'

function App() {
  const location = useLocation()
  const { t, language, setLanguage } = useI18n()
  const [opened, setOpened] = useState(true)
  const [jobsVersion, setJobsVersion] = useState(0)

  const [jobStatuses, setJobStatuses] = useState<Record<string, string>>({})
  const jobs = readJobHistory()

  useEffect(() => {
    async function fetchStatuses() {
      const newStatuses: Record<string, string> = {}
      const recentJobs = jobs.slice(0, 20)
      for (const job of recentJobs) {
        try {
          const status = await getJobStatus(job.job_id)
          newStatuses[job.job_id] = status.status
        } catch {
          newStatuses[job.job_id] = 'unknown'
        }
      }
      setJobStatuses(newStatuses)
    }

    fetchStatuses()
    const timer = setInterval(fetchStatuses, 10000)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.length, jobsVersion])

  const runningJobs = jobs.filter(j => {
    const s = jobStatuses[j.job_id]
    return s === 'running' || s === 'queued'
  })
  
  const historyJobs = jobs.filter(j => {
    const s = jobStatuses[j.job_id]
    return s && s !== 'running' && s !== 'queued'
  })

  function onDeleteJob(id: string) {
    removeJobHistory(id)
    setJobsVersion(v => v + 1)
  }

  return (
    <AppShell
      header={{ height: 48 }}
      navbar={{ width: opened ? 260 : 60, breakpoint: 'sm' }}
      padding="0"
    >
      <AppShell.Header style={{ borderBottom: '1px solid var(--kane-border)' }}>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="xs">
            <Burger opened={opened} onClick={() => setOpened(!opened)} hiddenFrom="sm" size="sm" />
            <ThemeIcon radius="md" size="md" variant="gradient" gradient={{ from: 'indigo', to: 'violet' }}>
              <IconTimelineEvent size={16} />
            </ThemeIcon>
            <Text fw={800} size="sm" style={{ letterSpacing: '-0.5px' }}>ScenAgent</Text>
          </Group>

          {/* Global Language Toggle Button */}
          <Tooltip label={language === 'zh' ? '切换到英文' : 'Switch to Chinese'}>
            <ActionIcon
              variant="light"
              color="blue"
              size="lg"
              radius="md"
              onClick={() => setLanguage(language === 'zh' ? 'en' : 'zh')}
            >
              <IconLanguage size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs" style={{ borderRight: '1px solid var(--kane-border)' }}>
        <Stack gap="xs" h="100%">
          <Stack gap={4}>
             <NavbarLink 
                icon={IconLayoutDashboard} 
                label={t('nav.run')} 
                active={location.pathname.startsWith('/run')} 
                to="/run"
                collapsed={!opened}
             />
             <NavbarLink 
                icon={IconSettings} 
                label={t('nav.settings')} 
                active={location.pathname.startsWith('/settings')} 
                to="/settings"
                collapsed={!opened}
             />
          </Stack>

          {opened && (
            <>
              <ScrollArea flex={1} type="auto" mx="-xs" px="xs">
                <Stack gap="md" py="md">
                  {/* Running Section */}
                  <Stack gap={4}>
                    <Group justify="space-between" px="xs" mb={4}>
                      <Text size="xs" c="blue" fw={700} tt="uppercase" style={{ letterSpacing: '0.5px' }}>
                        Running
                      </Text>
                      {runningJobs.length > 0 && <Badge size="xs" variant="light" color="blue">{runningJobs.length}</Badge>}
                    </Group>
                    {runningJobs.length === 0 ? (
                       <Text size="xs" c="dimmed" px="xs" fs="italic">No active tasks</Text>
                    ) : (
                      runningJobs.map((j) => (
                        <JobNavLink 
                          key={j.job_id} 
                          job={j} 
                          status={jobStatuses[j.job_id]} 
                          active={location.pathname.includes(j.job_id)} 
                          onDelete={() => onDeleteJob(j.job_id)}
                        />
                      ))
                    )}
                  </Stack>

                  {/* History Section */}
                  <Stack gap={4}>
                    <Text size="xs" c="dimmed" px="xs" fw={700} tt="uppercase" mb={4} style={{ letterSpacing: '0.5px' }}>
                      {t('nav.recent')}
                    </Text>
                    {historyJobs.length === 0 ? (
                      <Text size="xs" c="dimmed" px="xs">
                        {t('nav.recent.empty')}
                      </Text>
                    ) : (
                      historyJobs.map((j) => (
                        <JobNavLink 
                          key={j.job_id} 
                          job={j} 
                          status={jobStatuses[j.job_id]} 
                          active={location.pathname.includes(j.job_id)} 
                          onDelete={() => onDeleteJob(j.job_id)}
                        />
                      ))
                    )}
                  </Stack>
                </Stack>
              </ScrollArea>
            </>
          )}

          {!opened && (
             <Stack align="center" mt="auto">
                 <Tooltip label={t('nav.recent')} position="right">
                    <ThemeIcon variant="light" color="gray" size="lg" radius="md">
                        <IconHistory size={20} />
                    </ThemeIcon>
                 </Tooltip>
             </Stack>
          )}
          
          <UnstyledButton 
            onClick={() => setOpened(!opened)} 
            style={{ 
                display: 'flex', 
                justifyContent: 'center', 
                alignItems: 'center', 
                padding: 8, 
                borderRadius: 8,
                color: 'var(--mantine-color-dimmed)',
            }}
            visibleFrom="sm"
          >
             {opened ? <IconChevronLeft size={18} /> : <IconChevronRight size={18} />}
          </UnstyledButton>
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main bg="gray.0">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Navigate to="/run" replace />} />
            <Route path="/run" element={<RunPage />} />
            <Route path="/jobs/:jobId" element={<JobPage />} />
            <Route path="/jobs/:jobId/report" element={<JobReportPage />} />
            <Route path="/jobs/:jobId/artifacts" element={<Navigate to={`/jobs/${location.pathname.split('/')[2]}`} replace />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/run" replace />} />
          </Routes>
        </ErrorBoundary>
      </AppShell.Main>
    </AppShell>
  )
}

function NavbarLink({ icon: Icon, label, active, to, collapsed }: { icon: React.ElementType, label: string, active: boolean, to: string, collapsed: boolean }) {
  return (
    <Tooltip label={label} position="right" disabled={!collapsed} transitionProps={{ duration: 0 }}>
      <NavLink
        component={Link}
        to={to}
        label={!collapsed ? <Text fw={500} size="sm">{label}</Text> : null}
        leftSection={<Icon size={20} stroke={1.5} />}
        active={active}
        variant="light"
        color="blue"
        style={{ 
            borderRadius: 8,
            justifyContent: collapsed ? 'center' : 'flex-start',
            height: 44
        }}
      />
    </Tooltip>
  )
}

function JobNavLink({ job, status, active, onDelete }: { job: JobHistoryItem; status?: string; active: boolean; onDelete: () => void }) {
  const isRunning = status === 'running' || status === 'queued'
  
  return (
    <NavLink
      component={Link}
      to={`/jobs/${job.job_id}`}
      label={<Text size="sm" fw={isRunning ? 700 : 500} lineClamp={1}>{shortId(job.job_id)}</Text>}
      description={<Text size="xs" c="dimmed">{job.created_at || ''}</Text>}
      active={active}
      variant="light"
      color={isRunning ? 'blue' : 'gray'}
      style={{ borderRadius: 8 }}
      rightSection={
        <ActionIcon 
          variant="subtle" 
          color="gray" 
          size="sm" 
          onClick={(e) => {
            e.preventDefault()
            onDelete()
          }}
          className="delete-job-btn"
        >
          <IconTrash size={14} />
        </ActionIcon>
      }
      leftSection={
        isRunning ? (
          <Loader size={14} color="blue" />
        ) : status === 'success' ? (
          <IconCheck size={14} color="var(--mantine-color-green-6)" />
        ) : status === 'failed' ? (
          <IconAlertCircle size={14} color="var(--mantine-color-red-6)" />
        ) : (
          <IconHistory size={14} />
        )
      }
    />
  )
}

function shortId(id: string): string {
  if (id.length <= 12) return id
  return `${id.slice(0, 8)}…${id.slice(-4)}`
}

export default App
