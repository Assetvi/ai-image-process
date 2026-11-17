import { useEffect, useRef, useState } from 'react'
import { Check, Crop as CropIcon, Eraser, Eye, Maximize2, MousePointer2, Paintbrush, RotateCcw, Save, Scan, Undo2, X, ZoomIn, ZoomOut } from 'lucide-react'
import { imageUrl } from './api'
import CleanupPanel from './CleanupPanel'
import type { Crop, EditPayload, ImageItem, Stroke } from './types'

type Mode = 'view' | 'crop' | 'restore' | 'erase' | 'region'
type Props = {
  batchId: string; item: ImageItem; busy: boolean;
  onSave: (edit: EditPayload) => Promise<void>;
  onUndo: () => Promise<void>;
  onReview: () => Promise<void>;
  onDirty: (dirty: boolean) => void;
  onCleanupApply: (id: string) => Promise<void>;
}

export default function ImageEditor({ batchId, item, busy, onSave, onUndo, onReview, onDirty, onCleanupApply }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const viewport = useRef<HTMLDivElement>(null)
  const images = useRef<{ original: HTMLImageElement; current: HTMLImageElement } | null>(null)
  const activeStroke = useRef<Stroke | null>(null)
  const cropStart = useRef<{ x: number; y: number } | null>(null)
  const [mode, setMode] = useState<Mode>('view')
  const [original, setOriginal] = useState(false)
  const [strokes, setStrokes] = useState<Stroke[]>([])
  const [crop, setCrop] = useState<Crop | null>(null)
  const [radius, setRadius] = useState(24)
  const [zoom, setZoom] = useState(1)
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [size, setSize] = useState({ width: 600, height: 420 })
  const [paintTick, setPaintTick] = useState(0)
  const [saving, setSaving] = useState(false)
  const [regions, setRegions] = useState<Crop[]>([])
  const [regionDraft, setRegionDraft] = useState<Crop | null>(null)
  const regionDraftRef = useRef<Crop | null>(null)
  const [cleanupBusy, setCleanupBusy] = useState(false)
  const [previewImage, setPreviewImage] = useState<HTMLImageElement | null>(null)
  const [previewActive, setPreviewActive] = useState(false)
  const previewGeneration = useRef(0)
  const prefix = `/batches/${batchId}/images/${item.id}`
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null)
  const pixelDirty = strokes.length > 0 || crop !== null
  const dirty = pixelDirty || regions.length > 0 || cleanupBusy
  const canEdit = item.status === 'ready' && !busy && !saving && !cleanupBusy && loaded && !original
  function changePreview(id: string | null): Promise<void> {
    const generation = ++previewGeneration.current
    setMode('view'); setPreviewImage(null); setPreviewActive(!!id)
    if (!id) return Promise.resolve()
    return new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => { if (generation === previewGeneration.current) setPreviewImage(img); resolve() }
      img.onerror = () => { if (generation === previewGeneration.current) setPreviewActive(false); reject(new Error('Preview could not load. Generate another preview.')) }
      img.src = `/api${prefix}/cleanup/previews/${id}`
    })
  }

  useEffect(() => { onDirty(dirty); return () => onDirty(false) }, [dirty, onDirty])
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  useEffect(() => {
    let cancelled = false
    setLoaded(false); setLoadError(false); setStrokes([]); setCrop(null); setMode('view'); setZoom(1)
    activeStroke.current = null; cropStart.current = null
    setRegions([]); setRegionDraft(null); regionDraftRef.current = null; changePreview(null)
    const load = (kind: string) => new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = reject
      img.src = imageUrl(batchId, item.id, kind, item.revision)
    })
    void Promise.all([load('original'), load('current')]).then(([source, current]) => {
      if (!cancelled) { images.current = { original: source, current }; setLoaded(true) }
    }).catch(() => { if (!cancelled) setLoadError(true) })
    return () => { cancelled = true }
  }, [batchId, item.id, item.revision])
  useEffect(() => {
    if (!viewport.current) return
    const observer = new ResizeObserver(([entry]) => setSize({ width: entry.contentRect.width, height: entry.contentRect.height }))
    observer.observe(viewport.current)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const element = canvas.current
    if (!element || !images.current || !loaded) return
    const scale = Math.min(1, 1800 / Math.max(item.width, item.height))
    element.width = Math.round(item.width * scale)
    element.height = Math.round(item.height * scale)
    const context = element.getContext('2d')!
    context.clearRect(0, 0, element.width, element.height)
    context.drawImage(original ? images.current.original : previewImage ?? images.current.current, 0, 0, element.width, element.height)
    if (original) return
    for (const stroke of [...strokes, ...(activeStroke.current ? [activeStroke.current] : [])]) {
      context.save()
      context.beginPath()
      const r = stroke.radius * scale
      const points = stroke.points.map(p => ({ x: p.x * element.width, y: p.y * element.height }))
      // A union of round dabs matches the full-resolution server brush geometry.
      for (let i = 0; i < points.length; i++) {
        const p = points[i]
        context.moveTo(p.x + r, p.y); context.arc(p.x, p.y, r, 0, 2 * Math.PI)
        if (i > 0) {
          const prev = points[i - 1], angle = Math.atan2(p.y - prev.y, p.x - prev.x)
          const dx = Math.sin(angle) * r, dy = Math.cos(angle) * r
          context.moveTo(prev.x + dx, prev.y - dy); context.lineTo(p.x + dx, p.y - dy)
          context.lineTo(p.x - dx, p.y + dy); context.lineTo(prev.x - dx, prev.y + dy); context.closePath()
        }
      }
      if (stroke.mode === 'restore') {
        context.clip(); context.clearRect(0, 0, element.width, element.height)
        context.drawImage(images.current.original, 0, 0, element.width, element.height)
      } else { context.globalCompositeOperation = 'destination-out'; context.fill() }
      context.restore()
    }
  }, [loaded, item.width, item.height, strokes, original, paintTick, previewImage])

  const ratio = item.width / item.height
  const fitWidth = Math.max(100, Math.min(size.width - 80, (size.height - 80) * ratio))
  const displayWidth = fitWidth * zoom
  const box = crop ?? { x: item.crop[0], y: item.crop[1], width: item.crop[2] - item.crop[0], height: item.crop[3] - item.crop[1] }

  function position(event: React.PointerEvent<HTMLCanvasElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) }
  }
  function pointerDown(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!canEdit || previewActive || mode === 'view' || event.button !== 0) return
    event.currentTarget.setPointerCapture(event.pointerId)
    const point = position(event)
    if (mode === 'crop' || mode === 'region') cropStart.current = point
    else {
      activeStroke.current = { mode, radius, points: [point] }
      setPaintTick(v => v + 1)
    }
  }
  function pointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    const point = position(event)
    setCursor(point)
    if (activeStroke.current && activeStroke.current.points.length < 4000) {
      activeStroke.current.points.push(point); setPaintTick(v => v + 1)
    }
    if (cropStart.current) {
      const start = cropStart.current
      const x = Math.min(item.width - 1, Math.floor(Math.min(start.x, point.x) * item.width))
      const y = Math.min(item.height - 1, Math.floor(Math.min(start.y, point.y) * item.height))
      const rectangle = { x, y, width: Math.max(1, Math.min(item.width - x, Math.ceil(Math.abs(start.x - point.x) * item.width))),
        height: Math.max(1, Math.min(item.height - y, Math.ceil(Math.abs(start.y - point.y) * item.height))) }
      if (mode === 'region') { regionDraftRef.current = rectangle; setRegionDraft(rectangle) }
      else setCrop(rectangle)
    }
  }
  function pointerEnd() {
    if (regionDraftRef.current) {
      const region = regionDraftRef.current
      setRegions(previous => [...previous, region].slice(0, 20)); regionDraftRef.current = null; setRegionDraft(null)
    }
    const stroke = activeStroke.current
    if (stroke) { setStrokes(previous => [...previous, stroke]); activeStroke.current = null }
    cropStart.current = null
  }
  async function save(extra: EditPayload = {}) {
    setSaving(true)
    try { await onSave({ strokes, ...(crop ? { crop } : {}), ...extra }); setStrokes([]); setCrop(null) }
    catch { /* Parent presents the API error and leaves this draft intact. */ }
    finally { setSaving(false) }
  }
  const tools = [
    { mode: 'view', icon: MousePointer2, title: 'Inspect' }, { mode: 'crop', icon: CropIcon, title: 'Crop' },
    { mode: 'restore', icon: Paintbrush, title: 'Restore' }, { mode: 'erase', icon: Eraser, title: 'Erase' },
  ] as const

  return <section className="editor" aria-label="Image editor">
    <div className="editor-top"><div className="editor-file"><span className="file-symbol">IMG</span><div><strong>{item.name}</strong><small>{item.width.toLocaleString()} × {item.height.toLocaleString()} px <span>•</span> Original preserved</small></div></div>
      <div className="segmented" aria-label="Image comparison"><button className={!original ? 'active' : ''} onClick={() => setOriginal(false)}>Processed</button><button className={original ? 'active' : ''} onClick={() => setOriginal(true)}><Eye size={13} /> Original</button></div></div>
    <div className="editor-toolbar"><div className="tool-group">{tools.map(({ mode: value, icon: Icon, title }) => <button key={value} className={`tool ${mode === value ? 'selected' : ''}`} disabled={value !== 'view' && (!canEdit || previewActive || strokes.length >= 200)} onClick={() => setMode(value)} title={title}><Icon size={16} /><span>{title}</span></button>)}</div>
      <div className="tool-group"><button className="icon-button" title="Undo last brush stroke or saved edit" aria-label="Undo" disabled={busy || saving || cleanupBusy || previewActive || (!dirty && item.history.length === 0)} onClick={() => {
        if (regions.length) { setRegions(p => p.slice(0, -1)); changePreview(null) }
        else if (crop) setCrop(null)
        else if (strokes.length) setStrokes(p => p.slice(0, -1))
        else void onUndo().catch(() => {})
      }}><Undo2 size={17} /></button><button className="icon-button" title="Reset to original" aria-label="Reset to original" disabled={!canEdit || dirty} onClick={() => void save({ reset_original: true })}><RotateCcw size={16} /></button></div></div>
    <div className={`editor-viewport ${mode === 'view' || !canEdit ? '' : 'drawing'}`} ref={viewport}>
      <div className="canvas-surround"><div className="canvas-board checker" style={{ width: displayWidth, height: displayWidth / ratio }}>
        <canvas aria-label="Image editing canvas" ref={canvas} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerEnd} onPointerCancel={pointerEnd} onLostPointerCapture={pointerEnd} onPointerLeave={() => setCursor(null)} />
        {loaded && !original && <div className={`crop-box ${mode === 'crop' ? 'crop-active' : ''}`} style={{ left: `${box.x / item.width * 100}%`, top: `${box.y / item.height * 100}%`, width: `${box.width / item.width * 100}%`, height: `${box.height / item.height * 100}%` }}><i /><i /><i /><i /><span>{box.width} × {box.height}</span></div>}
        {!original && !previewImage && [...regions, ...(regionDraft ? [regionDraft] : [])].map((r, i) => <div key={i} className="removal-region" style={{ left: `${r.x / item.width * 100}%`, top: `${r.y / item.height * 100}%`, width: `${r.width / item.width * 100}%`, height: `${r.height / item.height * 100}%` }}><span>{i + 1}</span></div>)}
        {cursor && canEdit && (mode === 'restore' || mode === 'erase') && <div className={`brush-cursor ${mode}`} style={{ left: `${cursor.x * 100}%`, top: `${cursor.y * 100}%`, width: radius * 2 / item.width * displayWidth, height: radius * 2 / item.width * displayWidth }} />}
      </div></div>
      {!loaded && <div className="canvas-loading">{loadError ? 'Image could not load. Refresh to try again.' : 'Loading image…'}</div>}
      <div className="canvas-label"><span className={`status-dot ${original ? 'muted' : ''}`} />{original ? 'Original image' : dirty ? 'Unsaved changes' : 'Output crop preview'}</div>
      <div className="zoom-controls"><button aria-label="Zoom out" disabled={zoom <= 0.5} onClick={() => setZoom(z => Math.max(0.5, z - 0.25))}><ZoomOut size={15} /></button><span>{Math.round(zoom * 100)}%</span><button aria-label="Zoom in" disabled={zoom >= 4} onClick={() => setZoom(z => Math.min(4, z + 0.25))}><ZoomIn size={15} /></button><button aria-label="Fit image" title="Fit image" onClick={() => setZoom(1)}><Maximize2 size={14} /></button></div>
    </div>
    <div className="editor-bottom"><div className="editor-hint">{mode === 'restore' || mode === 'erase' ? <><label htmlFor="brush-size">Brush size</label><input id="brush-size" aria-label="Brush radius" type="range" min="2" max="150" value={radius} onChange={e => setRadius(Number(e.target.value))} /><span>{radius * 2}px</span></> : <><Scan size={15} /><span>{mode === 'crop' ? 'Drag a rectangle around the product.' : 'Inspect the edges. Restore any missing product detail.'}</span></>}</div>
      {pixelDirty ? <div className="button-row"><button className="button subtle compact" disabled={saving} onClick={() => { setStrokes([]); setCrop(null) }}><X size={14} />Discard</button><button className="button primary compact" disabled={saving || busy || cleanupBusy} onClick={() => void save()}><Save size={14} />{saving ? 'Saving…' : 'Save edits'}</button></div> : <button className={`button compact ${item.reviewed ? 'approved' : 'subtle'}`} disabled={!canEdit || dirty} onClick={() => void onReview().catch(() => {})}><Check size={15} />{item.reviewed ? 'Approved' : 'Approve image'}</button>}</div>
    {item.status !== 'ready' && <div className={`image-notice ${item.status === 'error' ? 'error-notice' : ''}`}>{item.status === 'error' ? item.error : item.status === 'pending' ? 'Choose whether this image needs background removal, then process the batch.' : 'Processing this batch. Editing will be available when it finishes.'}</div>}
    {item.warning && <div className="image-notice">{item.warning} Use manual crop if needed.</div>}
    <div className="editor-secondary"><button disabled={!canEdit || dirty} onClick={() => void save({ auto_crop: true })}><CropIcon size={13} /> Auto-crop again</button><span>Edits save at original resolution</span></div>
    <CleanupPanel prefix={prefix} revision={item.revision} regions={regions} setRegions={setRegions} disabled={!canEdit || pixelDirty} onDraw={() => setMode('region')} onPreview={changePreview} onApply={onCleanupApply} onBusy={setCleanupBusy} />
  </section>
}
