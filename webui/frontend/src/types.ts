export interface Minute {
  key: string;
  time: string;
  cameras: string[];
  size: number;
}

export interface EventMetadata {
  timestamp: string | null;
  city: string | null;
  street: string | null;
  reason: string | null;
  camera: string | null;
  lat: number | null;
  lon: number | null;
}

export interface DashcamEvent {
  id: string;
  path: string;
  name: string;
  group: string;
  minutes: Minute[];
  minute_count: number;
  clip_count: number;
  total_size: number;
  has_thumb: boolean;
  metadata: EventMetadata | null;
}

export type Settings = {
  layout: string;
  perspective: boolean;
  view_mode: string;
  swap: boolean;
  background: string;
  cameras: Record<string, boolean>;
  show_timestamp: boolean;
  halign: string | null;
  valign: string | null;
  fontsize: number | null;
  fontcolor: string | null;
  font: string | null;
  text_overlay_fmt: string | null;
  motion_only: boolean;
  speedup: number | null;
  slowdown: number | null;
  merge: boolean;
  quality: string;
  compression: string;
  encoding: string;
  fps: number;
  bitrate: string | null;
  scale: number | null;
  faststart: boolean;
  skip_existing: boolean;
  gpu: boolean;
  gpu_type: string;
  title_screen_map: boolean;
  loglevel: string;
};

export type MapOverlay = {
  enabled: boolean;
  corner: string;
  size_pct: number;
  opacity: number;
  zoom: number;
};

export interface AppConfig {
  input_dir: string;
  output_dir: string;
  gpu_available: boolean;
  render_node: string;
  default_gpu_type: string;
  engine_version: string | null;
  defaults: Settings;
  map_overlay_defaults: MapOverlay;
  layouts: string[];
  qualities: string[];
  compressions: string[];
  encodings: string[];
  gpu_types: string[];
  cameras: string[];
}

export interface JobProgress {
  phase: string;
  message: string;
  percent: number;
  eta_seconds: number | null;
  total_events: number;
  total_clips: number;
  clips_done: number;
  events_done: number;
  current_event: number;
  clip_in_event: number;
  clips_in_event: number;
  outputs: string[];
  errors: string[];
  warnings: string[];
}

export interface Job {
  id: string;
  status: string;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
  request: {
    event_count: number;
    event_names: string[];
    minute_count: number;
    layout: string | null;
    map_overlay: boolean;
    delete_input: boolean;
  };
  progress: JobProgress;
  cli: string | null;
  outputs: string[];
  deleted_inputs: string[];
  delete_skipped: string[];
  freed_bytes: number;
  error: string | null;
  version: number;
  log_length: number;
  log_truncated: boolean;
  log?: string[];
}

export interface OutputFile {
  path: string;
  name: string;
  size: number;
  mtime: number;
  playable: boolean;
}
