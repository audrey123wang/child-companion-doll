'use client'

import { useEffect, useRef, useState } from 'react'
import { Mic, Square, Volume2 } from 'lucide-react'
import { useAppStore } from '@/components/app-store'
import { Character } from '@/components/kid/character'
import { STORIES } from '@/lib/mock-data'
import { chatSpeech, chatTurn, stopStorySession, transcribe } from '@/lib/api'
import { startRecording, type RecordingHandle } from '@/lib/recording'

type Message = { id: number; from: 'kid' | 'pal'; text: string; support?: boolean }

export function KidChat({ storyId }: { storyId?: string }) {
  const { animal, childId, goKid } = useAppStore()
  const story = storyId ? STORIES.find((item) => item.id === storyId) : undefined
  const [messages, setMessages] = useState<Message[]>([{ id: 0, from: 'pal', text: story ? `刚才的《${story.title}》好听吗？你想聊聊朋友之间的事吗？` : '你好呀，想和我聊聊今天和朋友相处的事吗？' }])
  const [draft, setDraft] = useState('')
  const [recording, setRecording] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [voiceUrl, setVoiceUrl] = useState<string | null>(null)
  const [finished, setFinished] = useState(false)
  const recorder = useRef<RecordingHandle | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const audio = useRef<HTMLAudioElement | null>(null)
  const list = useRef<HTMLDivElement | null>(null)
  const nextId = useRef(1)

  useEffect(() => { list.current?.scrollTo({ top: list.current.scrollHeight, behavior: 'smooth' }) }, [messages])
  useEffect(() => () => {
    recorder.current?.cancel()
    if (timer.current) clearTimeout(timer.current)
    audio.current?.pause()
    if (audio.current?.src.startsWith('blob:')) URL.revokeObjectURL(audio.current.src)
  }, [])

  function add(from: 'kid' | 'pal', text: string, support = false) {
    setMessages((items) => [...items, { id: nextId.current++, from, text, support }])
  }
  async function stopAndTranscribe() {
    if (!recorder.current) return
    if (timer.current) clearTimeout(timer.current)
    const current = recorder.current
    recorder.current = null
    setRecording(false)
    setBusy(true)
    setError(null)
    try { setDraft(await transcribe(await current.stop(), childId)) }
    catch (cause) { setError(cause instanceof Error ? cause.message : '录音识别失败') }
    finally { setBusy(false) }
  }
  async function toggleRecording() {
    if (recording) { await stopAndTranscribe(); return }
    setError(null); setDraft('')
    try {
      recorder.current = await startRecording()
      setRecording(true)
      timer.current = setTimeout(() => void stopAndTranscribe(), 12000)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '麦克风不可用') }
  }
  async function send(text: string) {
    const value = text.trim()
    if (!value || busy) return
    setBusy(true); setError(null); setDraft('')
    add('kid', value)
    try {
      const turn = await chatTurn(childId, value, sessionId)
      setSessionId(turn.session_id)
      setFinished(turn.route !== 'conversation')
      add('pal', turn.reply_text, turn.route === 'support')
      if (turn.tts_status === 'pending') {
        try {
          const mp3 = await chatSpeech(childId, turn.reply_id)
          if (audio.current?.src.startsWith('blob:')) URL.revokeObjectURL(audio.current.src)
          const url = URL.createObjectURL(mp3)
          setVoiceUrl(url)
          const player = new Audio(url)
          audio.current = player
          await player.play()
        } catch { setError('文字回答已显示；语音播放失败，可点“播放回答”重试。') }
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : '问答服务暂不可用') }
    finally { setBusy(false) }
  }
  function replay() {
    if (!voiceUrl) return
    if (audio.current) { audio.current.currentTime = 0; void audio.current.play().catch(() => setError('浏览器阻止了播放，请再点一次。')) }
  }
  function exit() {
    recorder.current?.cancel()
    if (sessionId) void stopStorySession(childId, sessionId).catch(() => {})
    goKid({ name: 'home' })
  }
  return <div className="flex h-full flex-col gap-4 px-6 pb-5 pt-2 sm:flex-row sm:gap-8">
    <aside className="flex shrink-0 flex-row items-center gap-4 sm:w-72 sm:flex-col sm:justify-center"><Character animal={animal} state={recording ? 'listening' : busy ? 'thinking' : 'welcome'} className="w-32 sm:w-full" /><p className="text-sm text-muted-foreground">我会先显示你说的话，再告诉你我的回答。</p></aside>
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-[2rem] bg-card shadow-sm">
      <div ref={list} className="flex flex-1 flex-col gap-4 overflow-y-auto p-6" aria-live="polite">
        {messages.map((message) => <div key={message.id} className={`flex ${message.from === 'kid' ? 'justify-end' : 'justify-start'}`}><p className={`max-w-[85%] rounded-3xl px-5 py-3 text-lg leading-relaxed ${message.from === 'kid' ? 'text-white' : message.support ? 'bg-primary/10' : 'bg-muted'}`} style={message.from === 'kid' ? { backgroundColor: animal.color } : undefined}>{message.text}</p></div>)}
        {busy && <p className="w-fit rounded-3xl bg-muted px-5 py-3 text-sm text-muted-foreground">{animal.name}正在处理…</p>}
      </div>
      <div className="border-t border-border p-4">
        {error && <p role="alert" className="mb-3 rounded-xl bg-destructive/10 p-3 text-sm">{error}</p>}
        {draft && <div className="mb-3 space-y-2"><label className="block text-sm font-semibold" htmlFor="asr-draft">我听到你说（可以修改）</label><textarea id="asr-draft" value={draft} maxLength={300} onChange={(event) => setDraft(event.target.value)} className="min-h-20 w-full rounded-xl border border-input bg-background p-3 text-base" /><div className="flex gap-2"><button type="button" disabled={busy || !draft.trim()} onClick={() => void send(draft)} className="rounded-xl bg-primary px-5 py-2 font-semibold text-primary-foreground disabled:opacity-50">发送给{animal.name}</button><button type="button" onClick={() => setDraft('')} className="rounded-xl bg-muted px-4 py-2">重录</button></div></div>}
        <div className="flex items-center gap-3"><button type="button" onClick={exit} className="rounded-full bg-muted px-4 py-3 text-sm font-semibold">结束</button><button type="button" onClick={() => void toggleRecording()} disabled={busy || finished} className="flex h-16 min-w-0 flex-1 items-center justify-center gap-2 rounded-full font-display text-xl text-white disabled:opacity-50" style={{ backgroundColor: animal.color }}>{recording ? <Square className="size-6" /> : <Mic className="size-7" />}{recording ? '点我结束录音' : '点我说话'}</button>{voiceUrl && <button type="button" onClick={replay} aria-label="播放回答" className="rounded-full bg-muted p-3"><Volume2 className="size-6" /></button>}</div>
        <p className="mt-2 text-center text-xs text-muted-foreground">最长 12 秒 · 声音由 AI 生成 · 对话仅留在当前会话</p>
      </div>
    </section>
  </div>
}
