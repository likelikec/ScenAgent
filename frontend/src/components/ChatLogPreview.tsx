import { Badge, Code, Group, ScrollArea, Stack, Text } from '@mantine/core'
import { useI18n } from '../useI18n'

type ChatEvent = {
  role?: string
  content?: unknown
  [k: string]: unknown
}

export function ChatLogPreview(props: { jsonl: string; maxHeight?: number }) {
  const { t } = useI18n()
  const events = parseJsonl(props.jsonl)
  return (
    <ScrollArea h={props.maxHeight ?? 520} type="auto">
      <Stack gap="sm" p="xs">
        {events.length === 0 ? (
          <Text c="dimmed" size="sm">
            {t('chat.empty')}
          </Text>
        ) : null}
        {events.map((ev, idx) => (
          <Stack key={idx} gap={4}>
            <Group gap="xs">
              <Badge variant="light">{String(ev.role || 'event')}</Badge>
              <Text size="xs" c="dimmed">
                #{idx + 1}
              </Text>
            </Group>
            <Code block>{toPrettyText(ev.content ?? ev)}</Code>
          </Stack>
        ))}
      </Stack>
    </ScrollArea>
  )
}

function parseJsonl(text: string): ChatEvent[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
  const out: ChatEvent[] = []
  for (const line of lines) {
    try {
      const obj = JSON.parse(line) as ChatEvent
      out.push(obj)
    } catch {
      out.push({ role: 'raw', content: line })
    }
  }
  return out
}

function toPrettyText(v: unknown): string {
  try {
    if (typeof v === 'string') return v
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}
