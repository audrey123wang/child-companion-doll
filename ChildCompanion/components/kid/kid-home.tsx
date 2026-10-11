'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { useAppStore } from '@/components/app-store'
import { CharacterSpeechBubble } from '@/components/kid/character-speech-bubble'
import { CompanionSwitcher } from '@/components/kid/companion-switcher'
import { QuickChoices } from '@/components/kid/quick-choices'
import { RabbitCharacter } from '@/components/kid/rabbit-character'
import { StoryReader } from '@/components/kid/story-reader'
import { VoiceButton } from '@/components/kid/voice-button'
import { RABBIT_IMAGES, STORIES, type RabbitState } from '@/lib/mock-data'
import { FRIENDSHIP_STORY } from '@/lib/story-friendship'
import { cn } from '@/lib/utils'

/**
 * 单页 AI 陪伴体验 · 主状态机
 *
 * CompanionMode 控制「当前页面大场景」，RabbitState 控制「兔子当前状态」。
 * 两者是正交的：例如 storyReflection 场景下兔子可以是 speaking。
 *
 * 首页负责角色和故事展示；语音按钮进入真实录音问答页。
 */
type CompanionMode = 'companion' | 'chatting' | 'story' | 'storyReflection'

/** 各状态对应的一句话 */
const LINES: Record<RabbitState, string> = {
  welcome: '晚上好啊，\n你是想听个故事呢，\n还是一起聊聊天啊',
  idle: '今天想和我说点什么呀？',
  listening: '我在听呢～',
  thinking: '让我想一想～',
  speaking: '我在认真回应你',
}

/** 各状态对应的说明文字 */
const STATUS: Record<RabbitState, string> = {
  welcome: '正在和你打招呼',
  idle: '在等你开口',
  listening: '正在认真听你说',
  thinking: '正在想你的话',
  speaking: '正在回应你',
}

const TIMING = {
  welcome: 2000,
  thinking: 1200,
  speaking: 2500,
} as const

export function KidHome() {
  const { animal, goKid, pushedStories } = useAppStore()

  // ── 大场景 ────────────────────────────────────────────────
  const [mode, setMode] = useState<CompanionMode>('companion')
  // ── 兔子状态 ──────────────────────────────────────────────
  const [state, setState] = useState<RabbitState>('welcome')
  // ── 当前气泡要说的内容（null 表示用 LINES 默认值）──────────
  const [speech, setSpeech] = useState<string | null>(null)
  // ── 当前可用的快捷选项 ────────────────────────────────────
  const [choices, setChoices] = useState<string[]>([])
  // ── 场景淡出用（story 切换时让兔子先淡出再换场景）─────────
  const [stageFading, setStageFading] = useState(false)

  const greeted = useRef(false)
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])
  const pushed = pushedStories.map((id) => STORIES.find((s) => s.id === id)).filter(Boolean)[0]

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout)
    timers.current = []
  }, [])

  const later = useCallback((fn: () => void, ms: number) => {
    const t = setTimeout(fn, ms)
    timers.current.push(t)
    return t
  }, [])

  useEffect(() => clearTimers, [clearTimers])

  // welcome → idle
  useEffect(() => {
    if (mode !== 'companion' || state !== 'welcome') return
    const t = setTimeout(() => {
      greeted.current = true
      setState('idle')
    }, TIMING.welcome)
    timers.current.push(t)
    return () => clearTimeout(t)
  }, [state, mode])

  // thinking → speaking →（根据场景决定落点）
  useEffect(() => {
    if (state === 'thinking') {
      const t = setTimeout(() => setState('speaking'), TIMING.thinking)
      timers.current.push(t)
      return () => clearTimeout(t)
    }
    if (state === 'speaking' && mode === 'companion') {
      // 纯陪伴态下的自说自话，说完回到 idle
      const t = setTimeout(() => setState('idle'), TIMING.speaking)
      timers.current.push(t)
      return () => clearTimeout(t)
    }
    return undefined
  }, [state, mode])

  function onVoice() { goKid({ name: 'chat' }) }

  function onPick(label: string) {
    if (label === '听故事') enterStory()
    if (label === '聊一聊') goKid({ name: 'chat' })
  }

  // ── 进入故事模式：先淡出兔子区，再切场景 ──────────────────
  function enterStory() {
    setStageFading(true)
    clearTimers()
    setChoices([])
    setSpeech(null)
    later(() => {
      setMode('story')
      setState('idle')
      setStageFading(false)
    }, 380)
  }

  // ── 故事结束：进入 storyReflection，嘟嘟重新淡入 ───────────
  function onStoryFinish() {
    setStageFading(true)
    clearTimers()
    later(() => {
      setMode('storyReflection')
      setStageFading(false)
      setSpeech('故事讲完啦。要和我聊聊朋友的事吗？')
      setState('speaking')
      setChoices(['聊一聊'])
    }, 380)
  }

  const isStory = mode === 'story'
  const bubbleText = speech ?? LINES[state]

  return (
    <div
      className={cn(
        'relative flex h-full flex-col items-center px-5 pb-5 pt-1 sm:px-8 lg:pb-6',
        // 故事模式必须一屏装下（图片 + 滚动字幕 + 控件），禁止外层滚动
        isStory ? 'overflow-hidden' : 'overflow-y-auto',
      )}
    >
      {/* 左侧弱入口：换伙伴。故事模式下隐藏，避免干扰阅读 */}
      {!isStory && (
        <CompanionSwitcher className="mt-2 self-start sm:absolute sm:left-6 sm:top-4 sm:z-10 sm:mt-0" />
      )}

      {/* ── 故事场景 ─────────────────────────────────────── */}
      {isStory ? (
        <div
          className={cn(
            'flex min-h-0 w-full flex-1 flex-col items-center py-1',
            'transition-opacity duration-300 ease-out',
            stageFading ? 'opacity-0' : 'opacity-100 animate-fade-up',
          )}
        >
          <StoryReader story={FRIENDSHIP_STORY} onFinish={onStoryFinish} />
        </div>
      ) : (
        /* ── 陪伴 / 聊天 / 反思场景 ─────────────────────── */
        <div
          className={cn(
            'flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-3 sm:gap-4 [@media(max-height:820px)]:gap-2 lg:gap-5',
            'transition-opacity duration-300 ease-out',
            stageFading ? 'opacity-0' : 'opacity-100',
          )}
        >
          <CharacterSpeechBubble text={bubbleText} />

          <RabbitCharacter
            state={state}
            sources={animal.states ?? RABBIT_IMAGES}
            fallbackSrc={animal.image}
            alt={`${animal.species}${animal.name}`}
            className="w-[76%] max-w-[34rem] sm:w-[68%] lg:w-[58%]"
          />

          <p
            className="flex items-center gap-2 rounded-full bg-card/70 px-4 py-1.5 text-sm font-semibold text-muted-foreground shadow-sm backdrop-blur-sm sm:text-base"
            aria-live="polite"
          >
            <span className="size-2 rounded-full bg-primary/70 animate-pulse motion-reduce:animate-none" aria-hidden />
            {STATUS[state]}
          </p>

          {/* 对话中的轻量快捷选择 */}
          <QuickChoices options={choices} onPick={onPick} className="min-h-0" />

          <VoiceButton listening={false} onClick={onVoice} />

          {pushed && mode === 'companion' && (
            <button
              type="button"
              onClick={() => goKid({ name: 'player', storyId: pushed.id })}
              className="flex items-center gap-2 rounded-full border border-dashed border-primary/40 bg-card/80 px-5 py-2.5 text-sm font-semibold transition active:scale-[0.98]"
            >
              <Sparkles className="size-4 shrink-0 text-primary" />
              爸爸妈妈给你准备了一个故事：《{pushed.title}》
            </button>
          )}
        </div>
      )}

    </div>
  )
}
