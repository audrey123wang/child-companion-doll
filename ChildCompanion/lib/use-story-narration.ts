'use client'

import { useEffect, useRef, useState } from 'react'
import { storyNarration } from '@/lib/api'

export function useStoryNarration(childId: string, storyId: string, page: number, text: string, onEnded: () => void) {
  const [started, setStarted] = useState(false)
  const [paused, setPaused] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const audio = useRef<HTMLAudioElement | null>(null)
  const url = useRef<string | null>(null)
  const pausedRef = useRef(paused)
  const endedRef = useRef(onEnded)
  pausedRef.current = paused
  endedRef.current = onEnded

  useEffect(() => {
    if (!started) return
    let cancelled = false
    audio.current?.pause()
    audio.current = null
    if (url.current) { URL.revokeObjectURL(url.current); url.current = null }
    setLoading(true); setError(null)
    void storyNarration(childId, storyId, page, text).then((blob) => {
      if (cancelled) return
      url.current = URL.createObjectURL(blob)
      const player = new Audio(url.current)
      audio.current = player
      player.onended = () => endedRef.current()
      if (!pausedRef.current) void player.play().catch(() => setError('浏览器阻止了自动播放，请点播放按钮。'))
    }).catch((cause) => {
      if (!cancelled) setError(cause instanceof Error ? cause.message : '故事配音失败')
    }).finally(() => { if (!cancelled) setLoading(false) })
    return () => {
      cancelled = true
      audio.current?.pause()
      audio.current = null
      if (url.current) { URL.revokeObjectURL(url.current); url.current = null }
    }
  }, [childId, storyId, page, text, started])

  function play() {
    if (!started) { setStarted(true); setPaused(false); return }
    setPaused(false)
    if (audio.current) void audio.current.play().catch(() => setError('无法播放语音，请重试。'))
  }
  function pause() { setPaused(true); audio.current?.pause() }
  function stop() { setStarted(false); setPaused(false); audio.current?.pause() }
  return { playing: started && !paused, started, loading, error, play, pause, stop }
}
