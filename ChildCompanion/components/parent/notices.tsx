'use client'

import { useState } from 'react'
import { BatteryLow, CalendarDays, CalendarRange, ShieldAlert } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { useAppStore } from '@/components/app-store'
import { PageHeader, Panel } from '@/components/parent/parts'
import type { Notice } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

const ICON: Record<Notice['type'], { icon: React.ElementType; cls: string }> = {
  daily: { icon: CalendarDays, cls: 'bg-secondary text-secondary-foreground' },
  weekly: { icon: CalendarRange, cls: 'bg-accent/40 text-accent-foreground' },
  attention: { icon: ShieldAlert, cls: 'bg-primary/15 text-primary' },
  device: { icon: BatteryLow, cls: 'bg-muted text-muted-foreground' },
}

const TARGET: Record<Notice['type'], 'daily' | 'weekly' | 'device'> = {
  daily: 'daily',
  weekly: 'weekly',
  attention: 'daily',
  device: 'device',
}

export function Notices() {
  const { notices, setNotices, setParentTab } = useAppStore()
  const [preview, setPreview] = useState<Notice | undefined>(notices[0])
  const [prefs, setPrefs] = useState({ daily: true, weekly: true, attention: true, device: true })
  const [time, setTime] = useState('19:00')

  if (notices.length === 0) return <><PageHeader title="报告消息" sub="查看报告消息" /><Panel title="暂无消息"><p className="text-sm text-muted-foreground">目前没有新消息。</p></Panel></>

  return (
    <>
      <PageHeader
        title="报告推送"
        sub="通知锁屏只显示概括，不展示孩子原话"
        action={
          <button
            type="button"
            className="text-sm font-semibold text-primary"
            onClick={() => setNotices((n) => n.map((x) => ({ ...x, read: true })))}
          >
            全部标为已读
          </button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-5">
        <Panel title="消息" className="lg:col-span-3">
          <ul className="flex flex-col gap-2">
            {notices.map((n) => {
              const { icon: Icon, cls } = ICON[n.type]
              return (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setPreview(n)
                      setNotices((list) => list.map((x) => (x.id === n.id ? { ...x, read: true } : x)))
                    }}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-2xl p-3 text-left transition hover:bg-muted/60',
                      preview?.id === n.id && 'bg-muted/60',
                    )}
                  >
                    <span className={cn('flex size-10 shrink-0 items-center justify-center rounded-xl', cls)}>
                      <Icon className="size-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className="font-semibold">{n.title}</span>
                        {!n.read && <span className="size-2 rounded-full bg-destructive" aria-label="未读" />}
                      </span>
                      <span className="mt-0.5 block text-sm text-muted-foreground">{n.body}</span>
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">{n.time}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </Panel>

        <div className="flex flex-col gap-4 lg:col-span-2">
          <Panel title="锁屏预览">
            <div className="rounded-[2rem] bg-gradient-to-b from-[#4a2e1f] to-[#7a4a2e] p-5 text-white">
              <p className="text-center text-4xl font-light tabular-nums">19:02</p>
              <p className="mb-5 text-center text-xs opacity-75">10月11日 星期日</p>
              <div className="rounded-2xl bg-white/20 p-3 backdrop-blur">
                <p className="text-xs opacity-80">嘟嘟 · 现在</p>
                <p className="mt-1 text-sm font-semibold">{preview?.lockText}</p>
              </div>
            </div>
            {preview && (
              <button
                type="button"
                onClick={() => setParentTab(TARGET[preview.type])}
                className="mt-3 w-full rounded-xl bg-primary py-2.5 text-sm font-bold text-primary-foreground"
              >
                打开查看详情
              </button>
            )}
          </Panel>

          <Panel title="推送设置">
            <ul className="flex flex-col gap-4 text-sm">
              <li className="flex items-center justify-between gap-3">
                <span>
                  <span className="block font-semibold">每日日报</span>
                  <label className="text-xs text-muted-foreground">
                    推送时间
                    <select value={time} onChange={(e) => setTime(e.target.value)} className="ml-2 rounded-md border border-border bg-background px-1.5 py-0.5">
                      {['18:00', '19:00', '20:00', '21:00'].map((t) => (
                        <option key={t}>{t}</option>
                      ))}
                    </select>
                  </label>
                </span>
                <Switch checked={prefs.daily} onCheckedChange={(v) => setPrefs((p) => ({ ...p, daily: v }))} aria-label="每日日报" />
              </li>
              {(
                [
                  ['weekly', '每周周报', '每周日 20:00'],
                  ['attention', '需关注提醒', '求助、危险相关内容立即提醒'],
                  ['device', '设备提醒', '低电量、离线、收音异常'],
                ] as const
              ).map(([k, label, hint]) => (
                <li key={k} className="flex items-center justify-between gap-3">
                  <span>
                    <span className="block font-semibold">{label}</span>
                    <span className="text-xs text-muted-foreground">{hint}</span>
                  </span>
                  <Switch checked={prefs[k]} onCheckedChange={(v) => setPrefs((p) => ({ ...p, [k]: v }))} aria-label={label} />
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </>
  )
}
