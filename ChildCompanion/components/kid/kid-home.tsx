'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { BookOpen, Sparkles, Volume2 } from 'lucide-react'
import { useAppStore } from '@/components/app-store'
import { CharacterSpeechBubble } from '@/components/kid/character-speech-bubble'
import { CompanionSwitcher } from '@/components/kid/companion-switcher'
import { QuickChoices } from '@/components/kid/quick-choices'
import { RabbitCharacter } from '@/components/kid/rabbit-character'
import { StoryReader } from '@/components/kid/story-reader'
import { VoiceButton } from '@/components/kid/voice-button'
import { chatSpeech, homeChatTurn, stopStorySession, transcribe } from '@/lib/api'
import { RABBIT_IMAGES, STORIES, type RabbitState } from '@/lib/mock-data'
import { startRecording, type RecordingHandle } from '@/lib/recording'
import { FRIENDSHIP_STORY } from '@/lib/story-friendship'
import { cn } from '@/lib/utils'

/**
 * 单页 AI 陪伴体验 · 主状态机
 *
 * CompanionMode 控制「当前页面大场景」，RabbitState 控制「兔子当前状态」。
 * 两者是正交的：例如 storyReflection 场景下兔子可以是 speaking。
 *
 * 首页负责角色、故事入口和原位录音问答。
 */
type CompanionMode = 'companion' | 'story' | 'storyReflection'

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
  speaking: 2500,
} as const

export function KidHome() {
  const { animal, childId, goKid, pushedStories } = useAppStore()

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
  const [recording, setRecording] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasReplyAudio, setHasReplyAudio] = useState(false)
  const recorder = useRef<RecordingHandle | null>(null)
  const recordTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const replyAudio = useRef<HTMLAudioElement | null>(null)
  const storyAudio = useRef<HTMLAudioElement | null>(null)
  const replyAudioUrl = useRef<string | null>(null)
  const sessionId = useRef<string | null>(null)

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

  useEffect(() => () => {
    clearTimers()
    recorder.current?.cancel()
    if (recordTimer.current) clearTimeout(recordTimer.current)
    replyAudio.current?.pause()
    storyAudio.current?.pause()
    if (replyAudioUrl.current) URL.revokeObjectURL(replyAudioUrl.current)
    if (sessionId.current) void stopStorySession(childId, sessionId.current).catch(() => {})
  }, [childId, clearTimers])

  // welcome → idle
  useEffect(() => {
    if (mode !== 'companion' || state !== 'welcome') return
    const t = setTimeout(() => {
      setState('idle')
    }, TIMING.welcome)
    timers.current.push(t)
    return () => clearTimeout(t)
  }, [state, mode])

  // 回复显示一段时间后，角色恢复待命；气泡文字仍保留最后一条回复。
  useEffect(() => {
    if (state === 'speaking' && mode === 'companion') {
      const t = setTimeout(() => setState('idle'), TIMING.speaking)
      timers.current.push(t)
      return () => clearTimeout(t)
    }
    return undefined
  }, [state, mode])

  async function stopAndTranscribe() {
    const current = recorder.current
    if (!current) return
    recorder.current = null
    if (recordTimer.current) clearTimeout(recordTimer.current)
    recordTimer.current = null
    setRecording(false)
    setBusy(true)
    setState('thinking')
    try {
      const heard = await transcribe(await current.stop(), childId)
      const text = heard.trim()
      if (!text) throw new Error('没有听清楚，请再说一次。')
      await sendMessage(text)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '语音发送失败，请再试一次。')
      setState('idle')
    } finally {
      setBusy(false)
    }
  }

  async function onVoice() {
    if (recording) { await stopAndTranscribe(); return }
    if (busy) return
    setError(null)
    setSpeech(null)
    replyAudio.current?.pause()
    setHasReplyAudio(false)
    setBusy(true)
    try {
      recorder.current = await startRecording()
      setRecording(true)
      setState('listening')
      recordTimer.current = setTimeout(() => void stopAndTranscribe(), 12000)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '麦克风不可用')
      setState('idle')
    } finally {
      setBusy(false)
    }
  }

  async function sendMessage(text: string) {
    setError(null)
    setState('thinking')
    const turn = await homeChatTurn(childId, text, sessionId.current)
    sessionId.current = turn.route === 'conversation' ? turn.session_id : null
    setSpeech(turn.reply_text)
    setState('speaking')
    setHasReplyAudio(false)
    if (replyAudio.current) replyAudio.current.pause()
    if (replyAudioUrl.current) URL.revokeObjectURL(replyAudioUrl.current)
    replyAudioUrl.current = null
    if (turn.tts_status === 'pending') {
      try {
        const mp3 = await chatSpeech(childId, turn.reply_id)
        const url = URL.createObjectURL(mp3)
        replyAudioUrl.current = url
        setHasReplyAudio(true)
        const player = new Audio(url)
        replyAudio.current = player
        await player.play()
      } catch {
        setError('文字回答已显示；语音播放失败，可点播放按钮重试。')
      }
    }
  }

  function replayReply() {
    if (!replyAudio.current) return
    replyAudio.current.currentTime = 0
    void replyAudio.current.play().catch(() => setError('浏览器阻止了播放，请再点一次。'))
  }

  function onPick(label: string) {
    if (label === '听故事') enterStory()
    if (label === '聊一聊') void onVoice()
  }

  // ── 进入故事模式：在点击时立即挂载播放器，以便自动播放 ────
  function enterStory() {
    replyAudio.current?.pause()
    clearTimers()
    setChoices([])
    storyAudio.current?.pause()
    const firstScene = new Audio(FRIENDSHIP_STORY.scenes[0].audio)
    storyAudio.current = firstScene
    void firstScene.play().catch(() => {})
    setMode('story')
    setState('idle')
    setStageFading(false)
  }

  function returnToConversation() {
    clearTimers()
    storyAudio.current?.pause()
    storyAudio.current = null
    setMode('companion')
    setStageFading(false)
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
          <StoryReader story={FRIENDSHIP_STORY} onFinish={onStoryFinish} onBack={returnToConversation} initialAudio={storyAudio.current} />
        </div>
      ) : (
        /* ── 陪伴 / 反思场景 ───────────────────────────── */
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
            className="w-[70%] max-w-[28rem] sm:w-[60%] lg:w-[50%]"
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

          <VoiceButton listening={recording} disabled={busy} onClick={() => void onVoice()} />
          {hasReplyAudio && <button type="button" onClick={replayReply} className="flex items-center gap-2 rounded-full bg-card px-5 py-2 text-sm font-semibold shadow-sm"><Volume2 className="size-4" />再听一遍回答</button>}
          {error && <p role="alert" className="max-w-md rounded-2xl bg-destructive/10 px-4 py-2 text-center text-sm">{error}</p>}
          <button
            type="button"
            onClick={enterStory}
            disabled={recording || busy}
            className="mt-1 flex items-center gap-2 rounded-full bg-card px-7 py-3 font-display text-lg font-semibold text-foreground shadow-sm transition hover:shadow-md active:scale-[0.98] disabled:opacity-50"
          >
            <BookOpen className="size-6 text-primary" />
            讲故事
          </button>

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
