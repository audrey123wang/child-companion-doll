import { cn } from '@/lib/utils'
import { EMOTIONS, SOURCE_LABEL, type Emotion, type SourceType } from '@/lib/mock-data'

export function PageHeader({ title, sub, action }: { title: string; sub?: string; action?: React.ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight md:text-3xl">{title}</h1>
        {sub && <p className="mt-1 text-sm text-muted-foreground">{sub}</p>}
      </div>
      {action}
    </header>
  )
}

export function Panel({ title, action, className, children }: { title?: string; action?: React.ReactNode; className?: string; children: React.ReactNode }) {
  return (
    <section className={cn('rounded-3xl border border-border bg-card p-5', className)}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-2">
          {title && <h2 className="font-bold">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function EmotionBar({ mix, className }: { mix: { emotion: Emotion; value: number }[]; className?: string }) {
  return (
    <div className={cn('flex h-4 w-full overflow-hidden rounded-full bg-muted', className)}>
      {mix.map((m) => (
        <span key={m.emotion} style={{ width: `${m.value}%`, backgroundColor: EMOTIONS[m.emotion].color }} title={`${EMOTIONS[m.emotion].label} ${m.value}%`} />
      ))}
    </div>
  )
}

export function EmotionChip({ emotion }: { emotion: Emotion }) {
  const e = EMOTIONS[emotion]
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ backgroundColor: e.soft, color: '#4a2e1f' }}>
      <span className="size-2 rounded-full" style={{ backgroundColor: e.color }} />
      {e.label}
    </span>
  )
}

const SOURCE_STYLE: Record<SourceType, string> = {
  active: 'bg-primary/15 text-primary',
  ambient: 'bg-muted text-muted-foreground',
  chat: 'bg-accent/30 text-accent-foreground',
}

export function SourceChip({ source }: { source: SourceType }) {
  return <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-semibold', SOURCE_STYLE[source])}>{SOURCE_LABEL[source]}</span>
}

export function Stat({ label, value, unit, hint }: { label: string; value: string | number; unit?: string; hint?: string }) {
  return (
    <div className="rounded-3xl border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-3xl font-extrabold tabular-nums">
        {value}
        {unit && <span className="ml-1 text-sm font-semibold text-muted-foreground">{unit}</span>}
      </p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

export function Legend({ emotions }: { emotions: Emotion[] }) {
  return (
    <ul className="flex flex-wrap gap-3 text-xs text-muted-foreground">
      {emotions.map((e) => (
        <li key={e} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full" style={{ backgroundColor: EMOTIONS[e].color }} />
          {EMOTIONS[e].label}
        </li>
      ))}
    </ul>
  )
}
