/** Local experiment BFF: browser never receives backend role tokens or cloud keys. */
import type { NextRequest } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type Context = { params: Promise<{ path: string[] }> }

async function forward(request: NextRequest, { params }: Context) {
  const { path } = await params
  const scope = path[1]
  if (path[0] !== 'v1' || (scope !== 'parent' && scope !== 'child')) {
    return Response.json({ detail: 'route not allowed' }, { status: 404 })
  }
  const backend = new URL(process.env.BACKEND_BASE_URL || 'http://127.0.0.1:8766')
  if (!['127.0.0.1', 'localhost', '::1'].includes(backend.hostname)) {
    return Response.json({ detail: 'local backend required' }, { status: 503 })
  }
  const token = scope === 'parent'
    ? (process.env.LOCAL_PARENT_TOKEN || 'local-parent-token')
    : (process.env.LOCAL_CHILD_TOKEN || 'local-child-token')
  const target = new URL(path.map(encodeURIComponent).join('/'), `${backend.origin}/`)
  target.search = request.nextUrl.search
  const headers = new Headers({ authorization: `Bearer ${token}` })
  const contentType = request.headers.get('content-type')
  if (contentType) headers.set('content-type', contentType)
  const childId = request.headers.get('x-child-id')
  if (childId) headers.set('x-child-id', childId)
  const storyId = request.headers.get('x-story-id')
  if (storyId) headers.set('x-story-id', storyId)
  const sessionId = request.headers.get('x-session-id')
  if (sessionId) headers.set('x-session-id', sessionId)
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === 'GET' || request.method === 'HEAD' ? undefined : await request.arrayBuffer(),
      cache: 'no-store',
      signal: AbortSignal.timeout(60000),
    })
    const responseHeaders = new Headers({ 'cache-control': 'no-store' })
    for (const name of ['content-type', 'x-ai-generated-voice']) {
      const value = upstream.headers.get(name)
      if (value) responseHeaders.set(name, value)
    }
    return new Response(await upstream.arrayBuffer(), { status: upstream.status, headers: responseHeaders })
  } catch {
    return Response.json({ detail: '本地后端无法连接或请求超时' }, { status: 502 })
  }
}

export const GET = forward
export const POST = forward
export const PUT = forward
export const PATCH = forward
export const DELETE = forward
