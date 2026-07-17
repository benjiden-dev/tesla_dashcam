import { useEffect } from "react";
import { useStudio } from "./store";
import { Composer } from "./components/Composer";
import { EventBrowser } from "./components/EventBrowser";
import { OutputsGallery } from "./components/OutputsGallery";
import { SettingsPanels } from "./components/SettingsPanels";
import { Badge, cx } from "./components/ui";

function Header() {
  const tab = useStudio((state) => state.tab);
  const setTab = useStudio((state) => state.setTab);
  const config = useStudio((state) => state.config);
  const activeJob = useStudio((state) => state.activeJob);
  const outputs = useStudio((state) => state.outputs);

  const jobRunning =
    activeJob != null && ["queued", "running"].includes(activeJob.status);

  return (
    <header className="h-14 shrink-0 border-b border-edge/60 flex items-center px-4 gap-5 bg-surface/50 backdrop-blur">
      <div className="flex items-center gap-2.5">
        <span className="w-8 h-8 rounded-lg bg-tesla flex items-center justify-center text-white font-black text-base shadow-lg shadow-tesla/30">
          T
        </span>
        <div className="leading-tight">
          <div className="text-sm font-extrabold tracking-tight text-snow">
            Dashcam Studio
          </div>
          <div className="text-[10px] text-fog -mt-0.5">tesla_dashcam web UI</div>
        </div>
      </div>

      <nav className="flex gap-1 ml-4">
        {(
          [
            ["create", "Create"],
            ["outputs", "Outputs"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={cx(
              "px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-colors relative",
              tab === key
                ? "bg-raised text-snow border border-edge"
                : "text-fog hover:text-snow",
            )}
          >
            {label}
            {key === "outputs" && outputs.length > 0 ? (
              <span className="ml-1.5 text-[10px] text-fog">{outputs.length}</span>
            ) : null}
            {key === "create" && jobRunning ? (
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-tesla animate-pulse" />
            ) : null}
          </button>
        ))}
      </nav>

      <div className="flex-1" />

      {config ? (
        <Badge tone={config.gpu_available ? "green" : "amber"}>
          {config.gpu_available
            ? `VAAPI · ${config.render_node.split("/").pop()}`
            : "CPU encode"}
        </Badge>
      ) : null}
    </header>
  );
}

export default function App() {
  const init = useStudio((state) => state.init);
  const tab = useStudio((state) => state.tab);

  useEffect(() => {
    void init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="h-full flex flex-col">
      <Header />
      <div className="flex-1 flex min-h-0">
        <EventBrowser />
        {tab === "create" ? (
          <>
            <Composer />
            <SettingsPanels />
          </>
        ) : (
          <OutputsGallery />
        )}
      </div>
    </div>
  );
}
