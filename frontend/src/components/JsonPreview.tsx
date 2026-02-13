import { Code, ScrollArea } from '@mantine/core'

export function JsonPreview(props: { value: unknown; maxHeight?: number }) {
  const text = safeStringify(props.value)
  return (
    <ScrollArea h={props.maxHeight ?? 420} type="auto">
      <Code block>{text}</Code>
    </ScrollArea>
  )
}

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

