'use client'

import { useState } from 'react'
import Image from 'next/image'
import { Check, Info, PencilLine, RefreshCw, Send } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { useAppStore } from '@/components/app-store'
import { EmotionBar, Legend, PageHeader, Panel } from '@/components/parent/parts'
import { STORIES, TODAY_SUMMARY } from '@/lib/mock-data'
import { correctInput, generateDailyReport, type ParentInput } from '@/lib/api'

export function DailyReport() {
  const { childId, profile, today, inputs, report, applyReport, pushedStories, pushStory, refreshData, dataError } = useAppStore()
  const [generating, setGenerating] = useState(false)
  async function generateNow() {
    if (!profile || generating) return
    setGenerating(true)
    try {
      const generated = await generateDailyReport(childId)
      applyReport(generated)
      void refreshData()
      toast.success(generated.status === 'ready' ? '今日报告已生成' : '已生成报告：今天的信息还不足以总结同伴相处情况')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '生成报告失败')
    } finally {
      setGenerating(false)
    }
  }
  const recommended = report?.status === 'ready' && report.story_topic === 'friendship_and_inclusion'
    ? STORIES.find((story) => story.id === 's2') : undefined
  return (
    <>
      <PageHeader
        title="今日日报"
        sub={`${today?.date ?? '今日'} · ${report?.status === 'pending' ? '待生成' : report?.status === 'ready' ? '已生成' : '信息不足'}`}
        action={<Button onClick={() => void generateNow()} disabled={!profile || generating}>
          <RefreshCw className={generating ? 'animate-spin' : ''} />
          {generating ? '正在生成…' : report?.status === 'pending' ? '立即生成今日报告' : '重新生成今日报告'}
        </Button>}
      />
      {dataError && <p role="alert" className="mb-4 rounded-2xl bg-destructive/10 p-4 text-sm">后端连接失败：{dataError}</p>}
      <div className="mb-4 flex items-start gap-3 rounded-2xl bg-muted/70 p-4 text-sm"><Info className="mt-0.5 size-4 shrink-0" /><p>{report?.status === 'pending' ? '可随时手动生成；未手动生成时，今晚 19:00 自动生成。' : report?.status === 'ready' || report?.status === 'insufficient' ? report.coverage_note : '请先设置孩子档案并连接本地后端。'}原始录音不存储；当日可查看 ASR 文字。</p></div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <Panel title="情绪分布"><EmotionBar mix={TODAY_SUMMARY.mood} className="h-6" /><div className="mt-3"><Legend emotions={TODAY_SUMMARY.mood.map((item) => item.emotion)} /></div></Panel>
          <Panel title="孩子今天主动说的话" action={<span className="text-xs text-muted-foreground">{inputs.length} 条</span>}>
            {inputs.length === 0 ? <p className="text-sm text-muted-foreground">今天还没有收到按键留言。</p> : <ul className="flex flex-col gap-3">{inputs.map((input) => <InputItem key={`${input.device_id}/${input.segment_id}`} input={input} childId={childId} onSaved={refreshData} />)}</ul>}
          </Panel>
          <Panel title="报告观察" action={report?.status === 'ready' ? <span className="text-xs text-muted-foreground">版本 {report.revision}</span> : undefined}>
            {report?.status === 'ready' ? <ul className="flex flex-col gap-3">{report.observations.map((item, index) => <li key={`${item.event_ids.join('-')}-${index}`} className="rounded-xl bg-secondary/40 p-3 text-sm">{item.text}<span className="mt-1 block text-xs text-muted-foreground">依据事件：{item.event_ids.join('、')}</span></li>)}</ul> : <p className="text-sm text-muted-foreground">{report?.status === 'pending' ? '点击上方按钮，立即生成今日报告。' : '目前没有足够的同伴相处信息。'}</p>}
          </Panel>
          {report?.status !== 'pending' && report && <Panel title="主要问题与家长引导">
            {report.main_issue ? <div className="space-y-3 text-sm">
              <p><span className="font-semibold">从留言看，孩子主要遇到：</span>{report.main_issue.problem}</p>
              <p><span className="font-semibold">家长可以这样引导：</span>{report.main_issue.guidance}</p>
            </div> : <p className="text-sm text-muted-foreground">今天还没有足够的同伴相处留言，暂时无法总结主要问题；可以先听孩子说说今天的经历。</p>}
          </Panel>}
        </div>
        <div className="flex flex-col gap-4">
          <Panel title="建议家长怎么聊">
            {report?.status === 'ready' && report.parent_prompts.length ? <ol className="flex flex-col gap-3">{report.parent_prompts.map((question, index) => <li key={question} className="flex gap-3 text-sm"><span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-bold">{index + 1}</span>{question}</li>)}</ol> : <p className="text-sm text-muted-foreground">报告生成后显示基于今日留言的沟通建议。</p>}
          </Panel>
          {recommended && <Panel title="相关故事（本地故事库）"><div className="flex items-center gap-3"><div className="relative size-14 shrink-0 overflow-hidden rounded-xl"><Image src={recommended.cover} alt="" fill sizes="56px" className="object-cover" /></div><div className="min-w-0 flex-1"><p className="font-semibold">{recommended.title}</p><p className="text-xs text-muted-foreground">{recommended.tags.join(' · ')}</p></div><Button size="sm" disabled={pushedStories.includes(recommended.id)} onClick={() => { pushStory(recommended.id); toast.success('已在当前 App 会话中加入儿童端') }}>{pushedStories.includes(recommended.id) ? <Check /> : <Send />}{pushedStories.includes(recommended.id) ? '已加入' : '加入'}</Button></div></Panel>}
        </div>
      </div>
    </>
  )
}

function InputItem({ input, childId, onSaved }: { input: ParentInput; childId: string; onSaved: () => Promise<void> }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(input.transcript ?? '')
  const [busy, setBusy] = useState(false)
  const time = new Date(input.received_at).toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit' })
  async function save() {
    setBusy(true)
    try { await correctInput(input, childId, text); await onSaved(); setEditing(false); toast.success('已更正转写并重新计算报告') }
    catch (error) { toast.error(error instanceof Error ? error.message : '更正失败') }
    finally { setBusy(false) }
  }
  return <li className="rounded-2xl border border-border p-4 text-sm"><div className="flex items-center justify-between"><span className="font-semibold">{time} · 娃娃按键留言</span><span className="text-xs text-muted-foreground">{input.status === 'unreadable' ? '未听清' : input.summary ? '同伴相处' : '未归类'}</span></div>
    {editing ? <div className="mt-3 flex flex-col gap-2"><textarea value={text} onChange={(event) => setText(event.target.value)} maxLength={500} className="min-h-20 rounded-xl border border-input bg-background p-2" /><div className="flex gap-2"><Button size="sm" disabled={busy || !text.trim()} onClick={() => void save()}>保存更正</Button><Button size="sm" variant="ghost" onClick={() => setEditing(false)}>取消</Button></div></div> : <><p className="mt-2">{input.transcript ?? (input.status === 'unreadable' ? '这段录音未听清。' : '逐字稿已过期。')}</p>{input.summary && <p className="mt-2 text-muted-foreground">事件摘要：{input.summary}</p>}{input.transcript && <button type="button" className="mt-2 flex items-center gap-1 text-xs text-primary" onClick={() => setEditing(true)}><PencilLine className="size-3" /> 更正转写</button>}</>}
  </li>
}
