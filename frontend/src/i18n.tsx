import { useMemo, useState } from 'react'
import { I18nContext, STORAGE_KEY, dictEn, dictZh, format, normalizeLanguage } from './i18nCore'

export function LanguageProvider(props: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState(() => normalizeLanguage(localStorage.getItem(STORAGE_KEY)))

  function setLanguage(lang: 'zh' | 'en') {
    setLanguageState(lang)
    localStorage.setItem(STORAGE_KEY, lang)
  }

  const value = useMemo(() => {
    const dict = language === 'en' ? dictEn : dictZh
    return {
      language,
      setLanguage,
      t: (key: string, vars?: Record<string, string | number>) => format(dict[key] || key, vars),
    }
  }, [language])

  return <I18nContext.Provider value={value}>{props.children}</I18nContext.Provider>
}
