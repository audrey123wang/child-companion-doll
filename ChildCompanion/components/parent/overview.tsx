'use client'

import { ArrowRight, Info, RefreshCw } from 'lucide-react'
import { useAppStore } from '@/components/app-store'
import { EmotionBar, Legend, PageHeader, Panel, Stat } from '@/components/parent/parts'
import { TODAY_SUMMARY } from '@/lib/mock-data'

export function Overview() {
  const { setParentTab, today, inputs, report, profile, dataError, dataLoading, refreshData } = useAppStore()
  const status = !profile ? '请先设置孩子档案' : report?.status === 'pending' ? '19:00 后生成' : report?.status === 'ready' ? '已生成' : '信息不足'
  return (
    <>
      <PageHeader title="今日概览" sub={today ? `${today.date} · 日报${status}` : status} action={
        <button type="button" onClick={() => void refreshData()} className="flex items-center gap-2 rounded-full bg-card px-4 py-2 text-sm font-semibold">
          <RefreshCw className="size-4" /> 刷新
        </button>
      } />
      {dataError && <p role="alert" className="mb-4 rounded-2xl bg-destructive/10 p-4 text-sm">后端连接失败：{dataError}</p>}
      {dataLoading && <p className="mb-4 text-sm text-muted-foreground">正在读取今日记录…</p>}
      {!profile && !dataLoading && <button type="button" onClick={() => setParentTab('profile')} className="mb-4 rounded-2xl bg-secondary p-4 text-sm font-semibold">先设置孩子档案 <ArrowRight className="inline size-4" /></button>}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="按键留言" value={today?.active_input_count ?? 0} unit="条" />
        <Stat label="同伴事件" value={today?.peer_event_count ?? 0} unit="条" />
        <Stat label="未听清" value={today?.unreadable_input_count ?? 0} unit="条" />
        <Stat label="未归类" value={today?.unclassified_input_count ?? 0} unit="条" />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Panel title="今日情绪"><EmotionBar mix={TODAY_SUMMARY.mood} className="h-6" /><div className="mt-3"><Legend emotions={TODAY_SUMMARY.mood.map((item) => item.emotion)} /></div></Panel>
        <Panel title="孩子今天主动说的话" action={<button type="button" className="flex items-center gap-1 text-sm font-semibold text-primary" onClick={() => setParentTab('daily')}>查看日报 <ArrowRight className="size-4" /></button>}>
          {inputs.length === 0 ? <p className="text-sm text-muted-foreground">今天还没有收到按键留言。</p> : (
            <ul className="flex flex-col gap-3">
              {inputs.slice(-3).reverse().map((input) => <li key={`${input.device_id}/${input.segment_id}`} className="rounded-2xl bg-muted/60 p-3 text-sm">
                <span className="font-semibold">{new Date(input.received_at).toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit' })}</span>
                <p className="mt-1">{input.transcript ?? (input.status === 'unreadable' ? '录音未听清' : '逐字稿已过期')}</p>
                {input.summary && <p className="mt-1 text-muted-foreground">{input.summary}</p>}
              </li>)}
            </ul>
          )}
        </Panel>
        <Panel title="今晚可以聊聊">
          {report?.status === 'ready' && report.parent_prompts.length > 0 ? (
            <ul className="flex flex-col gap-3 text-sm">{report.parent_prompts.slice(0, 3).map((prompt) => <li key={prompt} className="rounded-xl bg-secondary/40 p-3">{prompt}</li>)}</ul>
          ) : <p className="text-sm text-muted-foreground">{report?.status === 'pending' ? '今晚 19:00 后生成建议。' : '暂无足够的同伴相处信息，暂不生成建议。'}</p>}
        </Panel>
      </div>
      <p className="mt-4 flex gap-2 text-xs text-muted-foreground"><Info className="size-4 shrink-0" />{today?.coverage_note ?? '仅依据孩子主动按键留言，不能代表全天情况。'}</p>
    </>
  )
}
