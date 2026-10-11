'use client'

import { useState } from 'react'
import Image from 'next/image'
import { BookOpen, Home, MessageCircleHeart, Pause, Play, SkipBack, SkipForward } from 'lucide-react'
import { useAppStore } from '@/components/app-store'
import { Character } from '@/components/kid/character'
import { STORIES } from '@/lib/mock-data'
import { useStoryNarration } from '@/lib/use-story-narration'

export function StoryPlayer({ storyId }: { storyId: string }) {
  const { animal, goKid, childId } = useAppStore()
  const story = STORIES.find((s) => s.id === storyId) ?? STORIES[0]
  const [page, setPage] = useState(0)
  const done = page >= story.pages.length
  const narration = useStoryNarration(childId, story.id, Math.min(page, story.pages.length - 1), story.pages[Math.min(page, story.pages.length - 1)], () => {})
  const progress = Math.min(1, (page + 1) / story.pages.length)

  if (done) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-6 px-6 pb-6 sm:flex-row sm:gap-12">
        <Character animal={animal} state="welcome" className="w-56 sm:w-72" />
        <div className="flex max-w-md flex-col gap-4">
          <p className="font-display text-3xl leading-snug">故事讲完啦！</p>
          <p className="text-lg text-muted-foreground">想和{animal.name}聊聊这个故事吗？</p>
          <button
            type="button"
            onClick={() => goKid({ name: 'chat', storyId: story.id })}
            className="flex h-16 items-center justify-center gap-3 rounded-full font-display text-2xl text-white shadow-[0_6px_0_0_rgba(0,0,0,0.12)] active:translate-y-1 active:shadow-none"
            style={{ backgroundColor: animal.color }}
          >
            <MessageCircleHeart className="size-7" /> 聊一聊
          </button>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => goKid({ name: 'stories' })}
              className="flex h-14 items-center justify-center gap-2 rounded-full bg-secondary font-display text-xl"
            >
              <BookOpen className="size-5" /> 再听一个
            </button>
            <button
              type="button"
              onClick={() => goKid({ name: 'home' })}
              className="flex h-14 items-center justify-center gap-2 rounded-full bg-card font-display text-xl"
            >
              <Home className="size-5" /> 回家
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col gap-4 px-6 pb-5 pt-2">
      <div className="flex min-h-0 flex-1 flex-col gap-5 sm:flex-row">
        <div className="relative min-h-48 flex-1 overflow-hidden rounded-[2rem] shadow-md sm:flex-[1.3]">
          <Image src={story.cover || '/placeholder.svg'} alt={story.title} fill sizes="60vw" className="object-cover" priority />
          <div className="absolute bottom-4 left-4 w-24 sm:w-28">
            <Character animal={animal} state={narration.playing ? 'telling' : 'listening'} showBadge={false} />
          </div>
        </div>
        <div className="flex flex-1 flex-col justify-between gap-4 rounded-[2rem] bg-card p-6 shadow-sm">
          <div>
            <p className="text-sm text-muted-foreground">
              {animal.name}讲故事 · 第 {page + 1}/{story.pages.length} 页
            </p>
            <h1 className="mt-1 font-display text-3xl">{story.title}</h1>
          </div>
          <p className="text-pretty text-2xl leading-relaxed" aria-live="polite">
            {story.pages[page]}
          </p>
          <div className="flex gap-1.5" aria-hidden>
            {story.pages.map((_, i) => (
              <span
                key={i}
                className="h-2 flex-1 rounded-full"
                style={{ backgroundColor: i <= page ? animal.color : 'var(--muted)' }}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-4 rounded-full bg-card px-4 py-3 shadow-sm">
        <button
          type="button"
          aria-label="上一页"
          onClick={() => {
            setPage((p) => Math.max(0, p - 1))
          }}
          className="flex size-14 items-center justify-center rounded-full bg-muted"
        >
          <SkipBack className="size-6" />
        </button>
        <button
          type="button"
          aria-label={narration.playing ? '暂停配音' : '播放配音'}
          onClick={narration.playing ? narration.pause : narration.play}
          disabled={narration.loading}
          className="flex size-16 items-center justify-center rounded-full text-white"
          style={{ backgroundColor: animal.color }}
        >
          {narration.playing ? <Pause className="size-8" fill="currentColor" /> : <Play className="size-8" fill="currentColor" />}
        </button>
        <button
          type="button"
          aria-label="下一页"
          onClick={() => {
            if (page === story.pages.length - 1) narration.stop()
            setPage((p) => p + 1)
          }}
          className="flex size-14 items-center justify-center rounded-full bg-muted"
        >
          <SkipForward className="size-6" />
        </button>
        <div className="h-3 flex-1 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="故事进度">
          <div className="h-full rounded-full transition-[width]" style={{ width: `${progress * 100}%`, backgroundColor: animal.color }} />
        </div>
        <span className="w-24 text-right text-sm tabular-nums text-muted-foreground">
          {page + 1} / {story.pages.length} 页
        </span>
      </div>
      {narration.error && <p role="alert" className="text-sm text-destructive">{narration.error}</p>}
      <p className="text-center text-xs text-muted-foreground">这段声音由 AI 生成</p>
    </div>
  )
}
