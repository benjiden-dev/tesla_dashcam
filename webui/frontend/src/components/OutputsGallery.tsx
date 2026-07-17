import { useState } from "react";
import { api, formatBytes } from "../api";
import { useStudio } from "../store";
import type { OutputFile } from "../types";
import { Badge, Button, Card, Modal, Spinner, cx } from "./ui";

function PlayerModal({
  file,
  onClose,
}: {
  file: OutputFile;
  onClose: () => void;
}) {
  return (
    <Modal open onClose={onClose} wide>
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm font-bold text-snow truncate">{file.name}</div>
            <div className="text-[11px] text-fog">
              {formatBytes(file.size)} ·{" "}
              {new Date(file.mtime * 1000).toLocaleString()}
            </div>
          </div>
          <div className="flex gap-2 shrink-0">
            <a
              href={api.outputFileUrl(file.path)}
              download={file.name}
              className="inline-flex items-center px-4 py-2 text-sm font-semibold rounded-lg bg-raised text-snow border border-edge hover:border-fog/50"
            >
              ⬇ Download
            </a>
            <Button variant="ghost" onClick={onClose}>
              ✕
            </Button>
          </div>
        </div>
        {file.playable ? (
          <video
            src={api.outputFileUrl(file.path)}
            controls
            autoPlay
            className="w-full rounded-xl bg-black max-h-[70vh]"
          />
        ) : (
          <div className="p-10 text-center text-sm text-fog border border-dashed border-edge rounded-xl">
            This file type may not play in the browser — download it instead.
          </div>
        )}
      </div>
    </Modal>
  );
}

function OutputCard({ file }: { file: OutputFile }) {
  const [playing, setPlaying] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const refreshOutputs = useStudio((state) => state.refreshOutputs);

  const remove = async () => {
    try {
      await api.deleteOutput(file.path);
    } finally {
      setConfirming(false);
      void refreshOutputs();
    }
  };

  return (
    <>
      <Card className="overflow-hidden group">
        <button
          type="button"
          className="relative w-full aspect-video bg-ink block"
          onClick={() => setPlaying(true)}
        >
          <img
            src={api.outputThumbUrl(file.path, file.mtime)}
            alt=""
            loading="lazy"
            className="w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity"
            onError={(imgEvent) => {
              (imgEvent.target as HTMLImageElement).style.visibility = "hidden";
            }}
          />
          <span className="absolute inset-0 flex items-center justify-center">
            <span className="w-12 h-12 rounded-full bg-black/60 border border-white/20 backdrop-blur flex items-center justify-center text-white text-lg opacity-0 group-hover:opacity-100 transition-opacity">
              ▶
            </span>
          </span>
          {!file.playable ? (
            <Badge tone="amber" className="absolute top-2 right-2">
              x265
            </Badge>
          ) : null}
        </button>
        <div className="p-3">
          <div
            className="text-[12px] font-semibold text-snow truncate"
            title={file.name}
          >
            {file.name}
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span className="text-[11px] text-fog">
              {formatBytes(file.size)} ·{" "}
              {new Date(file.mtime * 1000).toLocaleDateString()}
            </span>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <a
                href={api.outputFileUrl(file.path)}
                download={file.name}
                className="text-fog hover:text-snow text-xs px-1.5 py-0.5"
                title="Download"
              >
                ⬇
              </a>
              <button
                type="button"
                onClick={() => setConfirming(true)}
                className="text-fog hover:text-tesla-hot text-xs px-1.5 py-0.5"
                title="Delete"
              >
                🗑
              </button>
            </div>
          </div>
        </div>
      </Card>

      {playing ? <PlayerModal file={file} onClose={() => setPlaying(false)} /> : null}

      <Modal open={confirming} onClose={() => setConfirming(false)}>
        <div className="p-5 space-y-4">
          <div className="text-sm font-bold text-snow">Delete this video?</div>
          <div className="text-xs text-fog break-all">{file.path}</div>
          <div className="flex gap-2">
            <Button variant="danger" onClick={() => void remove()}>
              Delete
            </Button>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

export function OutputsGallery() {
  const outputs = useStudio((state) => state.outputs);
  const loading = useStudio((state) => state.outputsLoading);
  const refreshOutputs = useStudio((state) => state.refreshOutputs);

  return (
    <main className="flex-1 min-w-0 overflow-y-auto">
      <div className="max-w-5xl mx-auto p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-snow tracking-tight">Outputs</h1>
            <p className="text-xs text-fog mt-0.5">
              Rendered videos — click to play in the browser.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => void refreshOutputs()}>
            {loading ? <Spinner className="w-3 h-3" /> : "↻"} Refresh
          </Button>
        </div>

        {outputs.length === 0 ? (
          <div
            className={cx(
              "p-16 text-center text-sm text-fog border border-dashed border-edge rounded-2xl",
              loading && "shimmer",
            )}
          >
            {loading ? "" : "No rendered videos yet — create one from an event."}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
            {outputs.map((file) => (
              <OutputCard key={file.path} file={file} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
