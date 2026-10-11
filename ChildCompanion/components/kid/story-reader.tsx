'use client'

import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'
import type { Story } from '@/lib/story-friendship'
import { useAppStore } from '@/components/app-store'
import { useStoryNarration } from '@/lib/use-story-narration'
import { cn } from '@/lib/utils'

/**
 * 绘本模式的故事阅读器（提词器式排版）。
 *
 * 布局取向：
 * - 图片固定在上方，占满可用高度；
 * - 文字在下方固定高度的滚动区域内，自动缓慢向上滚动（像滚动字幕）；
 * - 整页不出现外层滚动，图片、字幕、控件都在一屏内。
 *
 * 用户也可以手动滚动文字区查看，自动滚动会在用户操作后暂停片刻。
 */
export function StoryReader({
  story,
  onFinish,
  className,
}: {
  story: Story
  /** 最后一幕点击「听完啦」时触发 */
  onFinish: () => void
  className?: string
}) {
  const [current, setCurrent] = useState(0)
  const [prevImage, setPrevImage] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const resumeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const scene = story.scenes[current]
  const { childId } = useAppStore()
  const narration = useStoryNarration(childId, story.id, current, scene.text, () => {})
  const isFirst = current === 0
  const isLast = current === story.scenes.length - 1

  // 切页时保留上一张图做交叉淡入
  useEffect(() => {
    const prev = story.scenes[current - 1]?.image ?? null
    setPrevImage(prev)
    if (!prev) return
    const t = setTimeout(() => setPrevImage(null), 400)
    return () => clearTimeout(t)
  }, [current, story.scenes])

  // 换幕时把字幕拉回顶部，等待自动滚动
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = 0
  }, [current])

  // 滚动字幕：每帧缓慢上移，到底后停住
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return

    let raf = 0
    let last = performance.now()
    let paused = false

    const tick = (now: number) => {
      const dt = now - last
      last = now
      if (!paused && el) {
        const max = el.scrollHeight - el.clientHeight
        if (max > 4 && el.scrollTop < max) {
          el.scrollTop += dt * 0.02 // 约 20px/秒，缓慢滚动
        }
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)

    // 用户手动滚动时暂停自动滚动，1.6 秒后恢复
    const onManual = () => {
      paused = true
      if (resumeTimer.current) clearTimeout(resumeTimer.current)
      resumeTimer.current = setTimeout(() => {
        paused = false
        last = performance.now()
      }, 1600)
    }
    el.addEventListener('wheel', onManual, { passive: true })
    el.addEventListener('touchmove', onManual, { passive: true })

    return () => {
      cancelAnimationFrame(raf)
      el.removeEventListener('wheel', onManual)
      el.removeEventListener('touchmove', onManual)
      if (resumeTimer.current) clearTimeout(resumeTimer.current)
    }
  }, [current, scene.text])

  return (
    <div
      className={cn(
        'flex h-full min-h-0 w-full max-w-3xl flex-col items-center gap-2 sm:gap-3',
        className,
      )}
    >
      {/* 顶部：故事标题 */}
      <h2 className="shrink-0 text-center text-sm font-bold text-foreground/80 sm:text-base">
        {story.title}
      </h2>

      {/* 主体：大幅插画。弹性占据剩余高度，但不会把字幕挤出屏幕 */}
      <div className="flex min-h-0 w-full flex-1 items-center justify-center">
        <div className="relative h-full max-h-full w-full overflow-hidden rounded-[1.75rem] shadow-[0_18px_40px_-18px_rgba(180,130,100,0.45)] ring-1 ring-foreground/5">
          {prevImage && (
            <img
              src={prevImage}
              alt=""
              aria-hidden
              className="absolute inset-0 size-full object-cover transition-opacity duration-300 ease-out"
            />
          )}
          <img
            key={scene.image}
            src={scene.image}
            alt={`第 ${scene.index} 幕：${scene.title}`}
            className="absolute inset-0 size-full object-cover animate-scene-in"
          />
        </div>
      </div>

      {/* 滚动字幕区：固定高度，内部滚动，整页不滚动 */}
      <div className="shrink-0 overflow-hidden rounded-[1.5rem] bg-card/85 shadow-sm backdrop-blur-sm">
        <p className="pt-3 text-center text-sm font-bold text-primary sm:text-base">{scene.title}</p>

        <div
          ref={scrollRef}
          className={cn(
            'story-marquee mt-1 max-h-[7.5rem] overflow-y-auto px-5 pb-4 sm:max-h-[8.5rem] sm:px-7',
            '[@media(max-height:760px)]:max-h-[5.5rem]',
          )}
        >
          <div
            key={scene.index}
            className="animate-scene-in space-y-3 text-center text-[1.05rem] leading-relaxed text-foreground/85 sm:text-lg sm:leading-loose"
          >
            {scene.text.split('\n\n').map((para, i) => (
              <p key={i} className="whitespace-pre-line">
                {para}
              </p>
            ))}
            {/* 底部留白，让最后一段能滚到中间位置 */}
            <div aria-hidden className="h-6" />
          </div>
        </div>
      </div>

      {/* 底部：翻页 + 进度点。最后一幕换成「听完啦」 */}
      <div className="flex shrink-0 flex-col items-center gap-1">
        <button type="button" onClick={narration.playing ? narration.pause : narration.play} disabled={narration.loading} className="flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">
          {narration.playing ? <Pause className="size-4" /> : <Play className="size-4" />}
          {narration.loading ? '正在生成配音…' : narration.playing ? '暂停配音' : narration.started ? '继续配音' : '播放本页配音'}
        </button>
        {narration.error && <p role="alert" className="text-xs text-destructive">{narration.error}</p>}
        <p className="text-[11px] text-muted-foreground">这段声音由 AI 生成</p>
      </div>
      <div className="flex shrink-0 w-full items-center justify-center gap-4">
        <button
          type="button"
          onClick={() => setCurrent((c) => Math.max(0, c - 1))}
          disabled={isFirst}
          aria-label="上一页"
          className="flex size-10 items-center justify-center rounded-full text-muted-foreground transition hover:bg-card/80 hover:text-foreground disabled:pointer-events-none disabled:opacity-25"
        >
          <ChevronLeft className="size-6" />
        </button>

        <div className="flex items-center gap-2" role="tablist" aria-label="故事进度">
          {story.scenes.map((s, i) => (
            <button
              key={s.index}
              type="button"
              role="tab"
              aria-selected={i === current}
              aria-label={`第 ${s.index} 幕`}
              onClick={() => setCurrent(i)}
              className={cn(
                'size-2.5 rounded-full transition-all',
                i === current ? 'w-6 bg-primary' : 'bg-foreground/20 hover:bg-foreground/35',
              )}
            />
          ))}
        </div>

        {isLast ? (
          <button
            type="button"
          onClick={() => { narration.stop(); onFinish() }}
            className="h-10 rounded-full bg-primary/90 px-6 text-sm font-bold text-primary-foreground shadow-sm transition active:scale-[0.97] sm:text-base"
          >
            听完啦
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setCurrent((c) => Math.min(story.scenes.length - 1, c + 1))}
            aria-label="下一页"
            className="flex size-10 items-center justify-center rounded-full text-muted-foreground transition hover:bg-card/80 hover:text-foreground"
          >
            <ChevronRight className="size-6" />
          </button>
        )}
      </div>
    </div>
  )
}
