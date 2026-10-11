'use client'

import Image from 'next/image'
import { Baby, Bell, CalendarDays, CalendarRange, Clock, Cpu, LayoutDashboard, UserRound } from 'lucide-react'
import { useAppStore, type ParentTab } from '@/components/app-store'
import { Overview } from '@/components/parent/overview'
import { DailyReport } from '@/components/parent/daily-report'
import { WeeklyReport } from '@/components/parent/weekly-report'
import { Notices } from '@/components/parent/notices'
import { ScheduleSettings } from '@/components/parent/schedule-settings'
import { ProfileSettings } from '@/components/parent/profile-settings'
import { DeviceSettings } from '@/components/parent/device-settings'
import { CHILD_PROFILE } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

const NAV: { id: ParentTab; label: string; icon: React.ElementType; group: string }[] = [
  { id: 'overview', label: '今日概览', icon: LayoutDashboard, group: '情绪' },
  { id: 'daily', label: '日报', icon: CalendarDays, group: '情绪' },
  { id: 'weekly', label: '周报', icon: CalendarRange, group: '情绪' },
  { id: 'notices', label: '报告推送', icon: Bell, group: '情绪' },
  { id: 'schedule', label: '收音时段', icon: Clock, group: '设置' },
  { id: 'profile', label: '孩子与偏好', icon: UserRound, group: '设置' },
  { id: 'device', label: '设备与隐私', icon: Cpu, group: '设置' },
]

export function ParentApp() {
  const { parentTab, setParentTab, setMode, goKid, animal, notices } = useAppStore()
  const unread = notices.filter((n) => !n.read).length

  return (
    <div className="flex h-full">
      <nav aria-label="家长端导航" className="flex w-20 shrink-0 flex-col border-r border-border bg-card md:w-56">
        <div className="flex items-center gap-3 p-4">
          <div className="relative size-11 shrink-0 overflow-hidden rounded-2xl" style={{ backgroundColor: '#f6e2c8' }}>
            <Image src={animal.image || '/placeholder.svg'} alt="" fill sizes="44px" className="scale-150 object-cover" />
          </div>
          <div className="hidden md:block">
            <p className="font-bold leading-tight">{CHILD_PROFILE.age ? `${CHILD_PROFILE.nickname}的家长` : '家长端'}</p>
            <p className="text-xs text-muted-foreground">
              {CHILD_PROFILE.age ? `${CHILD_PROFILE.age} 岁 · ` : '档案待设置 · '}伙伴{animal.name}
            </p>
          </div>
        </div>
        <div className="flex flex-1 flex-col gap-1 overflow-y-auto px-3">
          {['情绪', '设置'].map((g) => (
            <div key={g} className="mb-2">
              <p className="hidden px-3 py-2 text-xs font-semibold text-muted-foreground md:block">{g}</p>
              {NAV.filter((n) => n.group === g).map((n) => {
                const Icon = n.icon
                const active = parentTab === n.id
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => setParentTab(n.id)}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'relative flex w-full items-center justify-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition md:justify-start',
                      active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                    )}
                  >
                    <Icon className="size-5 shrink-0" />
                    <span className="hidden md:inline">{n.label}</span>
                    {n.id === 'notices' && unread > 0 && (
                      <span className="absolute right-2 top-1.5 flex size-5 items-center justify-center rounded-full bg-destructive text-[10px] text-white md:static md:ml-auto">
                        {unread}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
        <div className="p-3">
          <button
            type="button"
            onClick={() => {
              goKid({ name: 'home' })
              setMode('kid')
            }}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-secondary px-3 py-3 text-sm font-bold text-secondary-foreground transition hover:brightness-95"
          >
            <Baby className="size-5" />
            <span className="hidden md:inline">切换到儿童端</span>
          </button>
        </div>
      </nav>

      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl p-5 md:p-8">
          {parentTab === 'overview' && <Overview />}
          {parentTab === 'daily' && <DailyReport />}
          {parentTab === 'weekly' && <WeeklyReport />}
          {parentTab === 'notices' && <Notices />}
          {parentTab === 'schedule' && <ScheduleSettings />}
          {parentTab === 'profile' && <ProfileSettings />}
          {parentTab === 'device' && <DeviceSettings />}
        </div>
      </main>
    </div>
  )
}
