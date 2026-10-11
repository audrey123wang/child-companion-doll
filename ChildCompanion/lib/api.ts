/** Typed client for the local Next.js → FastAPI proxy. No credentials enter the browser. */
export const STORY_AGENT_ID = 'mimi-new-game-circle-v1'

export type ChildProfile = {
  child_id: string
  age: number
  school_stage: string
  listening_start: string | null
  listening_end: string | null
  scheduled_listening_status: 'configuration_only'
  button_recording_enabled: boolean
  device_id: string | null
}
export type ParentToday = {
  date: string
  active_input_count: number
  unreadable_input_count: number
  unclassified_input_count: number
  peer_event_count: number
  report_status: 'pending' | 'ready' | 'insufficient'
  report_revision: number
  coverage_note: string
}
export type ParentInput = {
  segment_id: string
  device_id: string
  status: string
  event_id: string | null
  transcript: string | null
  transcript_revision: number
  received_at: string
  summary: string | null
}
export type DailyReport =
  | { date: string; status: 'pending'; revision: number }
  | {
      date: string; status: 'ready' | 'insufficient'; revision: number
      observations: { text: string; event_ids: string[] }[]
      main_issue: { problem: string; guidance: string; event_ids: string[] } | null
      unknowns: string[]; parent_prompts: string[]; story_topic: string | null
      event_count: number; coverage_note: string
      input_counts: { input_count: number; understood_count: number; unclassified_count: number; unreadable_count: number }
    }
export type ChatReply = {
  session_id: string | null; turn_number: number; route: 'conversation' | 'stopped' | 'support'
  reply_text: string; reply_id: string; tts_status: 'pending' | 'not_configured' | 'ready' | 'failed'
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

function url(path: string) { return `/api/backend${path}` }

async function checked(response: Response) {
  if (response.ok) return response
  let detail = `请求失败 (${response.status})`
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') detail = body.detail
  } catch { /* keep status */ }
  throw new ApiError(response.status, detail)
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await checked(await fetch(url(path), { ...init, cache: 'no-store' }))
  return response.json() as Promise<T>
}

const query = (values: Record<string, string>) => new URLSearchParams(values).toString()
const payload = (value: unknown) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) })

export async function getProfile(): Promise<ChildProfile | null> {
  try { return await json<ChildProfile>('/v1/parent/profile') }
  catch (error) { if (error instanceof ApiError && error.status === 404) return null; throw error }
}
export function saveProfile(profile: { child_id: string; age: number; school_stage: string; listening_start: string | null; listening_end: string | null }) {
  return json<ChildProfile>('/v1/parent/profile', { ...payload(profile), method: 'PUT' })
}
export function setButtonRecording(child_id: string, enabled: boolean) {
  return json<ChildProfile>('/v1/parent/button-recording', { ...payload({ child_id, enabled }), method: 'PUT' })
}
export function bindDevice(child_id: string, device_id: string) {
  return json<ChildProfile>('/v1/parent/device-binding', { ...payload({ child_id, device_id }), method: 'PUT' })
}
export function getToday(childId: string) {
  return json<ParentToday>(`/v1/parent/today?${query({ child_id: childId })}`)
}
export async function getInputs(childId: string, date: string) {
  const body = await json<{ items: ParentInput[] }>(`/v1/parent/inputs?${query({ child_id: childId, date })}`)
  return body.items
}
export function getDailyReport(childId: string, date: string) {
  return json<DailyReport>(`/v1/parent/reports/daily?${query({ child_id: childId, date })}`)
}
export function generateDailyReport(childId: string) {
  return json<Extract<DailyReport, { status: 'ready' | 'insufficient' }>>(
    '/v1/parent/reports/daily/generate', payload({ child_id: childId }),
  )
}
export function correctInput(input: ParentInput, childId: string, text: string) {
  return json(`/v1/parent/inputs/${encodeURIComponent(input.device_id)}/${encodeURIComponent(input.segment_id)}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ child_id: childId, text, expected_revision: input.transcript_revision }),
  })
}
export function deleteInput(input: ParentInput, childId: string) {
  return json(`/v1/parent/inputs/${encodeURIComponent(input.device_id)}/${encodeURIComponent(input.segment_id)}?${query({ child_id: childId, expected_revision: String(input.transcript_revision) })}`, { method: 'DELETE' })
}
export async function transcribe(audio: Blob, childId: string): Promise<string> {
  const response = await checked(await fetch(url('/v1/child/chat-turns/transcribe'), {
    method: 'POST', headers: { 'Content-Type': 'audio/wav', 'X-Child-ID': childId }, body: audio,
  }))
  const body = await response.json() as { heard_text: string }
  return body.heard_text
}
export function chatTurn(childId: string, text: string, sessionId: string | null) {
  return json<ChatReply>('/v1/child/chat-turns', payload({
    child_id: childId, story_id: STORY_AGENT_ID, text, session_id: sessionId,
  }))
}
export function homeChatTurn(childId: string, text: string, sessionId: string | null) {
  return json<ChatReply>('/v1/child/conversations/turns', payload({
    child_id: childId, text, session_id: sessionId,
  }))
}
export async function chatSpeech(childId: string, replyId: string): Promise<Blob> {
  const response = await checked(await fetch(url(`/v1/child/chat-turns/${encodeURIComponent(replyId)}/speech?${query({ child_id: childId })}`), { method: 'POST' }))
  return response.blob()
}
export async function storyNarration(childId: string, storyId: string, page: number, text: string): Promise<Blob> {
  const response = await checked(await fetch(url('/v1/child/story-narration'), payload({ child_id: childId, story_id: storyId, page, text })))
  return response.blob()
}
export function stopStorySession(childId: string, sessionId: string) {
  return json(`/v1/child/story-sessions/${encodeURIComponent(sessionId)}?${query({ child_id: childId })}`, { method: 'DELETE' })
}
