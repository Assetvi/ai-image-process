import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowDownToLine, ArrowLeft, ArrowRight, Check, CheckCheck, ChevronDown, Crop, FolderOpen, HelpCircle, ImagePlus, Images, Layers2, LoaderCircle, LockKeyhole, Plus, Search, ShieldCheck, Sparkles, Upload, WandSparkles, X } from 'lucide-react'
import { imageUrl, mutate, request } from './api'
import ImageEditor from './ImageEditor'
import type { Batch, EditPayload, Health, RecentBatch } from './types'

const sampleNames = ['desk-speaker.png', 'white-bottle.png', 'studio-headphones.png', 'travel-camera.png', 'iphone-15-pro-max.jpg', 'cc0-camera.jpg']

export default function App() {
  const [batch, setBatch] = useState<Batch | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [recent, setRecent] = useState<RecentBatch[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [action, setAction] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<'all' | 'ai' | 'review'>('all')
  const [padding, setPadding] = useState(16)
  const [threshold, setThreshold] = useState(254)
  const [background, setBackground] = useState<'white' | 'transparent'>('white')
  const [reviewedOnly, setReviewedOnly] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const helpDialog = useRef<HTMLDialogElement>(null)
  const setEditorDirty = useCallback((value: boolean) => setDirty(value), [])
  const running = batch?.status === 'processing'
  const busy = action || !!running
  const item = batch?.images.find(image => image.id === selectedId) ?? batch?.images[0]
  const complete = batch?.images.filter(image => image.status === 'ready').length ?? 0
  const approved = batch?.images.filter(image => image.reviewed).length ?? 0
  const aiCount = batch?.images.filter(image => image.remove_background).length ?? 0
  const failed = batch?.images.filter(image => image.status === 'error').length ?? 0
  const pending = batch?.images.filter(image => image.status === 'pending' || image.status === 'error').length ?? 0
  const aiReady = health?.ai.installed && health.ai.model_cached
  const filtered = batch?.images.filter(image => image.name.toLowerCase().includes(search.toLowerCase()) &&
    (filter === 'all' || (filter === 'ai' ? image.remove_background : !image.reviewed))) ?? []

  function accept(next: Batch) {
    setBatch(next); localStorage.setItem('frame-batch', next.id)
  }
  useEffect(() => {
    void request<Health>('/health').then(setHealth).catch(() => setError('Cannot reach the local server. Start it with python -m app.'))
    void request<RecentBatch[]>('/batches').then(setRecent).catch(() => {})
    const id = localStorage.getItem('frame-batch')
    if (id) void request<Batch>(`/batches/${id}`).then(next => {
      accept(next); setPadding(next.options.padding); setThreshold(next.options.white_threshold)
    }).catch(() => localStorage.removeItem('frame-batch'))
  }, [])
  useEffect(() => {
    if (!running || !batch) return
    let active = true, timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try { const next = await request<Batch>(`/batches/${batch.id}`); if (active) setBatch(next) }
      catch { if (active) setError('Connection interrupted. Progress is saved locally; refresh to reconnect.') }
      if (active) timer = setTimeout(poll, 900)
    }
    timer = setTimeout(poll, 500)
    return () => { active = false; clearTimeout(timer) }
  }, [running, batch?.id])
  useEffect(() => {
    if (batch?.status === 'review') void request<Health>('/health').then(setHealth).catch(() => {})
  }, [batch?.status])
  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(''), 4500)
    return () => clearTimeout(timer)
  }, [notice])
  useEffect(() => {
    if (helpOpen) helpDialog.current?.showModal()
    else helpDialog.current?.close()
  }, [helpOpen])

  async function run(operation: () => Promise<void>) {
    setAction(true); setError('')
    try { await operation() }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'Something went wrong. Try again.'); throw caught }
    finally { setAction(false) }
  }
  function leaveDraft() { return !dirty || window.confirm('Discard your unsaved edits?') }
  async function upload(files: File[]) {
    if (busy || !files.length || !leaveDraft()) return
    if (files.length > 200 || files.some(file => file.size > 20 * 1024 * 1024) || files.reduce((sum, file) => sum + file.size, 0) > 500 * 1024 * 1024) {
      setError('Choose up to 200 images, 20 MB each, and 500 MB per batch.'); return
    }
    await run(async () => {
      const form = new FormData(); files.forEach(file => form.append('files', file))
      const next = await request<Batch>('/batches', { method: 'POST', body: form })
      accept(next); setSelectedId(next.images[0].id); setDirty(false); setSearch(''); setFilter('all')
      setNotice(`${next.images.length} images added. Flag the ones that need background removal.`)
      setRecent(await request<RecentBatch[]>('/batches'))
    })
  }
  async function loadSamples() {
    try {
      const files = await Promise.all(sampleNames.map(async name => {
        const response = await fetch(`/samples/${name}`)
        if (!response.ok) throw new Error('Sample images could not load.')
        return new File([await response.blob()], name, { type: name.endsWith('.jpg') ? 'image/jpeg' : 'image/png' })
      }))
      await upload(files)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Sample images could not load.') }
  }
  async function flag(ids: string[], value: boolean) {
    if (!batch || dirty) return
    await run(async () => { accept(await mutate(`/batches/${batch.id}/flags`, 'PATCH', { image_ids: ids, remove_background: value })) })
  }
  async function process() {
    if (!batch || dirty) return
    await run(async () => { accept(await mutate(`/batches/${batch.id}/process`, 'POST', { padding, white_threshold: threshold })) })
  }
  async function edit(payload: EditPayload) {
    if (!batch || !item) return
    await run(async () => { accept(await mutate(`/batches/${batch.id}/images/${item.id}/edit`, 'POST', { ...payload, revision: item.revision })) })
  }
  async function undo() {
    if (!batch || !item) return
    await run(async () => { accept(await mutate(`/batches/${batch.id}/images/${item.id}/undo`, 'POST', { reviewed: false, revision: item.revision })) })
  }
  async function applyCleanup(previewId: string) {
    if (!batch || !item) return
    await run(async () => { accept(await mutate(`/batches/${batch.id}/images/${item.id}/cleanup/apply`, 'POST', { revision: item.revision, preview_id: previewId })) })
  }
  async function review() {
    if (!batch || !item) return
    await run(async () => { accept(await mutate(`/batches/${batch.id}/images/${item.id}/review`, 'PATCH', { reviewed: !item.reviewed, revision: item.revision })) })
  }
  async function exportZip() {
    if (!batch || dirty) return
    await run(async () => {
      const response = await fetch(`/api/batches/${batch.id}/export?background=${background}&reviewed_only=${reviewedOnly}`)
      if (!response.ok) { const body = await response.json(); throw new Error(body.detail) }
      const url = URL.createObjectURL(await response.blob())
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `frame-${batch.id.slice(0, 8)}.zip`
      anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 10000)
      setNotice('ZIP exported. Your images are ready for upload.')
    })
  }
  function navigate(id: string) { if (leaveDraft()) { setSelectedId(id); setDirty(false) } }
  function reset() { if (leaveDraft()) { setBatch(null); setSelectedId(null); setDirty(false); localStorage.removeItem('frame-batch') } }
  const selectedIndex = batch?.images.findIndex(image => image.id === item?.id) ?? 0
  const step = !batch ? 1 : complete === batch.images.length ? 3 : 2

  return <div className="app-shell" onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true) }} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false) }} onDrop={event => {
    event.preventDefault(); setDragging(false); void upload(Array.from(event.dataTransfer.files)).catch(() => {})
  }}>
    <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" multiple hidden onChange={event => { void upload(Array.from(event.target.files ?? [])).catch(() => {}); event.target.value = '' }} />
    <header className="app-header"><a className="brand" href="#" onClick={event => { event.preventDefault(); reset() }} aria-label="Frame home"><span className="brand-icon"><Crop size={23} /></span><span>frame<span className="brand-period">.</span></span></a><span className="header-divider" /><span className="workspace-name">Product image workspace</span><div className="header-right"><span className="local-badge"><span className={`status-dot ${health ? '' : 'muted'}`} />{health ? 'Local workspace' : 'Connecting…'}</span><button className="icon-button" aria-label="Help" title="Help" onClick={() => setHelpOpen(true)}><HelpCircle size={19} /></button><span className="workspace-avatar">F</span></div></header>
    <main className={`main ${batch ? 'has-batch' : ''}`}>
      <div className="page-heading"><div><div className="eyebrow">YOUR PRODUCT IMAGES, READY FOR WHAT’S NEXT</div><h1>{batch ? 'Review your batch.' : 'Prepare product images.'}</h1><p>{batch ? 'Process the batch. Keep the details. You have the final say.' : 'A simple workspace to crop, clean up, and export product images.'}</p></div><div className="page-actions"><div className="history-wrap"><button className="button secondary" disabled={busy || !recent.length} onClick={() => setHistoryOpen(value => !value)}><FolderOpen size={15} /> Recent batches <ChevronDown size={13} /></button>{historyOpen && <div className="history-menu">{recent.map(entry => <button key={entry.id} onClick={() => {
        if (!leaveDraft()) return
        setHistoryOpen(false)
        void run(async () => { const next = await request<Batch>(`/batches/${entry.id}`); accept(next); setSelectedId(next.images[0].id); setDirty(false); setPadding(next.options.padding); setThreshold(next.options.white_threshold) }).catch(() => {})
      }}><Images size={16} /><span>{entry.count} images<small>{new Date(entry.created_at).toLocaleString()}</small></span><span className="tiny-tag">{entry.status}</span></button>)}</div>}</div>{batch && <button className="button primary" disabled={busy} onClick={() => fileInput.current?.click()}><Plus size={16} /> New batch</button>}</div></div>
      <div className="workflow-strip">{[{ number: 1, label: 'Add images', detail: 'Bring your batch' }, { number: 2, label: 'Choose & process', detail: 'AI only where needed' }, { number: 3, label: 'Review & export', detail: 'Ready for your catalog' }].map(({ number, label, detail }) => <div className={`workflow-step ${step === number ? 'current' : ''} ${step > number ? 'done' : ''}`} key={number}><span className="step-number">{step > number ? <Check size={14} /> : `0${number}`}</span><span><strong>{label}</strong><small>{detail}</small></span>{number < 3 && <ArrowRight size={15} className="step-arrow" />}</div>)}<span className="workflow-privacy"><LockKeyhole size={13} /> Images stay on this computer</span></div>
      {error && <div className="alert error" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X size={16} /></button></div>}
      {!batch ? <>
        <section className="empty-layout"><div className="upload-card"><div className="upload-card-top"><span className="section-overline">LET’S START WITH YOUR IMAGES</span><span className="tiny-tag">Batch workspace</span></div><div className="upload-area" onClick={() => fileInput.current?.click()} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); fileInput.current?.click() } }} role="button" tabIndex={0} aria-label="Upload images"><div className="upload-illustration"><div className="image-paper paper-left"><Images size={33} /></div><div className="image-paper paper-right"><Crop size={31} /></div><div className="image-paper paper-front"><ImagePlus size={39} /><span><Plus size={13} /></span></div></div><h2>Drop your images here</h2><p>One product or a whole catalog. Start with a batch.</p><span className="button primary"><Upload size={16} />{action ? 'Adding images…' : 'Choose images'}</span><small>JPG, PNG, or WebP · Up to 200 images · 20 MB each</small></div><div className="sample-row"><span>Just looking around?</span><button disabled={action} onClick={() => void loadSamples()}>Try an example batch <ArrowRight size={14} /></button></div></div>
          <aside className="intro-card"><span className="section-overline">THOUGHTFULLY SIMPLE</span><h2>Automate the repetitive.<br />Keep the human touch.</h2><p>A quick pass from you. The heavy lifting from your computer.</p><div className="intro-feature"><span><Crop size={19} /></span><div><strong>Crop the whole batch</strong><p>Trim excess whitespace in one go.</p></div></div><div className="intro-feature"><span><WandSparkles size={19} /></span><div><strong>Choose where AI helps</strong><p>Flag only images that need background removal.</p></div></div><div className="intro-feature"><span><ShieldCheck size={19} /></span><div><strong>Keep every product detail</strong><p>Review, restore, and crop by hand when needed.</p></div></div><div className="intro-note"><LockKeyhole size={15} /><span>Local processing.<br /><strong>Your images stay yours.</strong></span></div></aside></section>
        <div className="empty-footer"><div><Layers2 size={17} /><strong>One batch, one download.</strong><span>Export a ZIP, ready for your existing upload workflow.</span></div><span>No image uploads to AI services</span></div>
      </> : <>
        <div className="batch-bar"><div className="batch-title"><span className="batch-icon"><Images size={19} /></span><div><strong>Batch {batch.id.slice(0, 6).toUpperCase()}</strong><small>{batch.images.length} images <span>·</span> {approved} approved</small></div><span className={`batch-status ${running ? 'processing' : ''}`}>{running ? <><LoaderCircle size={12} className="spin" /> Processing</> : complete === batch.images.length ? <><Check size={12} /> Ready to review</> : 'Ready to process'}</span></div><div className="batch-navigation"><button className="icon-button" aria-label="Previous image" disabled={selectedIndex === 0} onClick={() => navigate(batch.images[selectedIndex - 1].id)}><ArrowLeft size={16} /></button><span>{selectedIndex + 1} / {batch.images.length}</span><button className="icon-button" aria-label="Next image" disabled={selectedIndex >= batch.images.length - 1} onClick={() => navigate(batch.images[selectedIndex + 1].id)}><ArrowRight size={16} /></button></div></div>
        <div className="workbench"><aside className="library-panel"><div className="panel-heading"><h2>Images <span>{batch.images.length}</span></h2><button className="icon-button" aria-label="Upload a new batch" title="Upload a new batch" disabled={busy} onClick={() => fileInput.current?.click()}><Plus size={17} /></button></div><label className="search-field"><Search size={14} /><input type="search" aria-label="Search images" placeholder="Find an image…" value={search} onChange={event => setSearch(event.target.value)} /></label><div className="image-filters">{(['all', 'ai', 'review'] as const).map(value => <button key={value} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{value === 'all' ? 'All' : value === 'ai' ? 'Flagged' : 'To review'}</button>)}</div><div className="image-list">{filtered.map((image, index) => <div className={`image-card ${item?.id === image.id ? 'selected' : ''}`} key={image.id}><button className="image-select" onClick={() => navigate(image.id)} aria-label={`Open ${image.name}`} aria-pressed={item?.id === image.id}><div className="image-thumb checker"><img loading="lazy" src={imageUrl(batch.id, image.id, 'thumbnail', image.revision)} alt={image.name} /><span className="image-index">{String(index + 1).padStart(2, '0')}</span>{image.reviewed && <span className="review-check"><Check size={12} /></span>}{image.status === 'processing' && <LoaderCircle size={20} className="thumb-loader spin" />}</div><span className="image-name" title={image.name}>{image.name}</span></button><label className="ai-flag"><input type="checkbox" checked={image.remove_background} disabled={busy || dirty} onChange={event => void flag([image.id], event.target.checked).catch(() => {})} /><span>{image.status === 'error' ? 'Processing failed' : 'Remove background'}</span>{image.remove_background && <Sparkles size={11} />}</label></div>)}{!filtered.length && <div className="no-images">No matching images.</div>}</div><div className="library-bottom"><button disabled={busy || dirty || !filtered.length} onClick={() => void flag(filtered.map(image => image.id), true).catch(() => {})}>Flag visible</button><span>·</span><button disabled={busy || dirty || !filtered.length} onClick={() => void flag(filtered.map(image => image.id), false).catch(() => {})}>Clear visible flags</button></div></aside>
          {item && <ImageEditor key={item.id} batchId={batch.id} item={item} busy={busy} onSave={edit} onUndo={undo} onReview={review} onDirty={setEditorDirty} onCleanupApply={applyCleanup} />}
          <aside className="settings-panel"><section className="processing-settings"><div className="panel-heading"><h2>Batch settings</h2><Crop size={17} /></div><div className="setting-label"><strong>Auto-crop</strong><span className="setting-tag">All images</span></div><p className="setting-description">Trim outer whitespace. Keep the product.</p><div className="range-heading"><label htmlFor="padding">Edge padding</label><span>{padding} px</span></div><input id="padding" type="range" min="0" max="100" value={padding} disabled={busy} onChange={event => setPadding(Number(event.target.value))} /><details className="advanced"><summary>Advanced crop settings</summary><div className="range-heading"><label htmlFor="threshold">White threshold</label><span>{threshold}</span></div><input id="threshold" type="range" min="235" max="255" value={threshold} disabled={busy} onChange={event => setThreshold(Number(event.target.value))} /><p>Higher values preserve more near-white detail. Applies to pending images on their next process.</p></details><div className="setting-divider" /><div className="setting-label"><strong>Background removal</strong><span className="ai-label"><Sparkles size={11} /> Selective AI</span></div><p className="setting-description">Only the images you flag.<br />{aiCount} of {batch.images.length} selected</p><div className={`ai-status ${aiReady ? 'available' : ''}`}><span className={`status-dot ${aiReady ? '' : 'warning'}`} /><span>{aiReady ? health?.ai.providers.includes('CUDAExecutionProvider') ? 'Local AI · CUDA active' : health?.ai.providers.length ? 'Local AI · CPU active' : 'Local AI ready' : 'AI setup needed'}</span>{!aiReady && <button aria-label="AI setup instructions" onClick={() => setHelpOpen(true)}><HelpCircle size={13} /></button>}</div><button className="button primary process-button" disabled={busy || dirty || !pending} onClick={() => void process().catch(() => {})}>{running ? <LoaderCircle size={16} className="spin" /> : complete === batch.images.length ? <CheckCheck size={16} /> : <WandSparkles size={16} />}{running ? `Processing ${complete} / ${batch.images.length}` : complete === batch.images.length ? 'All images processed' : failed ? 'Retry pending images' : 'Process batch'}</button>{running && <div className="progress-track" role="progressbar" aria-valuenow={complete} aria-valuemin={0} aria-valuemax={batch.images.length}><span style={{ width: `${complete / batch.images.length * 100}%` }} /></div>}<small className="process-note">{dirty ? 'Save or discard your edits to continue.' : batch.elapsed_seconds !== null ? `Last run finished in ${batch.elapsed_seconds.toFixed(1)}s` : `${batch.images.length - aiCount} crop only · ${aiCount} crop + background removal`}</small></section>
            <section className="export-settings"><div className="panel-heading"><h2>Export</h2><ArrowDownToLine size={16} /></div><label className="export-select-label" htmlFor="export-background">Background</label><select id="export-background" value={background} onChange={event => setBackground(event.target.value as 'white' | 'transparent')}><option value="white">Solid white</option><option value="transparent">Transparent</option></select><label className="review-only"><input type="checkbox" checked={reviewedOnly} onChange={event => setReviewedOnly(event.target.checked)} /><span>Approved images only</span></label><button className="button export-button" disabled={busy || dirty || complete !== batch.images.length || (reviewedOnly && !approved)} onClick={() => void exportZip().catch(() => {})}><ArrowDownToLine size={16} /> Export ZIP <span>{reviewedOnly ? approved : batch.images.length}</span></button><p className="export-note">PNG files + batch manifest.<br />Names kept; duplicates numbered.</p></section><div className="product-note"><ShieldCheck size={18} /><p>White products need a closer look.<br /><strong>The restore brush brings details back.</strong></p></div></aside>
        </div><div className="workspace-footer"><span><LockKeyhole size={12} /> Stored locally · Original images preserved</span><span>{complete} processed <span>·</span> {approved} approved <span>·</span> {failed} errors</span></div>
      </>}
    </main><footer className="app-footer"><span>frame. <span>A little help with the repetitive things.</span></span><a href="/samples/CREDITS.md" target="_blank" rel="noreferrer">Demo image credits</a><span>Made for a human final pass.</span></footer>
    {notice && <div className="toast" role="status"><Check size={16} />{notice}</div>}
    {dragging && <div className="drop-overlay"><Upload size={40} /><strong>Drop to start a new batch</strong><span>Your current batch stays saved.</span></div>}
    <dialog ref={helpDialog} className="help-dialog" onClose={() => setHelpOpen(false)}><div className="dialog-heading"><h2>A quick guide to Frame</h2><button className="icon-button" aria-label="Close help" onClick={() => setHelpOpen(false)}><X size={19} /></button></div><ol><li><strong>Add your images.</strong> JPEG, PNG, and WebP; up to 200 per batch, 20 MB each, and 24 megapixels per image.</li><li><strong>Choose where AI helps.</strong> Flag images needing background removal. Leave clean white-background images unflagged.</li><li><strong>Process the batch.</strong> Every pending image is auto-cropped. AI runs only on flagged images. Completed images keep their edits.</li><li><strong>Review and correct.</strong> Compare with the original, drag a manual crop, restore lost pixels, or erase leftovers. Save edits, then approve.</li><li><strong>Export a ZIP.</strong> Choose white or transparent output. Approval is optional unless you select “Approved images only.”</li></ol><div className="help-ai"><h3>Enable local background removal</h3><p>Run these commands from the project folder, in your Python environment:</p><pre>pip install -e ".[ai]"{'\n'}python -m app.download_model</pre><p>This downloads the model once. Uploaded images are processed locally. Restart the server after installing. Crop-only processing works without the AI extra.</p></div><p className="help-small">Transparency export preserves existing transparency; it does not remove an unflagged image’s white background. Cropping uses available image bounds; padding does not add new pixels. Recent batches are saved locally and can be reopened after a refresh.</p></dialog>
  </div>
}
