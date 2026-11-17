export type ImageItem = {
  id: string; name: string; width: number; height: number;
  remove_background: boolean; status: 'pending' | 'queued' | 'processing' | 'ready' | 'error';
  crop: [number, number, number, number]; reviewed: boolean; revision: number;
  history: { file: string; crop: number[]; warning: string | null }[];
  error: string | null; warning: string | null;
}
export type Batch = {
  id: string; created_at: string; status: 'draft' | 'processing' | 'review';
  options: { padding: number; white_threshold: number };
  elapsed_seconds: number | null; images: ImageItem[];
}
export type Health = {
  status: string;
  ai: { installed: boolean; model_cached: boolean; model: string; providers: string[]; error: string | null };
}
export type Stroke = { mode: 'restore' | 'erase'; radius: number; points: { x: number; y: number }[] }
export type Crop = { x: number; y: number; width: number; height: number }
export type EditPayload = { strokes?: Stroke[]; crop?: Crop; auto_crop?: boolean; reset_original?: boolean }
export type RecentBatch = { id: string; created_at: string; count: number; status: Batch['status'] }
