'use client'

import { cn } from '@/lib/utils'

/**
 * 伙伴当前正在说的一句话。
 * 只展示“此刻这一句”，不是聊天历史。
 */
export function CharacterSpeechBubble({ text, className }: { text: string; className?: string }) {
  return (
    <div className={cn('relative w-full max-w-[30rem]', className)}>
      <div
        role="status"
        aria-live="polite"
        className="rounded-[2rem] border border-white/70 bg-card/95 px-7 py-5 text-center shadow-[0_14px_34px_-18px_rgba(150,100,70,0.45)] backdrop-blur-sm"
      >
        <p key={text} className="animate-bubble-in font-display text-[1.35rem] leading-relaxed text-balance sm:text-2xl">
          {text}
        </p>
      </div>
      {/* 底部小三角，指向兔子 */}
      <span
        aria-hidden
        className="absolute -bottom-2 left-1/2 size-5 -translate-x-1/2 rotate-45 rounded-[3px] border-b border-r border-white/70 bg-card/95"
      />
    </div>
  )
}
