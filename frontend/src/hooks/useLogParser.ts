import { useMemo } from 'react'

export interface TimelineItem {
  id: string
  type: 'thought' | 'action' | 'user'
  content: string
  agent?: 'Planner' | 'Operator' | 'System'
}

export function useLogParser(logText: string, initialUserGoal?: string) {
  return useMemo(() => {
    const items: TimelineItem[] = []
    
    // Add initial user goal if present
    if (initialUserGoal) {
      items.push({
        id: 'init-goal',
        type: 'user',
        content: initialUserGoal,
      })
    }

    const lines = logText.split('\n')
    
    lines.forEach((line, index) => {
      // System Status
      if (line.includes('Main process starting...') || line.includes('Initializing Environment') || line.includes('Starting execution for App')) {
         items.push({
             id: `sys-${index}`,
             type: 'action',
             content: line.trim(),
             agent: 'System'
         })
      }

      // Errors
      if (line.includes('Get screenshot failed') || line.includes('CRITICAL ERROR') || line.includes('Error:')) {
         items.push({
             id: `err-${index}`,
             type: 'action',
             content: `⚠️ ${line.trim()}`,
             agent: 'System'
         })
      }

      // 1. Match Planner's Plan (First Step only)
      // Format: "Plan: 1. Click x... 2. Do y..."
      if (line.startsWith('Plan:')) {
         // Regex to capture text between "1." and "2." or end of line
         const match = line.match(/1\.\s*(.*?)(?=\s*2\.|$)/)
         if (match && match[1]) {
             items.push({ 
                 id: `plan-${index}`, 
                 type: 'action', 
                 content: match[1].trim(), 
                 agent: 'Planner' 
             })
         }
      }
    })
    
    return items
  }, [logText, initialUserGoal])
}
