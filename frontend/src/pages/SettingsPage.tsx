import { useState } from 'react'
import { Alert, Button, Card, Container, Group, Stack, Text, TextInput } from '@mantine/core'
import { IconCheck, IconKey, IconLink } from '@tabler/icons-react'
import { setBackendConfig } from '../api/mobileV4'
import { ApiError, getApiBaseUrl, setApiBaseUrl } from '../api/client'
import { useI18n } from '../useI18n'

export function SettingsPage() {
  const { t } = useI18n()
  const [apiBaseUrl, setApiBaseUrlInput] = useState(getApiBaseUrl())
  const [savingKey, setSavingKeyState] = useState(false)

  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')

  const [summaryApiKey, setSummaryApiKey] = useState('')
  const [summaryBaseUrl, setSummaryBaseUrl] = useState('')
  const [summaryModel, setSummaryModel] = useState('')

  const [saved, setSaved] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  function validateApiBaseUrlOrThrow(value: string) {
    const v = value.trim()
    if (!v) throw new Error('API_BASE_URL 不能为空（例如 http://127.0.0.1:8000）')
    if (!/^https?:\/\/.+/i.test(v)) throw new Error('API_BASE_URL 格式错误（例如 http://127.0.0.1:8000）')
  }

  function onSaveBaseUrl() {
    setError(null)
    setSaved(null)
    try {
      validateApiBaseUrlOrThrow(apiBaseUrl)
      setApiBaseUrl(apiBaseUrl)
      setSaved(t('settings.apiBaseUrl.saved'))
    } catch (e: unknown) {
      setError(toErrorText(e))
    }
  }

  async function onSaveLLMConfig() {
    setError(null)
    setSaved(null)
    setSavingKeyState(true)
    try {
      const payload: Record<string, string> = {}
      if (apiKey.trim()) payload.api_key = apiKey.trim()
      if (baseUrl.trim()) payload.base_url = baseUrl.trim()
      if (model.trim()) payload.model = model.trim()
      if (summaryApiKey.trim()) payload.summary_api_key = summaryApiKey.trim()
      if (summaryBaseUrl.trim()) payload.summary_base_url = summaryBaseUrl.trim()
      if (summaryModel.trim()) payload.summary_model = summaryModel.trim()

      await setBackendConfig(payload)
      setSaved(t('settings.llm.saved'))
      setApiKey('')
    } catch (e: unknown) {
      setError(toErrorText(e))
    } finally {
      setSavingKeyState(false)
    }
  }

  return (
    <Container size="lg" p="xl">
      <Stack gap="lg">
      <Stack gap={2}>
        <Text fw={700} size="lg">
          {t('settings.title')}
        </Text>
        <Text size="sm" c="dimmed">
          {t('settings.subtitle')}
        </Text>
      </Stack>

      {error ? (
        <Alert color="red" title={t('settings.saveFailed')}>
          {error}
        </Alert>
      ) : null}
      {saved ? (
        <Alert color="green" title={t('settings.done')} icon={<IconCheck size={16} />}>
          {saved}
        </Alert>
      ) : null}

      <Card withBorder radius="md" p="lg">
        <Stack gap="sm">
          <Group gap="xs">
            <IconLink size={18} />
            <Text fw={600}>{t('settings.apiBaseUrl.title')}</Text>
          </Group>
          <TextInput
            value={apiBaseUrl}
            onChange={(e) => setApiBaseUrlInput(e.currentTarget.value)}
            placeholder="http://127.0.0.1:8000"
          />
          <Group justify="flex-end">
            <Button variant="light" onClick={onSaveBaseUrl}>
              {t('settings.apiBaseUrl.save')}
            </Button>
          </Group>
        </Stack>
      </Card>

      <Card withBorder radius="md" p="lg">
        <Stack gap="md">
          <Group gap="xs">
            <IconKey size={18} />
            <Text fw={600}>{t('settings.llm.title')}</Text>
          </Group>
          <Group grow>
            <TextInput
              label={t('settings.llm.apiKey')}
              value={apiKey}
              onChange={(e) => setApiKey(e.currentTarget.value)}
              placeholder="sk-..."
              type="password"
            />
            <TextInput
              label={t('settings.llm.baseUrl')}
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.currentTarget.value)}
              placeholder="http://127.0.0.1:8000"
            />
            <TextInput
              label={t('settings.llm.model')}
              value={model}
              onChange={(e) => setModel(e.currentTarget.value)}
              placeholder="model-name"
            />
          </Group>

          <Text fw={600}>{t('settings.summaryLlm.title')}</Text>
          <Group grow>
            <TextInput
              label={t('settings.llm.summaryApiKey')}
              value={summaryApiKey}
              onChange={(e) => setSummaryApiKey(e.currentTarget.value)}
              placeholder="sk-..."
              type="password"
            />
            <TextInput
              label={t('settings.llm.summaryBaseUrl')}
              value={summaryBaseUrl}
              onChange={(e) => setSummaryBaseUrl(e.currentTarget.value)}
              placeholder="(optional)"
            />
            <TextInput
              label={t('settings.llm.summaryModel')}
              value={summaryModel}
              onChange={(e) => setSummaryModel(e.currentTarget.value)}
              placeholder="(optional)"
            />
          </Group>

          <Group justify="flex-end">
            <Button loading={savingKey} onClick={onSaveLLMConfig}>
              {t('settings.llm.save')}
            </Button>
          </Group>
        </Stack>
      </Card>
    </Stack>
    </Container>
  )
}

function toErrorText(err: unknown): string {
  if (err instanceof ApiError) return err.detail || err.message
  if (err instanceof Error) return err.message
  return String(err)
}
