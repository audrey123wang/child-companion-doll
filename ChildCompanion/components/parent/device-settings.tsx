'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { useAppStore } from '@/components/app-store'
import { PageHeader, Panel } from '@/components/parent/parts'
import { bindDevice, setButtonRecording } from '@/lib/api'
import { DEVICE } from '@/lib/mock-data'

export function DeviceSettings() {
  const { childId, profile, refreshData } = useAppStore()
  const [deviceId, setDeviceId] = useState('')
  const [busy, setBusy] = useState(false)
  const [keepAudio, setKeepAudio] = useState(false)
  const [retention, setRetention] = useState('30 天')
  useEffect(() => setDeviceId(profile?.device_id ?? ''), [profile?.device_id])

  async function bind() {
    setBusy(true)
    try { await bindDevice(childId, deviceId.trim()); await refreshData(); toast.success('设备已绑定') }
    catch (error) { toast.error(error instanceof Error ? error.message : '绑定失败') }
    finally { setBusy(false) }
  }
  async function toggle(enabled: boolean) {
    setBusy(true)
    try { await setButtonRecording(childId, enabled); await refreshData(); toast.success(enabled ? '已允许按键留言' : '已暂停按键留言') }
    catch (error) { toast.error(error instanceof Error ? error.message : '操作失败') }
    finally { setBusy(false) }
  }
  return <>
    <PageHeader title="设备与隐私" sub="娃娃设置与数据管理" />
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="绑定娃娃"><p className="mb-3 text-sm text-muted-foreground">USB 桥接终端会打印 Device ID for parent binding。</p>
        <label className="flex flex-col gap-2 text-sm font-semibold">设备 ID<input value={deviceId} onChange={(event) => setDeviceId(event.target.value)} placeholder="stickc-…" className="h-11 rounded-xl border border-input bg-background px-3 font-normal" /></label>
        <Button className="mt-3" disabled={!profile || !deviceId.trim() || busy} onClick={() => void bind()}>绑定设备</Button>
        <p className="mt-3 text-xs text-muted-foreground">{profile?.device_id ? `当前绑定：${profile.device_id}` : '尚未绑定；请先保存孩子档案。'}</p>
      </Panel>
      <Panel title="按键留言"><div className="flex items-center justify-between gap-4"><div><p className="font-semibold">允许娃娃按键录音</p><p className="text-sm text-muted-foreground">关闭后后端拒收新的按键留言。</p></div><Switch checked={profile?.button_recording_enabled ?? false} disabled={!profile?.device_id || busy} onCheckedChange={(enabled) => void toggle(enabled)} aria-label="允许娃娃按键录音" /></div>
        <p className="mt-4 rounded-xl bg-muted/60 p-3 text-xs text-muted-foreground">原始录音不写入数据库；当日逐字稿可供家长查看，次日清除正文。定时常开麦克风尚未由固件实现。</p>
      </Panel>
      <Panel title="设备状态"><dl className="grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-muted-foreground">设备名称</dt><dd className="font-semibold">{DEVICE.name}</dd></div>
        <div><dt className="text-muted-foreground">电量</dt><dd className="font-semibold">{DEVICE.battery}%</dd></div>
        <div><dt className="text-muted-foreground">型号</dt><dd className="font-semibold">{DEVICE.model}</dd></div>
        <div><dt className="text-muted-foreground">固件</dt><dd className="font-semibold">{DEVICE.firmware}</dd></div>
        <div><dt className="text-muted-foreground">最近同步</dt><dd className="font-semibold">{DEVICE.lastSync}</dd></div>
      </dl></Panel>
      <Panel title="隐私与数据"><div className="flex items-center justify-between gap-3 text-sm"><span>保存原始录音</span><Switch checked={keepAudio} onCheckedChange={setKeepAudio} aria-label="保存原始录音" /></div>
        <label className="mt-4 flex items-center justify-between text-sm">数据保存期限<select value={retention} onChange={(event) => setRetention(event.target.value)} className="rounded-lg border border-border bg-background px-2 py-1.5">{['7 天', '30 天', '90 天'].map((value) => <option key={value}>{value}</option>)}</select></label>
        <div className="mt-4 flex gap-2"><Button variant="outline" disabled>导出数据</Button><Button variant="destructive" disabled>删除今日数据</Button></div>
      </Panel>
    </div>
  </>
}
