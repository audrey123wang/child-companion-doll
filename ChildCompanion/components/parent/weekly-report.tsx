'use client'

import { useState } from 'react'
import { AlertTriangle, Lightbulb } from 'lucide-react'
import { EmotionChip, Legend, PageHeader, Panel, Stat } from '@/components/parent/parts'
import { EMOTIONS, WEEK_DATA, WEEK_SUMMARY, type Emotion } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

const ALL: Emotion[] = ['happy', 'calm', 'miss', 'sad', 'worried', 'angry']

export function WeeklyReport() {
  const [sel, setSel] = useState(WEEK_DATA.length - 1)
  const day = WEEK_DATA[sel]

  if (!day) return <><PageHeader title="本周周报" sub="查看本周记录" /><Panel title="暂无周报"><p className="text-sm text-muted-foreground">本周还没有可展示的记录。</p></Panel></>

  return (
    <>
      <PageHeader title="本周周报" sub={WEEK_SUMMARY.range} />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="主动表达" value={WEEK_SUMMARY.activeTotal} unit="次" />
        <Stat label="听故事" value={WEEK_SUMMARY.storyTotal} unit="次" />
        <Stat label="故事时长" value={WEEK_SUMMARY.storyMinutes} unit="分钟" />
        <Stat label="有效记录" value="6/7" unit="天" hint="周四设备离线" />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel title="每日情绪" className="lg:col-span-2" action={<Legend emotions={ALL} />}>
          <div className="flex h-56 items-end gap-3" role="list">
            {WEEK_DATA.map((d, i) => (
              <button
                key={d.day}
                type="button"
                role="listitem"
                onClick={() => setSel(i)}
                aria-pressed={sel === i}
                aria-label={`${d.day} ${d.dominant ? EMOTIONS[d.dominant].label : '记录不足'}`}
                className={cn('flex h-full flex-1 flex-col items-center gap-2 rounded-2xl p-1.5 transition', sel === i && 'bg-muted')}
              >
                <div className="flex w-full max-w-10 flex-1 flex-col-reverse overflow-hidden rounded-xl bg-muted">
                  {d.mix.length === 0 ? (
                    <span className="flex h-full items-center justify-center border-2 border-dashed border-border text-xs text-muted-foreground">—</span>
                  ) : (
                    d.mix.map((m) => <span key={m.emotion} style={{ height: `${m.value}%`, backgroundColor: EMOTIONS[m.emotion].color }} />)
                  )}
                </div>
                <span className={cn('text-xs', sel === i ? 'font-bold' : 'text-muted-foreground')}>{d.day}</span>
              </button>
            ))}
          </div>
          <div className="mt-4 rounded-2xl border border-border p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-bold">
                {day.day} {day.date}
              </span>
              {day.dominant ? <EmotionChip emotion={day.dominant} /> : <span className="text-xs text-muted-foreground">记录不足</span>}
              <span className="text-xs text-muted-foreground">
                主动表达 {day.active} 次 · 故事 {day.stories} 个
              </span>
            </div>
            {day.note && <p className="mt-2 text-sm text-muted-foreground">{day.note}</p>}
          </div>
        </Panel>

        <Panel title="本周主题">
          <ul className="flex flex-col gap-3">
            {WEEK_SUMMARY.themes.map((t) => (
              <li key={t.topic} className="flex items-center justify-between rounded-2xl bg-muted/60 p-3">
                <div>
                  <p className="font-semibold">{t.topic}</p>
                  <p className="text-xs text-muted-foreground">{t.trend}</p>
                </div>
                <span className="text-2xl font-extrabold tabular-nums">
                  {t.count}
                  <span className="text-xs font-semibold text-muted-foreground"> 次</span>
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel title="下周沟通建议" className="mt-4">
        <ul className="grid gap-3 md:grid-cols-3">
          {WEEK_SUMMARY.suggestions.map((s) => (
            <li key={s} className="flex gap-3 rounded-2xl bg-secondary/35 p-4 text-sm leading-relaxed">
              <Lightbulb className="size-5 shrink-0 text-primary" />
              {s}
            </li>
          ))}
        </ul>
        <p className="mt-4 flex items-start gap-2 text-xs text-muted-foreground">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          {WEEK_SUMMARY.caution}
        </p>
      </Panel>
    </>
  )
}
