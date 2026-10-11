'use client'

import { useAppStore } from '@/components/app-store'
import { KidApp } from '@/components/kid/kid-app'
import { ParentApp } from '@/components/parent/parent-app'

export function AppShell() {
  const { mode } = useAppStore()
  return (
    <div className="h-dvh w-full overflow-hidden bg-background">
      {mode === 'kid' ? <KidApp /> : <ParentApp />}
    </div>
  )
}
