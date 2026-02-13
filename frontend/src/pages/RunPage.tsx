import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Button,
  Container,
  FileInput,
  Group,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
  Box,
  Tooltip,
  ActionIcon,
  Divider,
  Transition,
  Modal,
} from '@mantine/core'
import {
  IconArrowRight,
  IconCheck,
  IconUpload,
  IconPackage,
  IconAdjustments,
  IconSparkles,
  IconPaperclip,
  IconX,
  IconCircleCheck,
} from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { runJob, uploadScenario, uploadFile } from '../api/mobileV4'
import type { RunRequest, ScenarioRef, SimpleTaskData } from '../api/types'
import { addJobHistory } from '../state/jobHistory'
import { addScenarioHistory, clearScenarioHistory, readScenarioHistory } from '../state/scenarioHistory'
import { getApiBaseUrl } from '../api/client'
import { useI18n } from '../useI18n'

export function RunPage() {
  const navigate = useNavigate()
  const { language, t } = useI18n()

  // Main mode: 'quick' or 'advanced'
  const [mainMode, setMainMode] = useState<'quick' | 'advanced'>('quick')

  // Modals
  const [showAppConfigModal, setShowAppConfigModal] = useState(false)
  const [shouldAutoSubmit, setShouldAutoSubmit] = useState(false)

  // Quick Mode States
  const [taskDescription, setTaskDescription] = useState('')
  const [packageName, setPackageName] = useState('')
  const [launchActivity, setLaunchActivity] = useState('')
  const [appName, setAppName] = useState('')
  const [apkFile, setApkFile] = useState<File | null>(null)
  const [apkToken, setApkToken] = useState<string>('')
  const [uploadingApk, setUploadingApk] = useState(false)

  // Advanced Mode States
  const [scenarioFile, setScenarioFile] = useState<File | null>(null)
  const [scenarioToken, setScenarioToken] = useState<string>('')
  const [uploading, setUploading] = useState(false)
  const [scenarioHistoryVersion, setScenarioHistoryVersion] = useState(0)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const scenarioHistory = useMemo(() => readScenarioHistory(), [scenarioHistoryVersion])

  const [mode, setMode] = useState<'single' | 'range' | 'batch'>('single')
  const [appId, setAppId] = useState('A1')
  const [scenarioId, setScenarioId] = useState('S1')
  const [scenarioStartId, setScenarioStartId] = useState('')
  const [scenarioEndId, setScenarioEndId] = useState('')

  // Common States
  const [submitting, setSubmitting] = useState(false)

  const canUpload = !!scenarioFile && !uploading

  // Validation
  const canSubmit = useMemo(() => {
    if (submitting) return false

    if (mainMode === 'quick') {
      return taskDescription.trim() !== ''
    } else {
      if (!scenarioToken) return false
      if (!appId) return false
      if (mode === 'single') return !!scenarioId
      if (mode === 'range') return !!scenarioStartId && !!scenarioEndId
      return true
    }
  }, [mainMode, taskDescription, scenarioToken, submitting, appId, mode, scenarioId, scenarioStartId, scenarioEndId])

  const scenarioRef: ScenarioRef = useMemo(
    () => ({ type: 'uploaded', value: scenarioToken }),
    [scenarioToken],
  )

  const onSubmit = useCallback(async () => {
    if (mainMode === 'quick' && !packageName.trim()) {
      setShowAppConfigModal(true)
      return
    }

    setSubmitting(true)
    try {
      let req: RunRequest

      if (mainMode === 'quick') {
        const simpleTask: SimpleTaskData = {
          task_description: taskDescription,
          package_name: packageName,
          launch_activity: launchActivity || null,
          app_name: appName || null,
        }

        req = {
          mode: 'single',
          simple_task: simpleTask,
          apk_ref: apkToken ? { type: 'uploaded', value: apkToken } : null,
          device_profile: 'default_android',
          model_profile: 'default_qwen_vl',
          lang: language,
        }
      } else {
        req = {
          mode,
          scenario_ref: scenarioRef,
          apk_ref: apkToken ? { type: 'uploaded', value: apkToken } : null,
          app_id: appId,
          scenario_id: mode === 'single' ? scenarioId : undefined,
          scenario_start_id: mode === 'range' ? scenarioStartId : undefined,
          scenario_end_id: mode === 'range' ? scenarioEndId : undefined,
          device_profile: 'default_android',
          model_profile: 'default_qwen_vl',
          lang: language,
        }
      }

      const res = await runJob(req)
      addJobHistory({ job_id: res.job_id, created_at: res.created_at })
      navigate(`/jobs/${res.job_id}`, { state: { userPrompt: taskDescription } })
    } catch (e: unknown) {
      console.error('Submit failed:', e)
    } finally {
      setSubmitting(false)
    }
  }, [mainMode, packageName, taskDescription, launchActivity, appName, language, mode, scenarioRef, appId, scenarioId, scenarioStartId, scenarioEndId, navigate])

  useEffect(() => {
    if (shouldAutoSubmit && !showAppConfigModal) {
      setShouldAutoSubmit(false)
      if (taskDescription.trim() && packageName.trim()) {
        onSubmit()
      }
    }
  }, [shouldAutoSubmit, showAppConfigModal, taskDescription, packageName, onSubmit])

  async function onUpload() {
    if (!scenarioFile) return
    setUploading(true)
    try {
      const res = await uploadScenario(scenarioFile)
      setScenarioToken(res.scenario_token)
      addScenarioHistory({
        scenario_token: res.scenario_token,
        filename: res.filename,
        uploaded_at: new Date().toISOString(),
        api_base_url: getApiBaseUrl(),
      })
      setScenarioHistoryVersion((v) => v + 1)
    } catch (e: unknown) {
      console.error('Upload failed:', e)
    } finally {
      setUploading(false)
    }
  }

  async function onUploadApk(file: File | null) {
    if (!file) {
      setApkFile(null)
      setApkToken('')
      return
    }
    setApkFile(file)
    setUploadingApk(true)
    try {
      const res = await uploadFile(file)
      if (res.type === 'apk') {
        setApkToken(res.token)
      }
    } catch (e: unknown) {
      console.error('APK Upload failed:', e)
      setApkFile(null)
      setApkToken('')
    } finally {
      setUploadingApk(false)
    }
  }

  return (
    <Container fluid h="calc(100vh - 48px)" p={0} style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <Stack gap={0} align="center" justify="center" style={{ flex: 1 }}>
        <Stack align="center" gap="lg" w="100%" maw={900} px="md">
          <Title order={1} style={{ fontSize: '2.2rem', fontWeight: 900, textAlign: 'center', letterSpacing: '-1px', color: 'var(--kane-text)' }}>
            {language === 'zh' ? '今天你想测试什么？' : 'What do you want to test today?'}
          </Title>

          {/* Quick Mode: Input + Control Bar */}
          <Box style={{ position: 'relative', width: '100%' }}>
            <Transition
              mounted={mainMode === 'quick'}
              transition="fade"
              duration={300}
              timingFunction="ease"
            >
              {(styles) => (
                <Paper
                  radius="16px"
                  w="100%"
                  shadow="md"
                  style={{
                    ...styles,
                    position: mainMode === 'quick' ? 'relative' : 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    border: '1px solid var(--kane-border)',
                    background: 'white',
                    overflow: 'hidden',
                  }}
                >
                  <Stack gap={0}>
                    {/* Input Area */}
                    <Box p={8}>
                      <TextInput
                        variant="unstyled"
                        size="lg"
                        placeholder={language === 'zh' ? '描述测试任务，例如：打开网易云音乐并搜索歌曲...' : 'Describe test task, e.g.: Open NetEase Music and search for a song...'}
                        value={taskDescription}
                        onChange={(e) => setTaskDescription(e.currentTarget.value)}
                        onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && canSubmit && onSubmit()}
                        styles={{ input: { fontSize: '1.1rem', fontWeight: 400, padding: '8px 12px' } }}
                      />
                    </Box>

                    {/* APK Attachment Info */}
                    {apkFile && (
                      <Box px={16} pb={8}>
                        <Group gap="xs" p="4px 8px" style={{ background: 'var(--mantine-color-gray-0)', borderRadius: '8px', border: '1px solid var(--mantine-color-gray-2)', width: 'fit-content' }}>
                          <IconPackage size={14} color="var(--mantine-color-teal-6)" />
                          <Text size="xs" fw={500} c="gray.7" maw={200} truncate="end">{apkFile.name}</Text>
                          {uploadingApk ? (
                            <Text size="xs" c="dimmed">...</Text>
                          ) : (
                            <IconCircleCheck size={14} color="var(--mantine-color-teal-6)" />
                          )}
                          <ActionIcon variant="subtle" color="gray" size="xs" onClick={() => { setApkFile(null); setApkToken(''); }}>
                            <IconX size={12} />
                          </ActionIcon>
                        </Group>
                      </Box>
                    )}

                    {/* Control Bar */}
                    <Group p={8} gap={6} wrap="nowrap">
                      {/* Mode Switch */}
                      <Tooltip label={language === 'zh' ? '切换到高级模式' : 'Switch to Advanced Mode'}>
                        <ActionIcon
                          variant="light"
                          color="violet"
                          size="lg"
                          radius="md"
                          onClick={() => setMainMode('advanced')}
                        >
                          <IconAdjustments size={18} />
                        </ActionIcon>
                      </Tooltip>

                      {/* App Config */}
                      <Tooltip label={language === 'zh' ? '应用配置' : 'App Config'}>
                        <ActionIcon
                          variant={packageName ? 'light' : 'subtle'}
                          color={packageName ? 'teal' : 'gray'}
                          size="lg"
                          radius="md"
                          onClick={() => setShowAppConfigModal(true)}
                        >
                          <IconPackage size={18} />
                        </ActionIcon>
                      </Tooltip>

                      {/* APK Upload */}
                      <Tooltip label={t('run.upload.apk.label')}>
                        <Box style={{ position: 'relative' }}>
                          <FileInput
                            accept=".apk"
                            onChange={onUploadApk}
                            style={{ position: 'absolute', inset: 0, opacity: 0, zIndex: 1, cursor: 'pointer' }}
                          />
                          <ActionIcon
                            variant={apkToken ? 'light' : 'subtle'}
                            color={apkToken ? 'teal' : 'gray'}
                            size="lg"
                            radius="md"
                            loading={uploadingApk}
                          >
                            <IconPaperclip size={18} />
                          </ActionIcon>
                        </Box>
                      </Tooltip>

                      <Box style={{ flex: 1 }} />

                      {/* Start Button */}
                      <Button
                        size="md"
                        radius="lg"
                        color="indigo"
                        onClick={onSubmit}
                        loading={submitting}
                        disabled={!canSubmit}
                        px="lg"
                      >
                        <IconArrowRight size={20} stroke={2.5} />
                      </Button>
                    </Group>
                  </Stack>
                </Paper>
              )}
            </Transition>

            {/* Advanced Mode: Configuration Form */}
            <Transition
              mounted={mainMode === 'advanced'}
              transition="fade"
              duration={300}
              timingFunction="ease"
            >
              {(styles) => (
                <Paper
                  radius="16px"
                  w="100%"
                  shadow="md"
                  style={{
                    ...styles,
                    position: mainMode === 'advanced' ? 'relative' : 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    border: '1px solid var(--kane-border)',
                    background: 'white',
                  }}
                >
                <Stack gap="lg" p="lg">
                  {/* Mode Switch Button */}
                  <Group justify="space-between">
                    <Text size="lg" fw={700}>{language === 'zh' ? '高级配置' : 'Advanced Configuration'}</Text>
                    <Tooltip label={language === 'zh' ? '返回快速模式' : 'Back to Quick Mode'}>
                      <ActionIcon
                        variant="light"
                        color="indigo"
                        size="lg"
                        radius="md"
                        onClick={() => setMainMode('quick')}
                      >
                        <IconSparkles size={18} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>

                  <Divider />

                  {/* Upload Section */}
                  <Box>
                    <Text size="sm" fw={700} mb="xs">{t('run.step1')}</Text>
                    <Stack gap="sm">
                      <Select
                        label={t('run.upload.history')}
                        placeholder={t('run.upload.history.placeholder')}
                        value={scenarioToken || null}
                        onChange={(v) => {
                          const token = v || ''
                          setScenarioToken(token)
                          if (token) setScenarioFile(null)
                        }}
                        data={scenarioHistory.map((x) => ({
                          value: x.scenario_token,
                          label: `${x.filename}`,
                        }))}
                        nothingFoundMessage={t('run.upload.history.empty')}
                        searchable
                        clearable
                        size="sm"
                        radius="md"
                      />

                      <FileInput
                        label={t('run.upload.label')}
                        placeholder={t('run.upload.placeholder')}
                        leftSection={<IconUpload size={16} />}
                        value={scenarioFile}
                        onChange={setScenarioFile}
                        accept=".json,application/json"
                        size="sm"
                        radius="md"
                      />

                      <Group grow>
                        <Button
                          variant={scenarioToken ? "light" : "filled"}
                          color={scenarioToken ? "teal" : "indigo"}
                          loading={uploading}
                          disabled={!canUpload}
                          onClick={onUpload}
                          leftSection={scenarioToken ? <IconCheck size={16} /> : <IconUpload size={16} />}
                          radius="md"
                          size="sm"
                        >
                          {scenarioToken ? t('run.upload.done') : t('run.upload.button')}
                        </Button>

                        <Button
                          variant="subtle"
                          color="gray"
                          size="sm"
                          radius="md"
                          disabled={scenarioHistory.length === 0}
                          onClick={() => {
                            clearScenarioHistory()
                            setScenarioToken('')
                            setScenarioHistoryVersion((v) => v + 1)
                          }}
                        >
                          {t('run.upload.history.clear')}
                        </Button>
                      </Group>
                    </Stack>
                  </Box>

                  <Divider />

                  {/* APK Upload Section (Advanced) */}
                  <Box>
                    <Text size="sm" fw={700} mb="xs">{t('run.upload.apk.label')}</Text>
                    <Stack gap="sm">
                      <FileInput
                        placeholder={t('run.upload.apk.placeholder')}
                        leftSection={<IconPackage size={16} />}
                        value={apkFile}
                        onChange={onUploadApk}
                        accept=".apk"
                        size="sm"
                        radius="md"
                        rightSection={apkToken && <IconCircleCheck size={16} color="teal" />}
                      />
                      {apkToken && (
                        <Text size="xs" c="teal" fw={500}>
                          {t('run.upload.apk.done')}: {apkFile?.name}
                        </Text>
                      )}
                    </Stack>
                  </Box>

                  <Divider />

                  {/* Task Config Section */}
                  <Box style={{ opacity: scenarioToken ? 1 : 0.5, pointerEvents: scenarioToken ? 'auto' : 'none' }}>
                    <Text size="sm" fw={700} mb="xs">{t('run.step2')}</Text>
                    <Stack gap="sm">
                      <SegmentedControl
                        value={mode}
                        onChange={(v) => setMode(v as 'single' | 'range' | 'batch')}
                        data={[
                          { label: t('run.mode.single'), value: 'single' },
                          { label: t('run.mode.range'), value: 'range' },
                          { label: t('run.mode.batch'), value: 'batch' },
                        ]}
                        fullWidth
                        size="xs"
                        radius="md"
                        color="indigo"
                      />

                      <TextInput
                        label={t('run.appId')}
                        placeholder="e.g. A1"
                        value={appId}
                        onChange={(e) => setAppId(e.currentTarget.value)}
                        size="sm"
                        radius="md"
                      />

                      {mode === 'single' && (
                        <TextInput
                          label={t('run.scenarioId')}
                          placeholder="e.g. S1"
                          value={scenarioId}
                          onChange={(e) => setScenarioId(e.currentTarget.value)}
                          size="sm"
                          radius="md"
                        />
                      )}

                      {mode === 'range' && (
                        <Group grow>
                          <TextInput
                            label={t('run.scenarioStartId')}
                            placeholder="e.g. 1"
                            value={scenarioStartId}
                            onChange={(e) => setScenarioStartId(e.currentTarget.value)}
                            size="sm"
                            radius="md"
                          />
                          <TextInput
                            label={t('run.scenarioEndId')}
                            placeholder="e.g. 10"
                            value={scenarioEndId}
                            onChange={(e) => setScenarioEndId(e.currentTarget.value)}
                            size="sm"
                            radius="md"
                          />
                        </Group>
                      )}
                    </Stack>
                  </Box>

                  {/* Submit Button */}
                  <Button
                    size="lg"
                    radius="md"
                    color="indigo"
                    onClick={onSubmit}
                    loading={submitting}
                    disabled={!canSubmit}
                    rightSection={<IconArrowRight size={20} />}
                    fullWidth
                  >
                    {language === 'zh' ? '开始执行' : 'Start Execution'}
                  </Button>
                </Stack>
              </Paper>
            )}
          </Transition>
          </Box>

          {/* Helper Text - Outside the card */}
          {mainMode === 'quick' && !packageName && (
            <Text size="xs" c="dimmed" ta="center" mt={-12}>
              {language === 'zh' ? '💡 点击 ' : '💡 Click '}
              <IconPackage size={14} style={{ display: 'inline', verticalAlign: 'middle', marginBottom: 2 }} />
              {language === 'zh' ? ' 配置应用信息' : ' to configure app info'}
            </Text>
          )}
        </Stack>
      </Stack>

      {/* App Config Modal (Quick Mode) */}
      <Modal
        opened={showAppConfigModal}
        onClose={() => setShowAppConfigModal(false)}
        title={<Text fw={700}>{language === 'zh' ? '应用配置' : 'App Configuration'}</Text>}
        size="md"
        radius="md"
      >
        <Stack gap="md">
          <TextInput
            label={language === 'zh' ? '应用包名' : 'Package Name'}
            placeholder="e.g. com.netease.cloudmusic"
            value={packageName}
            onChange={(e) => setPackageName(e.currentTarget.value)}
            size="sm"
            radius="md"
            required
          />
          <TextInput
            label={language === 'zh' ? '应用名称（可选）' : 'App Name (Optional)'}
            placeholder={language === 'zh' ? '例如：网易云音乐' : 'e.g.: NetEase Music'}
            value={appName}
            onChange={(e) => setAppName(e.currentTarget.value)}
            size="sm"
            radius="md"
          />
          <TextInput
            label={language === 'zh' ? '启动Activity（可选）' : 'Launch Activity (Optional)'}
            placeholder="e.g. .MainActivity"
            value={launchActivity}
            onChange={(e) => setLaunchActivity(e.currentTarget.value)}
            size="sm"
            radius="md"
          />
          <Button
            fullWidth
            onClick={() => {
              setShowAppConfigModal(false)
              if (taskDescription.trim() && packageName.trim()) {
                setShouldAutoSubmit(true)
              }
            }}
            disabled={!packageName.trim()}
            radius="md"
          >
            {language === 'zh' ? '确定' : 'Confirm'}
          </Button>
        </Stack>
      </Modal>
    </Container>
  )
}
