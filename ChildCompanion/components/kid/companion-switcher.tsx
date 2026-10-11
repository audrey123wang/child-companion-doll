'use client'

import Image from 'next/image'
import { useAppStore } from '@/components/app-store'
import { ANIMALS } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

/**
 * 低存在感的“换伙伴”入口。仅展示立绘 + 名字，
 * 点击后进入现有的 AnimalPicker（功能保持不变）。
 */
export function CompanionSwitcher({ className }: { className?: string }) {
  const { animalId, setAnimalId, goKid } = useAppStore()
  const others = ANIMALS.filter((a) => a.id !== animalId).slice(0, 4)

  return (
    <div
      className={cn(
        'flex w-fit flex-col items-center gap-2.5 rounded-[1.5rem] border border-white/70 bg-card/55 px-4 py-4 shadow-[0_10px_24px_-20px_rgba(150,100,70,0.5)] backdrop-blur-sm',
        className,
      )}
    >
      <p className="text-xs font-semibold text-muted-foreground">换伙伴</p>
      <ul className="flex items-center gap-2">
        {others.map((a) => (
          <li key={a.id}>
            <button
              type="button"
              onClick={() => {
                setAnimalId(a.id)
                goKid({ name: 'home' })
              }}
              aria-label={`换成${a.name}`}
              title={a.name}
              className="flex size-9 items-center justify-center overflow-hidden rounded-full bg-muted/60 ring-1 ring-white/80 transition hover:scale-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary/60"
            >
              <Image src={a.image || '/placeholder.svg'} alt="" width={36} height={36} className="size-9 scale-125 object-cover" />
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => goKid({ name: 'pick' })}
        className="text-xs font-semibold text-muted-foreground underline-offset-4 transition hover:text-foreground hover:underline"
      >
        看看全部 ›
      </button>
    </div>
  )
}
