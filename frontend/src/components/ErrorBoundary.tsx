import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { Alert, Button, Container, Stack, Text, Code, ScrollArea, Group } from '@mantine/core'
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-react'

interface Props {
  children?: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo)
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <Container size="md" py={50}>
          <Alert
            variant="light"
            color="red"
            title="页面组件崩溃"
            icon={<IconAlertTriangle size={20} />}
            radius="md"
          >
            <Stack gap="md">
              <Text size="sm">
                抱歉，应用在渲染此页面时遇到了不可恢复的错误。这可能是由于后端返回的数据格式不匹配或前端逻辑缺陷导致的。
              </Text>

              {this.state.error && (
                <ScrollArea h={120} bg="rgba(0,0,0,0.05)" p="xs" style={{ borderRadius: 4 }}>
                  <Code block color="red" bg="transparent" style={{ fontSize: '11px' }}>
                    {this.state.error.stack || this.state.error.message}
                  </Code>
                </ScrollArea>
              )}

              <Group justify="flex-end">
                <Button 
                  variant="filled" 
                  color="red" 
                  size="sm" 
                  leftSection={<IconRefresh size={16} />}
                  onClick={this.handleReset}
                >
                  刷新页面重试
                </Button>
              </Group>
            </Stack>
          </Alert>
        </Container>
      )
    }

    return this.props.children
  }
}
