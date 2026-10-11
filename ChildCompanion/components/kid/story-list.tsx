'use client'

import { useState } from 'react'
import Image from 'next/image'
import { Clock, Heart } from 'lucide-react'
import { useAppStore } from '@/components/app-store'
import { STORIES, TODAY_SUMMARY } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

const FILTERS = ['全部', '想念家人', '交朋友', '勇气', '分享', '睡前安定', '纯娱乐']

export function StoryList() {
  const { goKid, animal, pushedStories } = useAppStore()
  const [filter, setFilter] = useState('全部')
  const recommendedIds = Array.from(new Set([...pushedStories, ...TODAY_SUMMARY.recommendedStories]))
  const recommended = recommendedIds.map((id) => STORIES.find((s) => s.id === id)!).slice(0, 2)
  const list = STORIES.filter((s) => filter === '全部' || s.tags.includes(filter))

  return (
    <div className="h-full overflow-y-auto px-6 pb-8 pt-2">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <section aria-labelledby="rec">
          <h2 id="rec" className="mb-3 flex items-center gap-2 font-display text-2xl">
            <Heart className="size-6" style={{ color: animal.color }} fill={animal.color} />
            {animal.name}今天想给你讲
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {recommended.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => goKid({ name: 'player', storyId: s.id })}
                className="flex items-center gap-4 overflow-hidden rounded-[2rem] bg-card p-3 text-left shadow-sm transition active:scale-[0.98]"
              >
                <div className="relative aspect-square w-28 shrink-0 overflow-hidden rounded-[1.5rem]">
                  <Image src={s.cover || '/placeholder.svg'} alt="" fill sizes="112px" className="object-cover" />
                </div>
                <div className="flex flex-col gap-1">
                  <span className="font-display text-2xl">{s.title}</span>
                  <span className="text-sm text-muted-foreground">{s.reason}</span>
                  <span className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="size-3.5" /> {Math.round(s.duration / 60)} 分钟
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section aria-labelledby="all">
          <h2 id="all" className="sr-only">全部故事</h2>
          <div className="mb-4 flex gap-2 overflow-x-auto pb-1" role="tablist">
            {FILTERS.map((f) => (
              <button
                key={f}
                role="tab"
                aria-selected={filter === f}
                type="button"
                onClick={() => setFilter(f)}
                className={cn(
                  'h-11 shrink-0 rounded-full px-5 font-display text-lg transition',
                  filter === f ? 'text-white' : 'bg-card text-muted-foreground',
                )}
                style={filter === f ? { backgroundColor: animal.color } : undefined}
              >
                {f}
              </button>
            ))}
          </div>
          <ul className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
            {list.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => goKid({ name: 'player', storyId: s.id })}
                  className="flex w-full flex-col overflow-hidden rounded-[1.75rem] bg-card text-left shadow-sm transition active:scale-95"
                >
                  <div className="relative aspect-[4/3] w-full">
                    <Image src={s.cover || '/placeholder.svg'} alt="" fill sizes="300px" className="object-cover" />
                    <span className="absolute left-3 top-3 rounded-full bg-card/90 px-3 py-1 text-xs font-semibold">
                      {s.tags[0]}
                    </span>
                  </div>
                  <div className="p-4">
                    <span className="block font-display text-xl">{s.title}</span>
                    <span className="text-xs text-muted-foreground">
                      {Math.round(s.duration / 60)} 分钟 · {s.age}
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
