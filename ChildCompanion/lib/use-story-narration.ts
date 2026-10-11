'use client'

import { useEffect, useRef, useState } from 'react'
import { storyNarration } from '@/lib/api'

export function useStoryNarration(
  childId: string,
  storyId: string,
  page: number,
  text: string,
  onEnded: () => void,
  options?: { recordingUrl?: string; autoPlay?: boolean; initialAudio?: HTMLAudioElement | null },
) {
  const recordingUrl = options?.recordingUrl
  const initialAudio = options?.initialAudio
  const [started, setStarted] = useState(options?.autoPlay ?? false)
  const [paused, setPaused] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const audio = useRef<HTMLAudioElement | null>(null)
  const url = useRef<string | null>(null)
  const initialAudioUsed = useRef(false)
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
    setPlaying(false)
    setLoading(!recordingUrl); setError(null)

    const useAudio = (source: string | HTMLAudioElement) => {
      if (cancelled) return
      const player = typeof source === 'string' ? new Audio(source) : source
      audio.current = player
      player.onplay = () => setPlaying(true)
      player.onpause = () => setPlaying(false)
      player.onended = () => { setPlaying(false); endedRef.current() }
      player.onerror = () => setError('故事录音无法播放，请重试。')
      setPlaying(!player.paused)
      if (!pausedRef.current && player.paused) void player.play().catch(() => {
        if (!cancelled) setError('浏览器阻止了自动播放，请点播放按钮。')
      })
    }

    if (recordingUrl) {
      if (!initialAudioUsed.current && initialAudio?.src.endsWith(recordingUrl)) {
        initialAudioUsed.current = true
        useAudio(initialAudio)
      } else {
        useAudio(recordingUrl)
      }
    } else {
      void storyNarration(childId, storyId, page, text).then((blob) => {
        if (cancelled) return
        url.current = URL.createObjectURL(blob)
        useAudio(url.current)
      }).catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : '故事配音失败')
      }).finally(() => { if (!cancelled) setLoading(false) })
    }
    return () => {
      cancelled = true
      audio.current?.pause()
      audio.current = null
      if (url.current) { URL.revokeObjectURL(url.current); url.current = null }
    }
  }, [childId, storyId, page, text, started, recordingUrl, initialAudio])

  function play() {
    if (!started) { setStarted(true); setPaused(false); return }
    setPaused(false)
    if (audio.current) void audio.current.play().catch(() => setError('无法播放语音，请重试。'))
  }
  function pause() { setPaused(true); audio.current?.pause() }
  function stop() { setStarted(false); setPaused(false); audio.current?.pause() }
  return { playing, started, loading, error, play, pause, stop }
}
