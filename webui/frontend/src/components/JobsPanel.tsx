import { useEffect, useRef } from "react";
import { formatBytes, formatDuration } from "../api";
import { useStudio } from "../store";
import { Badge, Button, Card, Spinner, cx } from "./ui";

const PHASE_LABELS: Record<string, string> = {
  starting: "Starting engine",
  scanning: "Scanning folders",
  processing: "Encoding clips",
  assembling: "Assembling event movie",
  merging: "Merging movies",
  map_overlay: "Burning in map",
  cleanup: "Cleaning up input",
  done: "Done",
};

function Terminal() {
  const activeLog = useStudio((state) => state.activeLog);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeLog.length]);

  return (
    <div className="bg-ink border border-edge rounded-lg max-h-56 overflow-y-auto p-3 font-mono text-[11px] leading-relaxed">
      {activeLog.length === 0 ? (
        <span className="text-fog/60">Waiting for engine output…</span>
      ) : (
        activeLog.map((line, index) => (
          <div
            key={index}
            className={cx(
              "whitespace-pre-wrap break-all",
              /error/i.test(line) ? "text-tesla-hot" : "text-fog",
            )}
          >
            {line || " "}
          </div>
        ))
      )}
      <div ref={endRef} />
    </div>
  );
}

export function JobsPanel() {
  const job = useStudio((state) => state.activeJob);
  const logOpen = useStudio((state) => state.logOpen);
  const setLogOpen = useStudio((state) => state.setLogOpen);
  const cancelActive = useStudio((state) => state.cancelActive);
  const setTab = useStudio((state) => state.setTab);

  if (!job) return null;
  const progress = job.progress;
  const running = job.status === "running" || job.status === "queued";
  const elapsed =
    job.started_at != null
      ? (job.finished_at ?? Date.now() / 1000) - job.started_at
      : null;

  const statusTone =
    job.status === "completed"
      ? "green"
      : job.status === "failed"
        ? "red"
        : job.status === "cancelled"
          ? "amber"
          : "blue";

  return (
    <Card
      className={cx(
        "p-4 space-y-3",
        running && "border-tesla/40 shadow-lg shadow-tesla/5",
      )}
    >
      <div className="flex items-center gap-3">
        {running ? <Spinner /> : null}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-snow">
              {running
                ? PHASE_LABELS[progress.phase] ?? progress.phase
                : job.status === "completed"
                  ? "Render complete"
                  : job.status === "failed"
                    ? "Render failed"
                    : "Cancelled"}
            </span>
            <Badge tone={statusTone}>{job.status}</Badge>
          </div>
          <div className="text-[11px] text-fog truncate mt-0.5">
            {job.request.event_names.join(", ")}
            {progress.total_events > 1 && running
              ? ` — event ${Math.max(progress.current_event, 1)}/${progress.total_events}`
              : ""}
            {running && progress.clips_in_event > 0
              ? `, clip ${Math.max(progress.clip_in_event, 1)}/${progress.clips_in_event}`
              : ""}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-lg font-bold tabular-nums text-snow">
            {Math.round(progress.percent)}%
          </div>
          <div className="text-[10px] text-fog tabular-nums">
            {elapsed != null ? formatDuration(elapsed) : ""}
            {running && progress.eta_seconds != null
              ? ` · ~${formatDuration(progress.eta_seconds)} left`
              : ""}
          </div>
        </div>
      </div>

      <div className="h-2 rounded-full bg-ink overflow-hidden border border-edge/60">
        <div
          className={cx(
            "h-full rounded-full transition-all duration-500",
            job.status === "failed"
              ? "bg-tesla/70"
              : job.status === "completed"
                ? "bg-mint"
                : "bg-tesla progress-active",
          )}
          style={{ width: `${Math.max(progress.percent, 2)}%` }}
        />
      </div>

      <div className="text-xs text-fog">{progress.message}</div>

      {progress.warnings.length > 0 ? (
        <div className="text-[11px] text-amber bg-amber/10 border border-amber/30 rounded-lg px-3 py-2 space-y-0.5">
          {progress.warnings.slice(-3).map((warning, index) => (
            <div key={index}>{warning}</div>
          ))}
        </div>
      ) : null}

      {job.error ? (
        <pre className="text-[11px] text-tesla-hot bg-tesla/10 border border-tesla/30 rounded-lg px-3 py-2 whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
          {job.error}
        </pre>
      ) : null}

      {job.status === "completed" ? (
        <div className="flex items-center gap-2 text-xs text-fog flex-wrap">
          <span className="text-mint font-semibold">
            {job.outputs.length} video{job.outputs.length === 1 ? "" : "s"} ready
          </span>
          {job.freed_bytes > 0 ? (
            <span>· freed {formatBytes(job.freed_bytes)} of input</span>
          ) : null}
          {job.delete_skipped.length > 0 ? (
            <span className="text-amber">
              · kept {job.delete_skipped.join(", ")} (unverified)
            </span>
          ) : null}
          <Button size="sm" variant="secondary" onClick={() => setTab("outputs")}>
            View in gallery →
          </Button>
        </div>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setLogOpen(!logOpen)}
          className="text-[11px] text-fog hover:text-snow font-medium"
        >
          {logOpen ? "▾ Hide" : "▸ Show"} engine log
        </button>
        <div className="flex-1" />
        {running ? (
          <Button size="sm" variant="danger" onClick={() => void cancelActive()}>
            Cancel
          </Button>
        ) : null}
      </div>

      {logOpen ? <Terminal /> : null}
    </Card>
  );
}
