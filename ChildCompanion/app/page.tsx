import { AppShell } from '@/components/app-shell'
import { AppStoreProvider } from '@/components/app-store'

export default function Page() {
  return (
    <AppStoreProvider>
      <AppShell />
    </AppStoreProvider>
  )
}
