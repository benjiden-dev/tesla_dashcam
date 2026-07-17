import { create } from "zustand";
import { api, streamJob } from "./api";
import type {
  AppConfig,
  DashcamEvent,
  Job,
  MapOverlay,
  OutputFile,
  Settings,
} from "./types";

const MAX_UI_LOG = 2000;

export type Tab = "create" | "outputs";

interface StudioState {
  config: AppConfig | null;
  events: DashcamEvent[];
  eventsLoading: boolean;
  eventsError: string | null;
  groupFilter: string;
  selectedIds: string[];
  primaryId: string | null;
  minutes: Record<string, string[] | null>;
  settings: Partial<Settings>;
  mapOverlay: MapOverlay;
  deleteInput: boolean;
  tab: Tab;

  jobs: Job[];
  activeJob: Job | null;
  activeLog: string[];
  logOpen: boolean;

  outputs: OutputFile[];
  outputsLoading: boolean;

  init: () => Promise<void>;
  refreshEvents: () => Promise<void>;
  refreshJobs: () => Promise<void>;
  refreshOutputs: () => Promise<void>;
  setTab: (tab: Tab) => void;
  setGroupFilter: (group: string) => void;
  selectEvent: (id: string, additive: boolean) => void;
  toggleMinute: (eventId: string, key: string) => void;
  setMinutes: (eventId: string, keys: string[] | null) => void;
  setSetting: <K extends keyof Settings>(key: K, value: Settings[K]) => void;
  toggleCamera: (camera: string) => void;
  setMapOverlay: (overlay: Partial<MapOverlay>) => void;
  setDeleteInput: (value: boolean) => void;
  setLogOpen: (open: boolean) => void;
  run: () => Promise<Job>;
  cancelActive: () => Promise<void>;
  watchJob: (jobId: string) => void;
}

export const useStudio = create<StudioState>((set, get) => ({
  config: null,
  events: [],
  eventsLoading: true,
  eventsError: null,
  groupFilter: "All",
  selectedIds: [],
  primaryId: null,
  minutes: {},
  settings: {},
  mapOverlay: {
    enabled: false,
    corner: "bottom_right",
    size_pct: 0.22,
    opacity: 0.9,
    zoom: 16,
  },
  deleteInput: false,
  tab: "create",

  jobs: [],
  activeJob: null,
  activeLog: [],
  logOpen: false,

  outputs: [],
  outputsLoading: false,

  init: async () => {
    try {
      const [config, jobs] = await Promise.all([api.config(), api.jobs()]);
      set({
        config,
        jobs,
        mapOverlay: { ...config.map_overlay_defaults },
        settings: { gpu: config.gpu_available },
      });
      const running = jobs.find(
        (job) => job.status === "running" || job.status === "queued",
      );
      if (running) {
        set({ activeJob: running });
        get().watchJob(running.id);
      }
    } catch (error) {
      set({ eventsError: String(error) });
    }
    await Promise.all([get().refreshEvents(), get().refreshOutputs()]);
  },

  refreshEvents: async () => {
    set({ eventsLoading: true, eventsError: null });
    try {
      const events = await api.events();
      const { primaryId, selectedIds, minutes } = get();
      const ids = new Set(events.map((event) => event.id));
      set({
        events,
        eventsLoading: false,
        selectedIds: selectedIds.filter((id) => ids.has(id)),
        primaryId: primaryId && ids.has(primaryId) ? primaryId : null,
        minutes: Object.fromEntries(
          Object.entries(minutes).filter(([id]) => ids.has(id)),
        ),
      });
    } catch (error) {
      set({ eventsLoading: false, eventsError: String(error) });
    }
  },

  refreshJobs: async () => {
    try {
      set({ jobs: await api.jobs() });
    } catch {
      /* transient */
    }
  },

  refreshOutputs: async () => {
    set({ outputsLoading: true });
    try {
      set({ outputs: await api.outputs(), outputsLoading: false });
    } catch {
      set({ outputsLoading: false });
    }
  },

  setTab: (tab) => set({ tab }),
  setGroupFilter: (groupFilter) => set({ groupFilter }),

  selectEvent: (id, additive) => {
    const { selectedIds, primaryId } = get();
    if (additive) {
      const next = selectedIds.includes(id)
        ? selectedIds.filter((selected) => selected !== id)
        : [...selectedIds, id];
      set({
        selectedIds: next,
        primaryId: next.includes(primaryId ?? "") ? primaryId : next[0] ?? null,
      });
    } else {
      set({ selectedIds: [id], primaryId: id });
    }
  },

  toggleMinute: (eventId, key) => {
    const { minutes, events } = get();
    const event = events.find((candidate) => candidate.id === eventId);
    if (!event) return;
    const all = event.minutes.map((minute) => minute.key);
    const current = minutes[eventId] ?? all;
    const next = current.includes(key)
      ? current.filter((candidate) => candidate !== key)
      : [...current, key].sort();
    set({
      minutes: {
        ...minutes,
        [eventId]: next.length === all.length ? null : next,
      },
    });
  },

  setMinutes: (eventId, keys) =>
    set({ minutes: { ...get().minutes, [eventId]: keys } }),

  setSetting: (key, value) =>
    set({ settings: { ...get().settings, [key]: value } }),

  toggleCamera: (camera) => {
    const { settings, config } = get();
    const defaults = config?.defaults.cameras ?? {};
    const cameras = { ...defaults, ...(settings.cameras ?? {}) };
    cameras[camera] = !(cameras[camera] ?? true);
    set({ settings: { ...settings, cameras } });
  },

  setMapOverlay: (overlay) =>
    set({ mapOverlay: { ...get().mapOverlay, ...overlay } }),

  setDeleteInput: (deleteInput) => set({ deleteInput }),
  setLogOpen: (logOpen) => set({ logOpen }),

  run: async () => {
    const { selectedIds, minutes, settings, mapOverlay, deleteInput } = get();
    const job = await api.createJob({
      events: selectedIds.map((id) => ({ id, minutes: minutes[id] ?? null })),
      settings,
      map_overlay: mapOverlay,
      delete_input: deleteInput,
    });
    set({ activeJob: job, activeLog: [], logOpen: false });
    get().watchJob(job.id);
    void get().refreshJobs();
    return job;
  },

  cancelActive: async () => {
    const { activeJob } = get();
    if (!activeJob) return;
    try {
      await api.cancelJob(activeJob.id);
    } catch {
      /* already finished */
    }
  },

  watchJob: (jobId) => {
    streamJob(jobId, {
      onProgress: (job) => {
        set({ activeJob: job });
      },
      onLog: (line) => {
        const log = [...get().activeLog, line];
        set({
          activeLog: log.length > MAX_UI_LOG ? log.slice(-MAX_UI_LOG) : log,
        });
      },
      onDone: () => {
        void get().refreshJobs();
        void get().refreshOutputs();
        const job = get().activeJob;
        if (job && (job.deleted_inputs.length > 0 || job.status === "completed")) {
          void get().refreshEvents();
        }
      },
      onError: () => {
        // EventSource reconnects automatically; refresh state as a fallback.
        void get().refreshJobs();
      },
    });
  },
}));

export function effectiveMinutes(
  event: DashcamEvent,
  minutes: Record<string, string[] | null>,
): string[] {
  const selection = minutes[event.id];
  return selection ?? event.minutes.map((minute) => minute.key);
}
