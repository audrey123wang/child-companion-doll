'use client'

import Image from 'next/image'
import { cn } from '@/lib/utils'
import { CHARACTER_STATES, type Animal, type CharacterState } from '@/lib/mock-data'

const ANIM: Record<CharacterState, string> = {
  welcome: 'animate-float',
  listening: 'animate-breathe',
  thinking: 'animate-wiggle',
  telling: 'animate-nod',
  resting: 'animate-sleepy',
}

export function Character({
  animal,
  state,
  className,
  showBadge = true,
  onClick,
}: {
  animal: Animal
  state: CharacterState
  className?: string
  showBadge?: boolean
  onClick?: () => void
}) {
  const Wrapper = onClick ? 'button' : 'div'
  return (
    <div className={cn('relative flex flex-col items-center', className)}>
      <Wrapper
        type={onClick ? 'button' : undefined}
        onClick={onClick}
        aria-label={onClick ? `${animal.name}，当前${CHARACTER_STATES[state].label}，点击切换状态` : undefined}
        className={cn(
          'relative aspect-square w-full overflow-hidden rounded-[2.5rem] border-4 border-card shadow-[0_18px_40px_-18px_rgba(120,70,30,0.45)]',
          ANIM[state],
          onClick && 'cursor-pointer focus-visible:outline-4 focus-visible:outline-primary',
        )}
        style={{ backgroundColor: '#f6e2c8' }}
      >
        <Image
          src={animal.image || '/placeholder.svg'}
          alt={`${animal.species}${animal.name}`}
          fill
          sizes="(min-width: 1024px) 420px, 60vw"
          className={cn('object-cover scale-125', state === 'resting' && 'saturate-50')}
          priority
        />
        {state === 'resting' && (
          <span className="absolute right-[18%] top-[14%] font-display text-3xl text-muted-foreground" aria-hidden>
            Zzz
          </span>
        )}
      </Wrapper>

      {showBadge && (
        <div className="-mt-5 flex items-center gap-2 rounded-full border-2 border-card bg-card px-4 py-1.5 shadow-md">
          <StateIndicator state={state} color={animal.color} />
          <span className="font-display text-base" style={{ color: animal.color }}>
            {CHARACTER_STATES[state].label}
          </span>
        </div>
      )}
    </div>
  )
}

function StateIndicator({ state, color }: { state: CharacterState; color: string }) {
  if (state === 'listening') {
    return (
      <span className="flex h-4 items-end gap-0.5" aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className="w-1 animate-pulse rounded-full"
            style={{ backgroundColor: color, height: `${6 + ((i * 5) % 10)}px`, animationDelay: `${i * 120}ms` }}
          />
        ))}
      </span>
    )
  }
  if (state === 'thinking') {
    return (
      <span className="flex gap-1" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="size-1.5 animate-bounce rounded-full"
            style={{ backgroundColor: color, animationDelay: `${i * 150}ms` }}
          />
        ))}
      </span>
    )
  }
  return <span className="size-2.5 rounded-full" style={{ backgroundColor: color }} aria-hidden />
}
