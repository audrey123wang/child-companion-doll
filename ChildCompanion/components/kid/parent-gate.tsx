'use client'

import { useState } from 'react'
import { Lock, X } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { useAppStore } from '@/components/app-store'
import { cn } from '@/lib/utils'

const QUESTIONS = [
  { q: '7 × 6', a: 42, options: [36, 42, 48, 13] },
  { q: '9 × 8', a: 72, options: [64, 17, 72, 81] },
  { q: '13 + 29', a: 42, options: [32, 42, 52, 38] },
]

export function ParentGate({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { setMode } = useAppStore()
  const [idx, setIdx] = useState(0)
  const [wrong, setWrong] = useState<number | null>(null)
  const item = QUESTIONS[idx]

  function pick(n: number) {
    if (n === item.a) {
      onOpenChange(false)
      setWrong(null)
      setMode('parent')
    } else {
      setWrong(n)
      setTimeout(() => {
        setWrong(null)
        setIdx((i) => (i + 1) % QUESTIONS.length)
      }, 700)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false} className="max-w-md rounded-3xl border-0 bg-card p-8">
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          className="absolute right-4 top-4 rounded-full p-2 text-muted-foreground hover:bg-muted"
          aria-label="关闭"
        >
          <X className="size-5" />
        </button>
        <div className="flex flex-col items-center gap-2 text-center">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-muted text-primary">
            <Lock className="size-6" />
          </span>
          <DialogTitle className="text-xl font-bold">家长验证</DialogTitle>
          <DialogDescription>请家长回答下面的问题，进入家长端</DialogDescription>
        </div>
        <p className="mt-4 text-center text-4xl font-extrabold tracking-wide">{item.q} = ?</p>
        <div className="mt-4 grid grid-cols-2 gap-3">
          {item.options.map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => pick(n)}
              className={cn(
                'h-14 rounded-2xl border-2 border-border bg-background text-xl font-bold transition hover:border-primary hover:text-primary',
                wrong === n && 'border-destructive bg-destructive/10 text-destructive',
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
