import { useState } from "react";
import { useStudio } from "../store";
import type { Settings } from "../types";
import { Badge, Card, SectionTitle, Segmented, Select, Slider, Toggle, cx } from "./ui";

/* ── Layout schematics ──────────────────────────────────────────────── */
function LayoutIcon({ layout }: { layout: string }) {
  const box = "fill-current";
  switch (layout) {
    case "FULLSCREEN":
      return (
        <svg viewBox="0 0 44 28" className="w-full h-8 text-current">
          <rect x="10" y="2" width="24" height="14" rx="1.5" className={box} />
          <rect x="4" y="18" width="10" height="8" rx="1.5" className={box} opacity="0.55" />
          <rect x="17" y="18" width="10" height="8" rx="1.5" className={box} opacity="0.55" />
          <rect x="30" y="18" width="10" height="8" rx="1.5" className={box} opacity="0.55" />
        </svg>
      );
    case "WIDESCREEN":
      return (
        <svg viewBox="0 0 44 28" className="w-full h-8 text-current">
          <rect x="4" y="2" width="36" height="16" rx="1.5" className={box} />
          <rect x="4" y="20" width="10" height="6" rx="1.5" className={box} opacity="0.55" />
          <rect x="17" y="20" width="10" height="6" rx="1.5" className={box} opacity="0.55" />
          <rect x="30" y="20" width="10" height="6" rx="1.5" className={box} opacity="0.55" />
        </svg>
      );
    case "MOSAIC":
      return (
        <svg viewBox="0 0 44 28" className="w-full h-8 text-current">
          {[0, 1, 2].map((column) => (
            <g key={column}>
              <rect x={4 + column * 13} y="2" width="11" height="11" rx="1.5" className={box} opacity="0.8" />
              <rect x={4 + column * 13} y="15" width="11" height="11" rx="1.5" className={box} opacity="0.55" />
            </g>
          ))}
        </svg>
      );
    case "PERSPECTIVE":
      return (
        <svg viewBox="0 0 44 28" className="w-full h-8 text-current">
          <polygon points="4,4 13,7 13,25 4,28" className={box} opacity="0.55" />
          <rect x="16" y="4" width="12" height="18" rx="1.5" className={box} />
          <polygon points="40,4 31,7 31,25 40,28" className={box} opacity="0.55" />
        </svg>
      );
    case "CROSS":
      return (
        <svg viewBox="0 0 44 28" className="w-full h-8 text-current">
          <rect x="15" y="1" width="14" height="9" rx="1.5" className={box} />
          <rect x="4" y="10" width="14" height="9" rx="1.5" className={box} opacity="0.55" />
          <rect x="26" y="10" width="14" height="9" rx="1.5" className={box} opacity="0.55" />
          <rect x="15" y="19" width="14" height="8" rx="1.5" className={box} opacity="0.7" />
        </svg>
      );
    case "DIAMOND":
      return (
        <svg viewBox="0 0 44 28" className="w-full h-8 text-current">
          <rect x="14" y="1" width="16" height="9" rx="1.5" className={box} />
          <rect x="2" y="9" width="11" height="9" rx="1.5" className={box} opacity="0.55" />
          <rect x="31" y="9" width="11" height="9" rx="1.5" className={box} opacity="0.55" />
          <rect x="14" y="18" width="16" height="9" rx="1.5" className={box} opacity="0.7" />
        </svg>
      );
    default: // HORIZONTAL
      return (
        <svg viewBox="0 0 44 28" className="w-full h-8 text-current">
          <rect x="2" y="9" width="9" height="10" rx="1.5" className={box} opacity="0.55" />
          <rect x="13" y="9" width="9" height="10" rx="1.5" className={box} />
          <rect x="24" y="9" width="9" height="10" rx="1.5" className={box} opacity="0.7" />
          <rect x="35" y="9" width="7" height="10" rx="1.5" className={box} opacity="0.55" />
        </svg>
      );
  }
}

const CAMERA_LABELS: Record<string, string> = {
  front: "Front",
  back: "Rear",
  left_repeater: "Left rptr",
  right_repeater: "Right rptr",
  left_pillar: "Left pillar",
  right_pillar: "Right pillar",
};

const QUALITY_PRESETS: Record<string, Partial<Settings>> = {
  draft: { quality: "LOWEST", compression: "ultrafast", encoding: "x264" },
  balanced: { quality: "LOWER", compression: "medium", encoding: "x264" },
  archive: { quality: "HIGH", compression: "slow", encoding: "x264" },
};

function presetOf(settings: Partial<Settings>): string {
  for (const [name, preset] of Object.entries(QUALITY_PRESETS)) {
    if (
      (settings.quality ?? "LOWER") === preset.quality &&
      (settings.compression ?? "medium") === preset.compression
    ) {
      return name;
    }
  }
  return "custom";
}

export function SettingsPanels() {
  const config = useStudio((state) => state.config);
  const events = useStudio((state) => state.events);
  const primaryId = useStudio((state) => state.primaryId);
  const settings = useStudio((state) => state.settings);
  const setSetting = useStudio((state) => state.setSetting);
  const toggleCamera = useStudio((state) => state.toggleCamera);
  const mapOverlay = useStudio((state) => state.mapOverlay);
  const setMapOverlay = useStudio((state) => state.setMapOverlay);
  const deleteInput = useStudio((state) => state.deleteInput);
  const setDeleteInput = useStudio((state) => state.setDeleteInput);

  const [qualityOpen, setQualityOpen] = useState(false);
  const [overlayOpen, setOverlayOpen] = useState(false);

  if (!config) return null;
  const defaults = config.defaults;
  const value = <K extends keyof Settings>(key: K): Settings[K] =>
    (settings[key] ?? defaults[key]) as Settings[K];

  const event = events.find((candidate) => candidate.id === primaryId) ?? null;
  const hasGps = event?.metadata?.lat != null && event?.metadata?.lon != null;
  const cameras = { ...defaults.cameras, ...(settings.cameras ?? {}) };
  const preset = presetOf(settings);
  const gpuOn = value("gpu") && config.gpu_available;

  return (
    <aside className="w-[340px] shrink-0 border-l border-edge/60 overflow-y-auto">
      <div className="p-4 space-y-4">
        {/* Layout */}
        <Card className="p-4">
          <SectionTitle>Layout</SectionTitle>
          <div className="grid grid-cols-3 gap-1.5">
            {config.layouts.map((layout) => (
              <button
                key={layout}
                type="button"
                onClick={() => setSetting("layout", layout)}
                className={cx(
                  "rounded-lg border p-2 pb-1.5 transition-all",
                  value("layout") === layout
                    ? "border-tesla/70 bg-tesla/10 text-tesla-hot"
                    : "border-edge text-fog hover:text-snow hover:border-fog/50",
                )}
              >
                <LayoutIcon layout={layout} />
                <div className="text-[9px] font-semibold mt-1 tracking-wide">
                  {layout}
                </div>
              </button>
            ))}
          </div>
          <div className="mt-3 space-y-2.5">
            <Toggle
              checked={value("perspective")}
              onChange={(checked) => setSetting("perspective", checked)}
              label="Perspective side cameras"
            />
            <div className="flex items-center justify-between">
              <span className="text-sm text-snow">Rear view</span>
              <Segmented
                value={value("view_mode")}
                onChange={(mode) => setSetting("view_mode", mode)}
                options={[
                  { value: "default", label: "Normal" },
                  { value: "mirror", label: "Mirrored" },
                  { value: "rear", label: "Rear-first" },
                ]}
              />
            </div>
            <Toggle
              checked={value("swap")}
              onChange={(checked) => setSetting("swap", checked)}
              label="Swap left/right cameras"
            />
            <div className="flex items-center justify-between">
              <span className="text-sm text-snow">Background</span>
              <input
                type="color"
                value={value("background")}
                onChange={(colorEvent) =>
                  setSetting("background", colorEvent.target.value)
                }
                className="w-14 h-7 rounded border border-edge bg-ink cursor-pointer"
              />
            </div>
          </div>
        </Card>

        {/* Cameras */}
        <Card className="p-4">
          <SectionTitle>Cameras</SectionTitle>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2.5">
            {config.cameras.map((camera) => (
              <Toggle
                key={camera}
                checked={cameras[camera] ?? true}
                onChange={() => toggleCamera(camera)}
                label={CAMERA_LABELS[camera] ?? camera}
              />
            ))}
          </div>
        </Card>

        {/* Quality */}
        <Card className="p-4">
          <SectionTitle
            hint={gpuOn ? "VAAPI hardware encode" : "CPU software encode"}
          >
            Quality
          </SectionTitle>
          <Segmented
            className="w-full"
            value={preset}
            onChange={(name) => {
              const chosen = QUALITY_PRESETS[name];
              if (!chosen) return;
              for (const [key, presetValue] of Object.entries(chosen)) {
                setSetting(
                  key as keyof Settings,
                  presetValue as Settings[keyof Settings],
                );
              }
            }}
            options={[
              { value: "draft", label: "Draft" },
              { value: "balanced", label: "Balanced" },
              { value: "archive", label: "Archive" },
              ...(preset === "custom"
                ? [{ value: "custom", label: "Custom" }]
                : []),
            ]}
          />
          {gpuOn ? (
            <div className="mt-3 flex items-center justify-between">
              <span className="text-sm text-snow">
                Bitrate{" "}
                <span className="text-[10px] text-fog">(GPU encode)</span>
              </span>
              <Select
                value={value("bitrate") ?? "default"}
                onChange={(bitrate) =>
                  setSetting("bitrate", bitrate === "default" ? null : bitrate)
                }
                options={[
                  { value: "default", label: "Auto (10M×scale)" },
                  { value: "4M", label: "4 Mbps — small" },
                  { value: "8M", label: "8 Mbps — good" },
                  { value: "14M", label: "14 Mbps — high" },
                  { value: "20M", label: "20 Mbps — max" },
                ]}
              />
            </div>
          ) : null}
          <button
            type="button"
            className="mt-3 text-[11px] text-fog hover:text-snow font-medium"
            onClick={() => setQualityOpen(!qualityOpen)}
          >
            {qualityOpen ? "▾ Hide" : "▸ Show"} advanced encoding
          </button>
          {qualityOpen ? (
            <div className="mt-3 space-y-2.5 border-t border-edge/60 pt-3">
              {(
                [
                  ["quality", "CRF quality", config.qualities],
                  ["compression", "Preset", config.compressions],
                  ["encoding", "Codec", config.encodings],
                ] as const
              ).map(([key, label, options]) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-sm text-snow">{label}</span>
                  <Select
                    value={String(value(key))}
                    onChange={(next) =>
                      setSetting(key, next as Settings[typeof key])
                    }
                    options={options.map((option) => ({
                      value: option,
                      label: option,
                    }))}
                  />
                </div>
              ))}
              {value("encoding") === "x265" ? (
                <div className="text-[11px] text-amber bg-amber/10 border border-amber/30 rounded-lg px-2.5 py-1.5">
                  x265 files may not play in the browser gallery.
                </div>
              ) : null}
              {gpuOn && value("quality") !== defaults.quality ? (
                <div className="text-[11px] text-fog">
                  Note: with VAAPI the CRF quality applies only to previews;
                  use bitrate above for output size.
                </div>
              ) : null}
              <div className="flex items-center justify-between">
                <span className="text-sm text-snow">FPS</span>
                <Select
                  value={String(value("fps"))}
                  onChange={(fps) => setSetting("fps", Number(fps))}
                  options={["24", "30", "33"].map((fps) => ({
                    value: fps,
                    label: fps,
                  }))}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-snow">Scale</span>
                <Select
                  value={String(value("scale") ?? "default")}
                  onChange={(scale) =>
                    setSetting("scale", scale === "default" ? null : Number(scale))
                  }
                  options={[
                    { value: "default", label: "Layout default" },
                    { value: "0.5", label: "0.5× — smaller" },
                    { value: "1", label: "1× — full" },
                    { value: "1.5", label: "1.5× — larger" },
                  ]}
                />
              </div>
              <Toggle
                checked={value("gpu")}
                onChange={(checked) => setSetting("gpu", checked)}
                disabled={!config.gpu_available}
                label={`GPU acceleration (${config.default_gpu_type})`}
                description={
                  config.gpu_available
                    ? undefined
                    : "No render node detected in the container"
                }
              />
            </div>
          ) : null}
        </Card>

        {/* Map burn-in */}
        <Card className="p-4">
          <SectionTitle hint={hasGps ? undefined : "no GPS in event.json"}>
            Map burn-in
          </SectionTitle>
          <Toggle
            checked={mapOverlay.enabled}
            onChange={(checked) => setMapOverlay({ enabled: checked })}
            disabled={!hasGps}
            label="Burn location map into video"
            description="OSM tile with the event location, composited after rendering. Disables merging."
            accent="green"
          />
          {mapOverlay.enabled ? (
            <div className="mt-3 space-y-3 border-t border-edge/60 pt-3">
              <div>
                <div className="text-xs text-fog mb-1.5">Corner</div>
                <div className="grid grid-cols-2 gap-1.5 w-32">
                  {(
                    [
                      ["top_left", "↖"],
                      ["top_right", "↗"],
                      ["bottom_left", "↙"],
                      ["bottom_right", "↘"],
                    ] as const
                  ).map(([corner, arrow]) => (
                    <button
                      key={corner}
                      type="button"
                      onClick={() => setMapOverlay({ corner })}
                      className={cx(
                        "h-9 rounded-lg border text-base transition-colors",
                        mapOverlay.corner === corner
                          ? "border-mint/70 bg-mint/10 text-mint"
                          : "border-edge text-fog hover:text-snow",
                      )}
                    >
                      {arrow}
                    </button>
                  ))}
                </div>
              </div>
              <Slider
                label="Size"
                value={mapOverlay.size_pct}
                onChange={(size_pct) => setMapOverlay({ size_pct })}
                min={0.1}
                max={0.4}
                step={0.02}
                format={(size) => `${Math.round(size * 100)}% width`}
              />
              <Slider
                label="Opacity"
                value={mapOverlay.opacity}
                onChange={(opacity) => setMapOverlay({ opacity })}
                min={0.3}
                max={1}
                step={0.05}
                format={(opacity) => `${Math.round(opacity * 100)}%`}
              />
              <Slider
                label="Zoom"
                value={mapOverlay.zoom}
                onChange={(zoom) => setMapOverlay({ zoom })}
                min={10}
                max={18}
                step={1}
              />
            </div>
          ) : null}
        </Card>

        {/* Timestamp overlay */}
        <Card className="p-4">
          <SectionTitle>Timestamp</SectionTitle>
          <Toggle
            checked={value("show_timestamp")}
            onChange={(checked) => setSetting("show_timestamp", checked)}
            label="Show timestamp on video"
          />
          {value("show_timestamp") ? (
            <button
              type="button"
              className="mt-2 text-[11px] text-fog hover:text-snow font-medium"
              onClick={() => setOverlayOpen(!overlayOpen)}
            >
              {overlayOpen ? "▾ Hide" : "▸ Show"} text options
            </button>
          ) : null}
          {value("show_timestamp") && overlayOpen ? (
            <div className="mt-3 space-y-2.5 border-t border-edge/60 pt-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-snow">Horizontal</span>
                <Segmented
                  value={value("halign") ?? "CENTER"}
                  onChange={(halign) => setSetting("halign", halign)}
                  options={[
                    { value: "LEFT", label: "Left" },
                    { value: "CENTER", label: "Center" },
                    { value: "RIGHT", label: "Right" },
                  ]}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-snow">Vertical</span>
                <Segmented
                  value={value("valign") ?? "BOTTOM"}
                  onChange={(valign) => setSetting("valign", valign)}
                  options={[
                    { value: "TOP", label: "Top" },
                    { value: "MIDDLE", label: "Middle" },
                    { value: "BOTTOM", label: "Bottom" },
                  ]}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-snow">Font size</span>
                <Select
                  value={String(value("fontsize") ?? "default")}
                  onChange={(size) =>
                    setSetting(
                      "fontsize",
                      size === "default" ? null : Number(size),
                    )
                  }
                  options={[
                    { value: "default", label: "Auto" },
                    { value: "16", label: "16" },
                    { value: "24", label: "24" },
                    { value: "32", label: "32" },
                    { value: "48", label: "48" },
                  ]}
                />
              </div>
            </div>
          ) : null}
        </Card>

        {/* Options */}
        <Card className="p-4 space-y-2.5">
          <SectionTitle>Options</SectionTitle>
          <Toggle
            checked={value("motion_only")}
            onChange={(checked) => setSetting("motion_only", checked)}
            label="Motion only"
            description="Fast-forward through idle Sentry footage"
          />
          <div className="flex items-center justify-between">
            <span className="text-sm text-snow">Speed</span>
            <Select
              value={
                settings.speedup
                  ? `x${settings.speedup}`
                  : settings.slowdown
                    ? `s${settings.slowdown}`
                    : "1"
              }
              onChange={(speed) => {
                setSetting("speedup", speed.startsWith("x") ? Number(speed.slice(1)) : null);
                setSetting("slowdown", speed.startsWith("s") ? Number(speed.slice(1)) : null);
              }}
              options={[
                { value: "s2", label: "0.5× slow" },
                { value: "1", label: "1× normal" },
                { value: "x2", label: "2× fast" },
                { value: "x4", label: "4× fast" },
                { value: "x8", label: "8× fast" },
              ]}
            />
          </div>
          <Toggle
            checked={value("merge") && !mapOverlay.enabled}
            onChange={(checked) => setSetting("merge", checked)}
            disabled={mapOverlay.enabled}
            label="Merge events into one movie"
            description={
              mapOverlay.enabled ? "Unavailable with map burn-in" : undefined
            }
          />
          <Toggle
            checked={value("skip_existing")}
            onChange={(checked) => setSetting("skip_existing", checked)}
            label="Skip already-created movies"
          />
          <Toggle
            checked={value("title_screen_map")}
            onChange={(checked) => setSetting("title_screen_map", checked)}
            label="Map title screen"
            description="Engine feature: opens the movie with a full-frame map"
          />
          <div className="border-t border-edge/60 pt-2.5">
            <Toggle
              checked={deleteInput}
              onChange={setDeleteInput}
              label={
                <span className="text-tesla-hot font-semibold">
                  Delete input after processing
                </span>
              }
              description="Source event folders are removed only after the output is verified"
            />
          </div>
        </Card>

        <div className="text-center pb-2">
          <Badge tone="neutral" className="opacity-60">
            engine {config.engine_version || "dev"} · {config.input_dir}
          </Badge>
        </div>
      </div>
    </aside>
  );
}
