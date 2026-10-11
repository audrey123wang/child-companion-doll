'use client'

import { cn } from '@/lib/utils'

/**
 * 对话中的轻量快捷选择。
 *
 * 注意：这不是首页的大按钮，而是当前对话气泡下方的小选项，
 * 存在感刻意做弱，不抢兔子与气泡的视觉焦点。
 */
export function QuickChoices({
  options,
  onPick,
  className,
}: {
  options: string[]
  onPick: (label: string) => void
  className?: string
}) {
  if (options.length === 0) return null

  return (
    <div className={cn('flex flex-wrap items-center justify-center gap-2.5', className)}>
      {options.map((label, i) => (
        <button
          key={label}
          type="button"
          onClick={() => onPick(label)}
          className="animate-bubble-in rounded-full border border-primary/25 bg-card/90 px-5 py-2.5 text-sm font-semibold text-foreground/80 shadow-sm backdrop-blur-sm transition hover:border-primary/50 hover:text-primary active:scale-[0.97]"
          style={{ animationDelay: `${i * 70}ms` }}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
