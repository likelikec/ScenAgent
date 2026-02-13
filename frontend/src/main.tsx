import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MantineProvider } from '@mantine/core'
import '@mantine/core/styles.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { LanguageProvider } from './i18n'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider 
      defaultColorScheme="light"
      theme={{
        primaryColor: 'cyan',
        defaultRadius: 'md',
        fontFamily: 'Inter, system-ui, sans-serif',
        white: '#FFFFFF',
        black: '#1A1B1E',
        components: {
          Card: {
            defaultProps: {
              shadow: 'sm',
              withBorder: true,
              bg: 'white',
            },
            styles: {
              root: {
                borderColor: '#E9ECEF'
              }
            }
          },
          Paper: {
            defaultProps: {
              bg: 'white',
            }
          }
        }
      }}
    >
      <QueryClientProvider client={queryClient}>
        <LanguageProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </LanguageProvider>
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
)
