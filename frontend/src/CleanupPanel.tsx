import { useEffect, useState } from 'react'
import { Scan, Sparkles, X } from 'lucide-react'
import { mutate, request } from './api'
import type { Crop, Health } from './types'

type Suggestion = { region: Crop; score: number; label: string }
type Props = {
  prefix: string; revision: number; regions: Crop[]; disabled: boolean;
  setRegions: (regions: Crop[]) => void; onDraw: () => void;
  onPreview: (id: string | null) => Promise<void>; onApply: (id: string) => Promise<void>;
  onBusy: (busy: boolean) => void;
}
const same = (a: Crop, b: Crop) => a.x === b.x && a.y === b.y && a.width === b.width && a.height === b.height

export default function CleanupPanel({ prefix, revision, regions, disabled, setRegions, onDraw, onPreview, onApply, onBusy }: Props) {
  const [enabled, setEnabled] = useState(false)
  const [busy, setBusy] = useState(false)
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [preview, setPreview] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [query, setQuery] = useState('a brand logo')
  const [threshold, setThreshold] = useState(.15)
  const [health, setHealth] = useState<Health | null>(null)
  useEffect(() => { void request<Health>('/health').then(setHealth).catch(() => {}) }, [])
  useEffect(() => { setSuggestions([]); setPreview(null); setMessage(''); void onPreview(null) }, [revision])
  function clearPreview() { setPreview(null); void onPreview(null) }
  async function run(work: () => Promise<void>) {
    setBusy(true); onBusy(true); setMessage('')
    try { await work() } catch (e) { setMessage(e instanceof Error ? e.message : 'Cleanup failed. Your image is unchanged.') }
    finally { setBusy(false); onBusy(false) }
  }
  const ready = health?.cleanup?.inpainting_cached && health.cleanup.inpainting_installed
  const detectorReady = health?.cleanup?.detector_cached && health.cleanup.detector_installed
  return <section className="cleanup-panel" aria-label="Object and logo removal">
    <label className="cleanup-toggle"><input type="checkbox" checked={enabled} disabled={busy} onChange={e => {
      setEnabled(e.target.checked); clearPreview(); setRegions([]); setSuggestions([])
    }} /><span><strong>Object & logo removal</strong><small>Optional. Review regions before changing the product.</small></span><Sparkles size={17} /></label>
    {enabled && <>
      <label className="cleanup-query">Detection phrase <input value={query} maxLength={80} disabled={busy || !!preview} onChange={e => setQuery(e.target.value)} placeholder="e.g. a brand logo or a Panasonic logo" /></label>
      <details className="cleanup-help"><summary>Detection sensitivity</summary><label className="cleanup-query">Minimum model score <input aria-label="Detection minimum score" type="range" min="0.05" max="0.5" step="0.01" value={threshold} disabled={busy || !!preview} onChange={e => setThreshold(Number(e.target.value))} /><span>{threshold.toFixed(2)}</span></label><p>Lower scores show more suggestions, including more mistakes. Model scores are not calibrated probabilities.</p></details>
      <div className="cleanup-actions">
        <button className="button secondary compact" disabled={disabled || busy || !!preview || !detectorReady} onClick={() => void run(async () => {
          const result = await mutate<{ suggestions: Suggestion[] }>(`${prefix}/cleanup/detect`, 'POST', { revision, threshold, queries: [query.trim() || 'a brand logo'] })
          setSuggestions(result.suggestions); setMessage(result.suggestions.length ? 'Select only the suggestions you want to remove.' : 'No logo suggestions found. You can draw a region instead.')
        })}><Scan size={14} />Detect logos</button>
        <button className="button secondary compact" disabled={disabled || busy || !!preview || regions.length >= 20} onClick={onDraw}>Draw region</button>
        <button className="button primary compact" disabled={disabled || busy || !regions.length || !ready || !!preview} onClick={() => void run(async () => {
          const result = await mutate<{ preview_id: string }>(`${prefix}/cleanup/preview`, 'POST', { revision, regions })
          await onPreview(result.preview_id); setPreview(result.preview_id)
        })}>{busy ? 'Working…' : 'Preview removal'}</button>
      </div>
      {!ready && <p className="cleanup-help">Install the local LaMa model to enable removal. See README → Object cleanup.</p>}
      {!detectorReady && <p className="cleanup-help">Automatic suggestions need the optional detection model. Drawing regions works independently.</p>}
      {suggestions.length > 0 && <div className="suggestion-list">{suggestions.map((s, i) => <label key={i}><input type="checkbox" disabled={busy || !!preview} checked={regions.some(r => same(r, s.region))} onChange={e => {
        setRegions(e.target.checked ? [...regions, s.region].slice(0, 20) : regions.filter(r => !same(r, s.region)))
      }} />{s.label} <span>{Math.round(s.score * 100)}% model score</span></label>)}</div>}
      {regions.length > 0 && <div className="region-list">{regions.map((r, i) => <button key={i} disabled={busy || !!preview} onClick={() => setRegions(regions.filter((_, n) => n !== i))} aria-label={`Remove region ${i + 1}`}>Region {i + 1} · {r.width} × {r.height}<X size={12} /></button>)}</div>}
      {preview && <div className="cleanup-preview-actions"><strong>Preview only. Your saved image is unchanged.</strong><button className="button secondary compact" disabled={busy} onClick={clearPreview}>Discard preview</button><button className="button primary compact" disabled={busy || disabled} onClick={() => void run(async () => { await onApply(preview); clearPreview(); setRegions([]) })}>Apply removal</button></div>}
      {message && <p className="cleanup-help" role="status">{message}</p>}
      <p className="cleanup-help">AI fills selected rectangles using nearby pixels. It can invent surface detail. Inspect the result; Undo and Restore remain available.</p>
    </>}
  </section>
}
