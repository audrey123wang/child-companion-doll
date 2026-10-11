'use client'

import { useEffect, useState } from 'react'
import Image from 'next/image'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { useAppStore } from '@/components/app-store'
import { PageHeader, Panel } from '@/components/parent/parts'
import { ANIMALS, CHILD_PROFILE } from '@/lib/mock-data'
import { cn } from '@/lib/utils'
import { saveProfile } from '@/lib/api'

const PREFS = ['动物', '太空', '友谊', '恐龙', '公主', '自然', '科学', '交通工具']

export function ProfileSettings() {
  const { animalId, setAnimalId, childId, profile, refreshData } = useAppStore()
  const [nickname, setNickname] = useState(CHILD_PROFILE.nickname)
  const [age, setAge] = useState(CHILD_PROFILE.age)
  const [prefs, setPrefs] = useState<string[]>(CHILD_PROFILE.preferences)
  const [limit, setLimit] = useState(CHILD_PROFILE.storyLimit)
  const [schoolStage, setSchoolStage] = useState('grade_1')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (profile) { setAge(profile.age); setSchoolStage(profile.school_stage) }
  }, [profile])

  async function save() {
    setSaving(true)
    try {
      await saveProfile({ child_id: childId, age, school_stage: schoolStage,
        listening_start: profile?.listening_start ?? null, listening_end: profile?.listening_end ?? null })
      await refreshData()
      toast.success('年龄与学段已保存到本地后端')
    } catch (error) { toast.error(error instanceof Error ? error.message : '保存失败') }
    finally { setSaving(false) }
  }

  return (
    <>
      <PageHeader title="孩子与偏好" sub="用于故事推荐和伙伴说话方式" action={<Button size="lg" disabled={saving || age < 5} onClick={() => void save()}>{saving ? '保存中…' : '保存档案'}</Button>} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="基础信息">
          <div className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5 text-sm font-semibold">
              昵称
              <input
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                className="h-11 rounded-xl border border-input bg-background px-3 font-normal outline-none focus:border-primary"
              />
            </label>
            <div className="flex flex-col gap-1.5 text-sm font-semibold">
              年龄
              <div className="flex flex-wrap gap-2">
                {[5, 6, 7, 8, 9, 10, 11, 12].map((a) => (
                  <button
                    key={a}
                    type="button"
                    onClick={() => setAge(a)}
                    aria-pressed={age === a}
                    className={cn('h-10 min-w-12 rounded-xl border px-3 font-semibold', age === a ? 'border-primary bg-primary text-primary-foreground' : 'border-border')}
                  >
                    {a} 岁
                  </button>
                ))}
              </div>
            </div>
            <label className="flex flex-col gap-1.5 text-sm font-semibold">学段
              <select value={schoolStage} onChange={(event) => setSchoolStage(event.target.value)} className="h-11 rounded-xl border border-input bg-background px-3 font-normal">
                <option value="kindergarten_large">幼儿园大班</option>
                {[1, 2, 3, 4, 5, 6].map((grade) => <option key={grade} value={`grade_${grade}`}>小学 {grade} 年级</option>)}
              </select>
            </label>
            <div className="flex flex-col gap-1.5 text-sm font-semibold">
              兴趣偏好
              <div className="flex flex-wrap gap-2">
                {PREFS.map((p) => {
                  const on = prefs.includes(p)
                  return (
                    <button
                      key={p}
                      type="button"
                      aria-pressed={on}
                      onClick={() => setPrefs((l) => (on ? l.filter((x) => x !== p) : [...l, p]))}
                      className={cn('rounded-full border px-3 py-1.5 font-normal', on ? 'border-transparent bg-secondary' : 'border-border text-muted-foreground')}
                    >
                      {p}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        </Panel>

        <Panel title="使用限制">
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-semibold">每日故事时长上限</span>
              <span className="font-bold tabular-nums text-primary">{limit} 分钟</span>
            </div>
            <Slider value={[limit]} min={10} max={60} step={5} onValueChange={(v) => setLimit(Array.isArray(v) ? v[0] : v)} aria-label="每日故事时长上限" />
            <p className="text-xs text-muted-foreground">到达上限后，伙伴会温柔地提醒孩子休息一下。</p>
          </div>
        </Panel>

        <Panel title="陪伴伙伴" className="lg:col-span-2">
          <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5">
            {ANIMALS.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => {
                    setAnimalId(a.id)
                    toast.success(`儿童端伙伴已切换为${a.name}`)
                  }}
                  aria-pressed={animalId === a.id}
                  className={cn('flex w-full flex-col items-center gap-2 rounded-2xl border-2 p-2 transition', animalId === a.id ? 'shadow-md' : 'border-transparent')}
                  style={{ borderColor: animalId === a.id ? a.color : undefined }}
                >
                  <div className="relative aspect-square w-full overflow-hidden rounded-xl" style={{ backgroundColor: '#f6e2c8' }}>
                    <Image src={a.image || '/placeholder.svg'} alt={a.species} fill sizes="140px" className="scale-125 object-cover" />
                  </div>
                  <span className="text-sm font-bold">{a.name}</span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  )
}
