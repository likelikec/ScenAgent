import { useContext } from 'react'
import { I18nContext } from './i18nCore'

export function useI18n() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used within LanguageProvider')
  return ctx
}

