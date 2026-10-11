'use client'

import { useState } from 'react'
import Image from 'next/image'
import { Check } from 'lucide-react'
import { useAppStore } from '@/components/app-store'
import { ANIMALS, type AnimalId } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

export function AnimalPicker() {
  const { animalId, setAnimalId, goKid } = useAppStore()
  const [selected, setSelected] = useState<AnimalId>(animalId)
  const current = ANIMALS.find((a) => a.id === selected)!

  return (
    <div className="flex h-full flex-col items-center gap-5 overflow-y-auto px-6 pb-6 pt-2">
      <h1 className="font-display text-3xl">选一个好朋友陪你吧</h1>
      <ul className="grid w-full max-w-5xl grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {ANIMALS.map((a) => {
          const active = a.id === selected
          return (
            <li key={a.id}>
              <button
                type="button"
                onClick={() => setSelected(a.id)}
                aria-pressed={active}
                className={cn(
                  'relative flex w-full flex-col items-center gap-2 rounded-[2rem] border-4 bg-card p-3 pb-4 transition active:scale-95',
                  active ? 'shadow-lg' : 'border-transparent opacity-90',
                )}
                style={{ borderColor: active ? a.color : undefined }}
              >
                <div className="relative aspect-square w-full overflow-hidden rounded-[1.5rem]" style={{ backgroundColor: '#f6e2c8' }}>
                  <Image src={a.image || '/placeholder.svg'} alt={a.species} fill sizes="200px" className="scale-125 object-cover" />
                </div>
                <span className="font-display text-2xl" style={{ color: a.color }}>
                  {a.name}
                </span>
                <span className="text-sm text-muted-foreground">{a.species}</span>
                {active && (
                  <span
                    className="absolute right-3 top-3 flex size-8 items-center justify-center rounded-full text-white"
                    style={{ backgroundColor: a.color }}
                  >
                    <Check className="size-5" />
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ul>
      <p className="text-center text-muted-foreground">
        {current.name}：{current.trait}
      </p>
      <button
        type="button"
        onClick={() => {
          setAnimalId(selected)
          goKid({ name: 'home' })
        }}
        className="h-16 rounded-full px-14 font-display text-2xl text-white shadow-[0_6px_0_0_rgba(0,0,0,0.12)] transition active:translate-y-1 active:shadow-none"
        style={{ backgroundColor: current.color }}
      >
        就选{current.name}！
      </button>
    </div>
  )
}
