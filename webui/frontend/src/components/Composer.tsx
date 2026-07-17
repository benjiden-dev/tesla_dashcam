import { useEffect, useMemo, useRef, useState } from "react";
import { api, eventTitle, formatBytes, formatDuration, reasonLabel } from "../api";
import { effectiveMinutes, useStudio } from "../store";
import type { DashcamEvent } from "../types";
import { Badge, Button, Card, SectionTitle, Spinner, cx } from "./ui";
import { JobsPanel } from "./JobsPanel";

/* ── Minute timeline ────────────────────────────────────────────────── */
function MinuteTimeline({ event }: { event: DashcamEvent }) {
  const minutes = useStudio((state) => state.minutes);
  const toggleMinute = useStudio((state) => state.toggleMinute);
  const setMinutes = useStudio((state) => state.setMinutes);

  const selected = new Set(effectiveMinutes(event, minutes));
  const allSelected = selected.size === event.minute_count;

  return (
    <Card className="p-4">
      <SectionTitle
        hint={`${selected.size}/${event.minute_count} minutes · ~${formatDuration(selected.size * 60)} of footage`}
      >
        Minutes to include
      </SectionTitle>
      <div className="flex flex-wrap gap-1.5">
        {event.minutes.map((minute) => {
          const isOn = selected.has(minute.key);
          return (
            <button
              key={minute.key}
              type="button"
              onClick={() => toggleMinute(event.id, minute.key)}
              title={`${minute.cameras.length} cameras · ${formatBytes(minute.size)}`}
              className={cx(
                "px-2.5 py-1.5 rounded-lg border text-xs font-mono font-medium transition-all",
                isOn
                  ? "border-tesla/70 bg-tesla/15 text-snow shadow-sm shadow-tesla/20"
                  : "border-edge bg-ink text-fog hover:text-snow hover:border-fog/50 line-through decoration-fog/40",
              )}
            >
              {minute.time.slice(0, 5)}
              <span
                className={cx(
                  "ml-1.5 text-[9px] align-middle",
                  isOn ? "text-tesla-hot" : "text-fog/50",
                )}
              >
                {minute.cameras.length}cam
              </span>
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex gap-2">
        <Button size="sm" variant="ghost" onClick={() => setMinutes(event.id, null)}>
          Select all
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={selected.size <= 1}
          onClick={() =>
            setMinutes(event.id, [event.minutes[event.minutes.length - 1]!.key])
          }
        >
          Last minute only
        </Button>
        {!allSelected ? (
          <span className="text-[11px] text-fog self-center">
            Skipped minutes are excluded from the video.
          </span>
        ) : null}
      </div>
    </Card>
  );
}

/* ── First-frame preview ────────────────────────────────────────────── */
function PreviewPane({ event }: { event: DashcamEvent }) {
  const minutes = useStudio((state) => state.minutes);
  const settings = useStudio((state) => state.settings);
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef(0);

  const firstMinute = effectiveMinutes(event, minutes)[0] ?? null;

  const visualKey = useMemo(
    () =>
      JSON.stringify([
        event.id,
        firstMinute,
        settings.layout,
        settings.perspective,
        settings.view_mode,
        settings.swap,
        settings.background,
        settings.cameras,
        settings.show_timestamp,
        settings.scale,
      ]),
    [event.id, firstMinute, settings],
  );

  useEffect(() => {
    if (!firstMinute) {
      setUrl(null);
      return;
    }
    const requestId = ++requestRef.current;
    setLoading(true);
    setError(null);
    const timer = setTimeout(() => {
      api
        .preview(event.id, firstMinute, settings as Record<string, unknown>)
        .then((result) => {
          if (requestRef.current !== requestId) return;
          setUrl(result.url);
          setLoading(false);
        })
        .catch((previewError: Error) => {
          if (requestRef.current !== requestId) return;
          setError(previewError.message);
          setLoading(false);
        });
    }, 700);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visualKey]);

  return (
    <Card className="overflow-hidden">
      <div className="relative aspect-video bg-ink">
        {url ? (
          <img
            src={url}
            alt="Layout preview"
            className={cx(
              "w-full h-full object-contain transition-opacity duration-300",
              loading ? "opacity-40" : "opacity-100",
            )}
          />
        ) : (
          <div
            className={cx(
              "absolute inset-0",
              loading ? "shimmer" : "bg-ink",
            )}
          />
        )}
        {loading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="flex items-center gap-2 bg-ink/80 border border-edge rounded-full px-3 py-1.5 text-xs text-fog">
              <Spinner className="w-3 h-3" /> Rendering preview through the engine…
            </div>
          </div>
        ) : null}
        {!loading && !url && !error ? (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-fog">
            Select at least one minute to preview.
          </div>
        ) : null}
        {error ? (
          <div className="absolute inset-x-3 bottom-3 text-[11px] text-tesla-hot bg-tesla/10 border border-tesla/30 rounded-lg px-3 py-2">
            Preview failed: {error}
          </div>
        ) : null}
      </div>
      <div className="px-4 py-2.5 flex items-center justify-between border-t border-edge/60">
        <span className="text-[11px] text-fog">
          First frame of{" "}
          <span className="text-snow font-mono">
            {firstMinute ? firstMinute.slice(11).replace(/-/g, ":") : "—"}
          </span>{" "}
          rendered with the actual layout engine
        </span>
        <Badge tone="neutral">exact composite</Badge>
      </div>
    </Card>
  );
}

/* ── Run bar ────────────────────────────────────────────────────────── */
function RunBar() {
  const events = useStudio((state) => state.events);
  const selectedIds = useStudio((state) => state.selectedIds);
  const minutes = useStudio((state) => state.minutes);
  const settings = useStudio((state) => state.settings);
  const mapOverlay = useStudio((state) => state.mapOverlay);
  const deleteInput = useStudio((state) => state.deleteInput);
  const activeJob = useStudio((state) => state.activeJob);
  const run = useStudio((state) => state.run);

  const [confirming, setConfirming] = useState(false);
  const [cli, setCli] = useState<string | null>(null);
  const [cliOpen, setCliOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedEvents = events.filter((event) => selectedIds.includes(event.id));
  const totalMinutes = selectedEvents.reduce(
    (sum, event) => sum + effectiveMinutes(event, minutes).length,
    0,
  );
  const speedup = Number(settings.speedup) || 1;
  const busy =
    activeJob != null && ["queued", "running"].includes(activeJob.status);

  const openCli = async () => {
    const next = !cliOpen;
    setCliOpen(next);
    if (next) {
      try {
        const result = await api.cliPreview(
          settings as Record<string, unknown>,
          mapOverlay as unknown as Record<string, unknown>,
        );
        setCli(result.cli);
      } catch (cliError) {
        setCli(String(cliError));
      }
    }
  };

  const start = async () => {
    setConfirming(false);
    setError(null);
    try {
      await run();
    } catch (runError) {
      setError((runError as Error).message);
    }
  };

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center gap-3">
        <Button
          variant="primary"
          size="lg"
          disabled={totalMinutes === 0 || busy}
          onClick={() => (deleteInput ? setConfirming(true) : void start())}
          className="min-w-44"
        >
          {busy ? (
            <>
              <Spinner className="border-white/40 border-t-white" /> Processing…
            </>
          ) : (
            <>▶ Create video{selectedEvents.length > 1 ? "s" : ""}</>
          )}
        </Button>
        <div className="text-xs text-fog leading-relaxed">
          <div>
            {selectedEvents.length} event{selectedEvents.length === 1 ? "" : "s"} ·{" "}
            {totalMinutes} minute{totalMinutes === 1 ? "" : "s"} · ~
            {formatDuration((totalMinutes * 60) / speedup)} output
          </div>
          <div className="flex gap-1.5 mt-1">
            {mapOverlay.enabled ? <Badge tone="green">map burn-in</Badge> : null}
            {deleteInput ? <Badge tone="red">deletes input</Badge> : null}
            {settings.merge !== false && !mapOverlay.enabled && selectedEvents.length > 1 ? (
              <Badge>merged</Badge>
            ) : null}
          </div>
        </div>
        <div className="flex-1" />
        <Button size="sm" variant="ghost" onClick={() => void openCli()}>
          {cliOpen ? "Hide" : "Show"} CLI
        </Button>
      </div>

      {error ? (
        <div className="text-xs text-tesla-hot bg-tesla/10 border border-tesla/30 rounded-lg px-3 py-2">
          {error}
        </div>
      ) : null}

      {cliOpen ? (
        <pre className="text-[11px] font-mono text-fog bg-ink border border-edge rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-all">
          {cli ?? "…"}
        </pre>
      ) : null}

      {confirming ? (
        <div className="border border-tesla/40 bg-tesla/5 rounded-xl p-4 space-y-3">
          <div className="text-sm font-semibold text-snow">
            Delete source footage after processing?
          </div>
          <div className="text-xs text-fog leading-relaxed">
            After a verified successful render, the entire source folder
            {selectedEvents.length > 1 ? "s" : ""} for{" "}
            <span className="text-snow">
              {selectedEvents.map((event) => event.name).join(", ")}
            </span>{" "}
            will be permanently deleted — including any minutes you did not
            select. Deletion is skipped automatically if the output cannot be
            verified.
          </div>
          <div className="flex gap-2">
            <Button variant="danger" onClick={() => void start()}>
              Process & delete input
            </Button>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
    </Card>
  );
}

/* ── Event header ───────────────────────────────────────────────────── */
function EventHeader({ event }: { event: DashcamEvent }) {
  const metadata = event.metadata;
  const reason = reasonLabel(metadata?.reason ?? null);
  return (
    <div className="flex items-start gap-4">
      <div className="flex-1 min-w-0">
        <h1 className="text-xl font-bold text-snow tracking-tight">
          {eventTitle(event.name)}
        </h1>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-fog">
          <Badge tone={event.group === "SentryClips" ? "red" : "blue"}>
            {event.group.replace("Clips", "")}
          </Badge>
          {reason ? <Badge>{reason}</Badge> : null}
          {metadata?.city ? (
            <span>
              {metadata.street ? `${metadata.street}, ` : ""}
              {metadata.city}
            </span>
          ) : null}
          <span>
            · {event.minute_count} min · {formatBytes(event.total_size)}
          </span>
        </div>
      </div>
      {metadata?.lat != null && metadata?.lon != null ? (
        <img
          src={api.mapPreviewUrl(event.id, 240, 14)}
          alt="Event location"
          className="w-24 h-24 rounded-xl border border-edge object-cover shrink-0"
          onError={(imgEvent) => {
            (imgEvent.target as HTMLImageElement).style.display = "none";
          }}
        />
      ) : null}
    </div>
  );
}

/* ── Composer (main column) ─────────────────────────────────────────── */
export function Composer() {
  const events = useStudio((state) => state.events);
  const primaryId = useStudio((state) => state.primaryId);
  const activeJob = useStudio((state) => state.activeJob);

  const event = events.find((candidate) => candidate.id === primaryId) ?? null;

  return (
    <main className="flex-1 min-w-0 overflow-y-auto">
      <div className="max-w-3xl mx-auto p-5 space-y-4">
        {activeJob ? <JobsPanel /> : null}
        {event ? (
          <>
            <EventHeader event={event} />
            <MinuteTimeline event={event} />
            <PreviewPane event={event} />
            <RunBar />
          </>
        ) : (
          <div className="pt-24 text-center space-y-3">
            <div className="text-5xl">🎬</div>
            <h2 className="text-lg font-semibold text-snow">
              Pick an event to get started
            </h2>
            <p className="text-sm text-fog max-w-sm mx-auto leading-relaxed">
              Choose a Saved, Sentry or Recent event from the left, select the
              minutes you care about, tune the layout — then render it into a
              single video.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
