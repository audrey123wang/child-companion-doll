'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { getDailyReport, getInputs, getProfile, getToday, type ChildProfile, type DailyReport, type ParentInput, type ParentToday } from '@/lib/api'
import {
  ANIMALS,
  DEFAULT_SCHEDULE,
  NOTICES,
  TODAY_EVENTS,
  type AnimalId,
  type Notice,
  type ReportEvent,
  type TimeSlot,
} from '@/lib/mock-data'

export type Mode = 'kid' | 'parent'
export type KidScreen =
  | { name: 'home' }
  | { name: 'pick' }
  | { name: 'stories' }
  | { name: 'player'; storyId: string }
  | { name: 'chat'; storyId?: string }
export type ParentTab = 'overview' | 'daily' | 'weekly' | 'notices' | 'schedule' | 'profile' | 'device'

type Store = {
  mode: Mode
  setMode: (m: Mode) => void
  animalId: AnimalId
  setAnimalId: (id: AnimalId) => void
  animal: (typeof ANIMALS)[number]
  kidScreen: KidScreen
  goKid: (s: KidScreen) => void
  parentTab: ParentTab
  setParentTab: (t: ParentTab) => void
  notices: Notice[]
  setNotices: (fn: (n: Notice[]) => Notice[]) => void
  events: ReportEvent[]
  setEvents: (fn: (e: ReportEvent[]) => ReportEvent[]) => void
  schedule: Record<string, TimeSlot[]>
  setSchedule: (fn: (s: Record<string, TimeSlot[]>) => Record<string, TimeSlot[]>) => void
  micPaused: boolean
  setMicPaused: (v: boolean) => void
  pushedStories: string[]
  pushStory: (id: string) => void
  childId: string
  profile: ChildProfile | null
  today: ParentToday | null
  inputs: ParentInput[]
  report: DailyReport | null
  dataError: string | null
  dataLoading: boolean
  refreshData: () => Promise<void>
}

const StoreContext = createContext<Store | null>(null)

export function AppStoreProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>('kid')
  const [animalId, setAnimalId] = useState<AnimalId>('rabbit')
  const [kidScreen, goKid] = useState<KidScreen>({ name: 'home' })
  const [parentTab, setParentTab] = useState<ParentTab>('overview')
  const [notices, setNoticesState] = useState(NOTICES)
  const [events, setEventsState] = useState(TODAY_EVENTS)
  const [schedule, setScheduleState] = useState(DEFAULT_SCHEDULE)
  const [micPaused, setMicPaused] = useState(false)
  const [pushedStories, setPushed] = useState<string[]>([])
  const [childId, setChildId] = useState('demo-child')
  const [profile, setProfile] = useState<ChildProfile | null>(null)
  const [today, setToday] = useState<ParentToday | null>(null)
  const [inputs, setInputs] = useState<ParentInput[]>([])
  const [report, setReport] = useState<DailyReport | null>(null)
  const [dataError, setDataError] = useState<string | null>(null)
  const [dataLoading, setDataLoading] = useState(true)
  const refreshInFlight = useRef(false)

  const refreshData = useCallback(async () => {
    if (refreshInFlight.current) return
    refreshInFlight.current = true
    try {
      const currentProfile = await getProfile()
      setProfile(currentProfile)
      if (!currentProfile) {
        setToday(null); setInputs([]); setReport(null); setDataError(null)
        return
      }
      setChildId(currentProfile.child_id)
      const currentToday = await getToday(currentProfile.child_id)
      const [currentInputs, currentReport] = await Promise.all([
        getInputs(currentProfile.child_id, currentToday.date),
        getDailyReport(currentProfile.child_id, currentToday.date),
      ])
      setToday(currentToday); setInputs(currentInputs); setReport(currentReport); setDataError(null)
    } catch (error) {
      setDataError(error instanceof Error ? error.message : '无法加载本地后端')
    } finally {
      setDataLoading(false)
      refreshInFlight.current = false
    }
  }, [])

  useEffect(() => {
    void refreshData()
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') void refreshData()
    }
    const timer = setInterval(refreshWhenVisible, 2000)
    document.addEventListener('visibilitychange', refreshWhenVisible)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', refreshWhenVisible)
    }
  }, [refreshData])

  const value = useMemo<Store>(
    () => ({
      mode,
      setMode,
      animalId,
      setAnimalId,
      animal: ANIMALS.find((a) => a.id === animalId) ?? ANIMALS[0],
      kidScreen,
      goKid,
      parentTab,
      setParentTab,
      notices,
      setNotices: (fn) => setNoticesState(fn),
      events,
      setEvents: (fn) => setEventsState(fn),
      schedule,
      setSchedule: (fn) => setScheduleState(fn),
      micPaused,
      setMicPaused,
      pushedStories,
      pushStory: (id) => setPushed((p) => (p.includes(id) ? p : [id, ...p])),
      childId, profile, today, inputs, report, dataError, dataLoading, refreshData,
    }),
    [mode, animalId, kidScreen, parentTab, notices, events, schedule, micPaused, pushedStories,
      childId, profile, today, inputs, report, dataError, dataLoading, refreshData],
  )

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>
}

export function useAppStore() {
  const ctx = useContext(StoreContext)
  if (!ctx) throw new Error('useAppStore must be used within AppStoreProvider')
  return ctx
}
