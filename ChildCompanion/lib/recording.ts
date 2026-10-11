/** Browser microphone → 16 kHz mono PCM16 WAV, kept only in memory. */
export type RecordingHandle = { stop: () => Promise<Blob>; cancel: () => void }

export async function startRecording(): Promise<RecordingHandle> {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('当前浏览器无法使用麦克风；请使用 HTTPS 或本机地址。')
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
  const context = new AudioContext()
  await context.resume()
  const source = context.createMediaStreamSource(stream)
  const processor = context.createScriptProcessor(4096, 1, 1)
  const chunks: Float32Array[] = []
  processor.onaudioprocess = (event) => chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)))
  source.connect(processor)
  processor.connect(context.destination)
  let closed = false
  function close() {
    if (closed) return false
    closed = true
    processor.onaudioprocess = null
    processor.disconnect()
    source.disconnect()
    stream.getTracks().forEach((track) => track.stop())
    void context.close()
    return true
  }
  return {
    cancel: () => { close() },
    stop: async () => {
      if (!close()) throw new Error('录音已结束')
      const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
      const duration = length / context.sampleRate
      if (duration < 0.3) throw new Error('录音太短，请说完后再按一次。')
      if (duration > 15.5) throw new Error('录音超过 15 秒，请缩短后重试。')
      const samples = new Float32Array(length)
      let offset = 0
      for (const chunk of chunks) { samples.set(chunk, offset); offset += chunk.length }
      const targetLength = Math.round(length * 16000 / context.sampleRate)
      const buffer = new ArrayBuffer(44 + targetLength * 2)
      const view = new DataView(buffer)
      const ascii = (at: number, value: string) => { for (let i = 0; i < value.length; i++) view.setUint8(at + i, value.charCodeAt(i)) }
      ascii(0, 'RIFF'); view.setUint32(4, buffer.byteLength - 8, true); ascii(8, 'WAVE')
      ascii(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true)
      view.setUint16(22, 1, true); view.setUint32(24, 16000, true); view.setUint32(28, 32000, true)
      view.setUint16(32, 2, true); view.setUint16(34, 16, true); ascii(36, 'data')
      view.setUint32(40, targetLength * 2, true)
      for (let i = 0; i < targetLength; i++) {
        const position = i * context.sampleRate / 16000
        const left = Math.min(samples.length - 1, Math.floor(position))
        const fraction = position - left
        const sample = Math.max(-1, Math.min(1, samples[left] * (1 - fraction) + samples[Math.min(left + 1, samples.length - 1)] * fraction))
        view.setInt16(44 + i * 2, Math.round(sample < 0 ? sample * 32768 : sample * 32767), true)
      }
      return new Blob([buffer], { type: 'audio/wav' })
    },
  }
}
