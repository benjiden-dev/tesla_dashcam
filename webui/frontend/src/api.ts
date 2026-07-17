import type {
  AppConfig,
  DashcamEvent,
  Job,
  OutputFile,
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* not json */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

function post<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  config: () => request<AppConfig>("/api/config"),
  events: () => request<DashcamEvent[]>("/api/events"),
  eventThumbUrl: (id: string, minute?: string) =>
    `/api/events/${id}/thumb${minute ? `?minute=${encodeURIComponent(minute)}` : ""}`,
  mapPreviewUrl: (id: string, size = 320, zoom = 15) =>
    `/api/map/preview?event_id=${encodeURIComponent(id)}&size=${size}&zoom=${zoom}`,

  preview: (event_id: string, minute: string, settings: Record<string, unknown>) =>
    post<{ key: string; url: string; cached: boolean }>("/api/preview", {
      event_id,
      minute,
      settings,
    }),

  cliPreview: (settings: Record<string, unknown>, map_overlay: Record<string, unknown>) =>
    post<{ cli: string }>("/api/cli_preview", { settings, map_overlay }),

  createJob: (body: unknown) => post<Job>("/api/jobs", body),
  jobs: () => request<Job[]>("/api/jobs"),
  job: (id: string, logSince?: number) =>
    request<Job>(`/api/jobs/${id}${logSince != null ? `?log_since=${logSince}` : ""}`),
  cancelJob: (id: string) => post<{ status: string }>(`/api/jobs/${id}/cancel`, {}),

  outputs: () => request<OutputFile[]>("/api/outputs"),
  outputFileUrl: (path: string) =>
    `/api/outputs/file/${path.split("/").map(encodeURIComponent).join("/")}`,
  outputThumbUrl: (path: string, mtime: number) =>
    `/api/outputs/thumb/${path.split("/").map(encodeURIComponent).join("/")}?v=${mtime}`,
  deleteOutput: (path: string) =>
    request<{ deleted: string }>(
      `/api/outputs/file/${path.split("/").map(encodeURIComponent).join("/")}`,
      { method: "DELETE" },
    ),
};

export interface JobStreamHandlers {
  onProgress: (job: Job) => void;
  onLog: (line: string) => void;
  onDone: (status: string) => void;
  onError?: () => void;
}

export function streamJob(jobId: string, handlers: JobStreamHandlers): () => void {
  const source = new EventSource(`/api/jobs/${jobId}/stream`);
  source.addEventListener("progress", (event) => {
    handlers.onProgress(JSON.parse((event as MessageEvent).data) as Job);
  });
  source.addEventListener("log", (event) => {
    handlers.onLog(JSON.parse((event as MessageEvent).data) as string);
  });
  source.addEventListener("done", (event) => {
    handlers.onDone(JSON.parse((event as MessageEvent).data) as string);
    source.close();
  });
  source.onerror = () => {
    handlers.onError?.();
  };
  return () => source.close();
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log2(bytes) / 10), units.length - 1);
  return `${(bytes / 2 ** (10 * index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function formatDuration(totalSeconds: number | null): string {
  if (totalSeconds == null || Number.isNaN(totalSeconds)) return "–";
  const seconds = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
  return `${seconds}s`;
}

export function eventTitle(name: string): string {
  // "2026-07-10_14-30-11" -> "Jul 10, 2026 · 2:30 PM"
  const match = name.match(/^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})$/);
  if (!match) return name;
  const [, y, mo, d, h, mi] = match;
  const date = new Date(
    Number(y),
    Number(mo) - 1,
    Number(d),
    Number(h),
    Number(mi),
  );
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export const REASON_LABELS: Record<string, string> = {
  sentry_aware_object_detection: "Sentry · Object",
  sentry_aware_accel: "Sentry · Motion",
  user_interaction_honk: "Honk",
  user_interaction_dashcam_panel_save: "Manual save",
  user_interaction_dashcam_icon_tapped: "Manual save",
};

export function reasonLabel(reason: string | null): string | null {
  if (!reason) return null;
  if (REASON_LABELS[reason]) return REASON_LABELS[reason];
  for (const [key, label] of Object.entries(REASON_LABELS)) {
    if (reason.startsWith(key)) return label;
  }
  return reason.replace(/_/g, " ").slice(0, 28);
}
