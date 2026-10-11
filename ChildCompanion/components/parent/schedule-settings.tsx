'use client'

import { useState } from 'react'
import { Plus, RefreshCw, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { useAppStore } from '@/components/app-store'
import { PageHeader, Panel } from '@/components/parent/parts'
import { DEVICE, WEEKDAYS } from '@/lib/mock-data'

const toMin = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3))
const START = 7 * 60
const END = 22 * 60

export function ScheduleSettings() {
  const { schedule, setSchedule, micPaused, setMicPaused } = useAppStore()
  const [syncing, setSyncing] = useState(false)
  const [version, setVersion] = useState(12)
  const [dirty, setDirty] = useState(false)

  function edit(fn: Parameters<typeof setSchedule>[0]) {
    setSchedule(fn)
    setDirty(true)
  }

  return (
    <>
      <PageHeader
        title="收音时段"
        sub="只在设置的时段内收音，时段外娃娃不会监听"
        action={
          <Button
            size="lg"
            disabled={syncing}
            onClick={() => {
              setSyncing(true)
              setTimeout(() => {
                setSyncing(false)
                setDirty(false)
                setVersion((v) => v + 1)
                toast.success(`已同步到${DEVICE.name}，设置版本 #${version + 1}`)
              }, 1400)
            }}
          >
            <RefreshCw className={syncing ? 'animate-spin' : ''} />
            {syncing ? '同步中…' : dirty ? '保存并同步到设备' : `已同步 #${version}`}
          </Button>
        }
      />

      <Panel className="mb-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-bold">临时暂停收音</p>
            <p className="text-sm text-muted-foreground">开启后娃娃 LED 会变为“休息中”，直到您手动恢复</p>
          </div>
          <Switch
            checked={micPaused}
            onCheckedChange={(v) => {
              setMicPaused(v)
              toast(v ? '已暂停收音' : '已恢复按时段收音')
            }}
            aria-label="临时暂停收音"
          />
        </div>
      </Panel>

      <Panel title="每周时段" action={<span className="text-xs text-muted-foreground">07:00 – 22:00</span>}>
        <ul className="flex flex-col gap-3">
          {WEEKDAYS.map((d) => {
            const slots = schedule[d] ?? []
            const on = slots.length > 0
            return (
              <li key={d} className="flex flex-col gap-2 rounded-2xl border border-border p-3 md:flex-row md:items-center md:gap-4">
                <div className="flex w-28 items-center gap-3">
                  <Switch
                    checked={on}
                    onCheckedChange={(v) => edit((s) => ({ ...s, [d]: v ? [{ start: '16:00', end: '19:00' }] : [] }))}
                    aria-label={`${d}收音`}
                  />
                  <span className="font-semibold">{d}</span>
                </div>
                <div className="relative h-8 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden>
                  {slots.map((s, i) => (
                    <span
                      key={i}
                      className="absolute inset-y-1 rounded-full bg-accent"
                      style={{
                        left: `${((toMin(s.start) - START) / (END - START)) * 100}%`,
                        width: `${((toMin(s.end) - toMin(s.start)) / (END - START)) * 100}%`,
                      }}
                    />
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-2 md:w-72 md:justify-end">
                  {slots.map((s, i) => (
                    <span key={i} className="flex items-center gap-1 rounded-full bg-accent/25 py-1 pl-3 pr-1 text-sm tabular-nums">
                      {s.start}–{s.end}
                      <button
                        type="button"
                        aria-label="删除时段"
                        onClick={() => edit((sch) => ({ ...sch, [d]: sch[d].filter((_, j) => j !== i) }))}
                        className="rounded-full p-1 hover:bg-background"
                      >
                        <X className="size-3" />
                      </button>
                    </span>
                  ))}
                  {slots.length < 2 && (
                    <button
                      type="button"
                      onClick={() =>
                        edit((sch) => ({
                          ...sch,
                          [d]: [...(sch[d] ?? []), slots.length === 0 ? { start: '16:00', end: '19:00' } : { start: '09:00', end: '11:30' }],
                        }))
                      }
                      className="flex items-center gap-1 rounded-full border border-dashed border-border px-3 py-1 text-sm text-muted-foreground hover:text-foreground"
                    >
                      <Plus className="size-3.5" /> 时段
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
        <p className="mt-4 text-xs text-muted-foreground">
          孩子随时可以按娃娃按键主动说话，不受时段限制。设备断网时将按最近一次同步的规则运行。
        </p>
      </Panel>
    </>
  )
}
