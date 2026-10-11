'use client'

import { Mic } from 'lucide-react'
import { cn } from '@/lib/utils'

export type VoiceButtonProps = {
  /** 是否处于录音态 */
  listening: boolean
  /** 是否可以点击（思考/说话过程中不可点） */
  disabled?: boolean
  onClick: () => void
  className?: string
}

const HINT = {
  idle: '按一下，和我说话',
  listening: '我在听呢，再按一下结束',
  busy: '语音功能待接入',
} as const

/**
 * 底部中央的主交互按钮。接入录音前保持禁用，避免伪造识别结果。
 */
export function VoiceButton({ listening, disabled = false, onClick, className }: VoiceButtonProps) {
  const hint = listening ? HINT.listening : disabled ? HINT.busy : HINT.idle

  return (
    <div className={cn('flex flex-col items-center gap-3', className)}>
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-pressed={listening}
        aria-label={hint}
        className={cn(
          'relative flex size-24 items-center justify-center rounded-full text-white shadow-[0_12px_26px_-10px_rgba(190,110,140,0.65)] transition-transform duration-200 ease-out',
          'focus-visible:outline-4 focus-visible:outline-offset-4 focus-visible:outline-primary/60',
          disabled ? 'cursor-not-allowed opacity-70' : 'hover:scale-[1.04] active:scale-95',
          !disabled && 'motion-reduce:animate-none',
        )}
        style={{
          background: listening
            ? 'linear-gradient(160deg, #ff9fb8 0%, #f27aa0 55%, #e9618c 100%)'
            : 'linear-gradient(160deg, #ffb3c6 0%, #f2899f 55%, #e2718d 100%)',
        }}
      >
        {/* listening 时的柔光脉冲 */}
        {listening && (
          <>
            <span aria-hidden className="absolute inset-0 animate-mic-ring rounded-full bg-primary/40 motion-reduce:hidden" />
            <span aria-hidden className="absolute -inset-2 animate-mic-glow rounded-full bg-primary/25 blur-md motion-reduce:hidden" />
          </>
        )}
        <Mic className={cn('relative size-10 transition-transform duration-200', listening && 'scale-110')} />
      </button>
      <p
        className={cn(
          'rounded-full bg-card/80 px-4 py-1.5 text-sm font-semibold text-muted-foreground shadow-sm backdrop-blur-sm transition-colors sm:text-base',
          listening && 'text-primary',
        )}
      >
        {hint}
      </p>
    </div>
  )
}
