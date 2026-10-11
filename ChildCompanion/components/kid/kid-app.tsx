'use client'

import { useState } from 'react'
import { ArrowLeft, Lock, MicOff, BatteryLow } from 'lucide-react'
import { useAppStore } from '@/components/app-store'
import { ParentGate } from '@/components/kid/parent-gate'
import { KidHome } from '@/components/kid/kid-home'
import { AnimalPicker } from '@/components/kid/animal-picker'
import { StoryList } from '@/components/kid/story-list'
import { StoryPlayer } from '@/components/kid/story-player'
import { KidChat } from '@/components/kid/kid-chat'
import { DEVICE } from '@/lib/mock-data'

export function KidApp() {
  const { kidScreen, goKid, animal, micPaused } = useAppStore()
  const [gateOpen, setGateOpen] = useState(false)
  const isHome = kidScreen.name === 'home'

  return (
    <div
      className="relative flex h-full flex-col"
      style={{
        background: isHome
          ? 'radial-gradient(circle at 15% 15%, rgba(255,210,220,0.7), transparent 40%), radial-gradient(circle at 85% 85%, rgba(255,231,150,0.55), transparent 42%), #fffaf0'
          : `radial-gradient(1200px 600px at 20% 10%, ${animal.soft}, transparent 60%), radial-gradient(900px 500px at 90% 100%, #ffe9b8, transparent 60%), var(--background)`,
      }}
    >
      <header className="relative z-10 flex items-center justify-between gap-3 px-6 pt-5">
        {isHome ? (
          <div className="flex items-center gap-2">
            <span className="font-display text-2xl" style={{ color: animal.color }}>
              嘟嘟
            </span>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => goKid({ name: 'home' })}
            className="flex h-12 items-center gap-2 rounded-full bg-card px-5 font-display text-lg shadow-sm transition active:scale-95"
          >
            <ArrowLeft className="size-5" />
            回家
          </button>
        )}

        <div className="flex items-center gap-2">
          {micPaused && (
            <span className="flex items-center gap-1 rounded-full bg-card px-3 py-1.5 text-sm text-muted-foreground shadow-sm">
              <MicOff className="size-4" /> 娃娃休息中
            </span>
          )}
          {DEVICE.online && DEVICE.battery < 20 && (
            <span className="flex items-center gap-1 rounded-full bg-card px-3 py-1.5 text-sm text-muted-foreground shadow-sm">
              <BatteryLow className="size-4 text-destructive" /> 娃娃电量 {DEVICE.battery}%
            </span>
          )}
          <button
            type="button"
            onClick={() => setGateOpen(true)}
            className="flex h-10 items-center gap-1.5 rounded-full border border-border bg-card/70 px-4 text-sm text-muted-foreground transition hover:text-foreground"
          >
            <Lock className="size-4" />
            家长端
          </button>
        </div>
      </header>

      <main className="min-h-0 flex-1">
        {kidScreen.name === 'home' && <KidHome />}
        {kidScreen.name === 'pick' && <AnimalPicker />}
        {kidScreen.name === 'stories' && <StoryList />}
        {kidScreen.name === 'player' && <StoryPlayer key={kidScreen.storyId} storyId={kidScreen.storyId} />}
        {kidScreen.name === 'chat' && <KidChat key={kidScreen.storyId ?? 'free'} storyId={kidScreen.storyId} />}
      </main>

      <ParentGate open={gateOpen} onOpenChange={setGateOpen} />
    </div>
  )
}
