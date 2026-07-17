import { api, eventTitle, formatBytes, reasonLabel } from "../api";
import { effectiveMinutes, useStudio } from "../store";
import type { DashcamEvent } from "../types";
import { Badge, Button, Spinner, cx } from "./ui";

const GROUPS = [
  { value: "All", label: "All" },
  { value: "SavedClips", label: "Saved" },
  { value: "SentryClips", label: "Sentry" },
  { value: "RecentClips", label: "Recent" },
];

const GROUP_TONES: Record<string, "red" | "blue" | "green" | "neutral"> = {
  SentryClips: "red",
  SavedClips: "blue",
  RecentClips: "green",
};

function EventCard({ event }: { event: DashcamEvent }) {
  const selectedIds = useStudio((state) => state.selectedIds);
  const primaryId = useStudio((state) => state.primaryId);
  const minutes = useStudio((state) => state.minutes);
  const selectEvent = useStudio((state) => state.selectEvent);

  const isSelected = selectedIds.includes(event.id);
  const isPrimary = primaryId === event.id;
  const selectedCount = effectiveMinutes(event, minutes).length;
  const reason = reasonLabel(event.metadata?.reason ?? null);

  return (
    <button
      type="button"
      onClick={(mouseEvent) =>
        selectEvent(event.id, mouseEvent.metaKey || mouseEvent.ctrlKey)
      }
      className={cx(
        "w-full text-left rounded-xl border transition-all duration-150 overflow-hidden group",
        isPrimary
          ? "border-tesla/70 bg-tesla/5 shadow-lg shadow-tesla/10"
          : isSelected
            ? "border-tesla/40 bg-raised"
            : "border-edge/60 bg-surface hover:border-fog/40 hover:bg-raised/60",
      )}
    >
      <div className="flex gap-3 p-2.5">
        <div className="relative w-24 h-16 shrink-0 rounded-lg overflow-hidden bg-ink">
          <img
            src={api.eventThumbUrl(event.id)}
            alt=""
            loading="lazy"
            className="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity"
            onError={(imgEvent) => {
              (imgEvent.target as HTMLImageElement).style.visibility = "hidden";
            }}
          />
          {isSelected ? (
            <span className="absolute top-1 left-1 w-4 h-4 rounded-full bg-tesla text-white text-[10px] font-bold flex items-center justify-center shadow">
              ✓
            </span>
          ) : null}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-semibold text-snow truncate">
            {eventTitle(event.name)}
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            <Badge tone={GROUP_TONES[event.group] ?? "neutral"}>
              {event.group.replace("Clips", "")}
            </Badge>
            {reason ? <Badge>{reason}</Badge> : null}
            {event.metadata?.lat != null ? <Badge tone="green">GPS</Badge> : null}
          </div>
          <div className="mt-1.5 text-[11px] text-fog">
            {event.minute_count} min · {formatBytes(event.total_size)}
            {event.metadata?.city ? ` · ${event.metadata.city}` : ""}
            {isSelected && selectedCount !== event.minute_count
              ? ` · ${selectedCount} selected`
              : ""}
          </div>
        </div>
      </div>
    </button>
  );
}

export function EventBrowser() {
  const events = useStudio((state) => state.events);
  const loading = useStudio((state) => state.eventsLoading);
  const error = useStudio((state) => state.eventsError);
  const groupFilter = useStudio((state) => state.groupFilter);
  const setGroupFilter = useStudio((state) => state.setGroupFilter);
  const refreshEvents = useStudio((state) => state.refreshEvents);
  const selectedIds = useStudio((state) => state.selectedIds);

  const visible =
    groupFilter === "All"
      ? events
      : events.filter((event) => event.group === groupFilter);

  return (
    <aside className="w-[320px] shrink-0 border-r border-edge/60 flex flex-col min-h-0">
      <div className="p-3 pb-2 space-y-2.5">
        <div className="flex items-center justify-between">
          <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-fog">
            Events
          </h2>
          <Button size="sm" variant="ghost" onClick={() => void refreshEvents()}>
            {loading ? <Spinner className="w-3 h-3" /> : "↻"} Rescan
          </Button>
        </div>
        <div className="flex gap-1">
          {GROUPS.map((group) => (
            <button
              key={group.value}
              type="button"
              onClick={() => setGroupFilter(group.value)}
              className={cx(
                "px-2.5 py-1 rounded-full text-xs font-semibold transition-colors border",
                groupFilter === group.value
                  ? "bg-snow text-ink border-snow"
                  : "text-fog border-edge hover:text-snow hover:border-fog/50",
              )}
            >
              {group.label}
            </button>
          ))}
        </div>
        {selectedIds.length > 1 ? (
          <div className="text-[11px] text-fog">
            {selectedIds.length} events selected — settings apply to all.
          </div>
        ) : (
          <div className="text-[11px] text-fog/60">
            ⌘/Ctrl-click to select multiple events.
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-2">
        {error ? (
          <div className="text-xs text-tesla-hot bg-tesla/10 border border-tesla/30 rounded-lg p-3">
            {error}
          </div>
        ) : null}
        {loading && events.length === 0 ? (
          <>
            <div className="h-20 rounded-xl shimmer" />
            <div className="h-20 rounded-xl shimmer" />
            <div className="h-20 rounded-xl shimmer" />
          </>
        ) : null}
        {!loading && visible.length === 0 && !error ? (
          <div className="text-xs text-fog p-4 text-center border border-dashed border-edge rounded-xl">
            No events found in the input folder.
          </div>
        ) : null}
        {visible.map((event) => (
          <EventCard key={event.id} event={event} />
        ))}
      </div>
    </aside>
  );
}
