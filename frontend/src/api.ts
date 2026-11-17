import type { Batch } from './types'

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}).`)
  }
  return response.json() as Promise<T>
}
export function mutate(path: string, method: string, payload: unknown) {
  return request<Batch>(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
}
export function imageUrl(batch: string, image: string, kind: string, revision: number) {
  return `/api/batches/${batch}/images/${image}/${kind}?v=${revision}`
}
