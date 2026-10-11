'use client'

import Image from 'next/image'
import { RABBIT_IMAGES, type RabbitState } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

/** 每种状态对应的轻微附加动画，避免生硬切图 */
const MOTION: Record<RabbitState, string> = {
  welcome: 'animate-rabbit-welcome',
  idle: 'animate-rabbit-breathe',
  listening: 'animate-rabbit-listen',
  thinking: 'animate-rabbit-think',
  speaking: 'animate-rabbit-nod',
}

export type RabbitCharacterProps = {
  /** 当前状态，由儿童首页统一控制 */
  state: RabbitState
  /** 立绘地址映射，默认使用兔子 5 张状态图 */
  sources?: Partial<Record<RabbitState, string>>
  /** 兜底图片（用于尚未提供多状态立绘的伙伴） */
  fallbackSrc?: string
  alt?: string
  className?: string
}

/**
 * 伙伴立绘。只负责“按状态呈现正确的图与轻微动画”，不持有状态机。
 */
export function RabbitCharacter({ state, sources = RABBIT_IMAGES, fallbackSrc, alt = '伙伴', className }: RabbitCharacterProps) {
  const src = sources[state] ?? fallbackSrc ?? RABBIT_IMAGES[state]

  return (
    <div className={cn('relative w-full', className)}>
      {/* 5 张图交叉叠放，切换时用 opacity + scale 平滑过渡 200–350ms */}
      {(Object.keys(RABBIT_IMAGES) as RabbitState[]).map((s) => {
        const layerSrc = sources[s] ?? fallbackSrc
        if (!layerSrc) return null
        const active = s === state
        return (
          <Image
            key={s}
            src={layerSrc}
            alt={active ? alt : ''}
            aria-hidden={!active}
            width={1024}
            height={1024}
            sizes="(min-width: 1024px) 620px, (min-width: 768px) 480px, 78vw"
            priority={s === 'welcome' || s === 'idle'}
            className={cn(
              'h-auto w-full origin-center select-none object-contain transition-[opacity,transform] duration-300 ease-out motion-reduce:transition-none',
              'max-h-[38vh] min-[700px]:max-h-[46vh] min-[900px]:max-h-[52vh] [@media(max-height:820px)]:max-h-[30vh] [@media(max-height:700px)]:max-h-[24vh]',
              s === Object.keys(RABBIT_IMAGES)[0] ? 'relative' : 'absolute inset-0',
              active ? `opacity-100 ${MOTION[state]} drop-shadow-[0_22px_28px_rgba(190,140,110,0.22)]` : 'pointer-events-none scale-[0.97] opacity-0',
            )}
            draggable={false}
          />
        )
      })}
    </div>
  )
}
