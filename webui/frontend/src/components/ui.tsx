import type { ReactNode } from "react";
import { useEffect } from "react";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

/* ── Button ─────────────────────────────────────────────────────────── */
export function Button({
  variant = "secondary",
  size = "md",
  className,
  disabled,
  onClick,
  children,
  title,
}: {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  className?: string;
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
  title?: string;
}) {
  const base =
    "inline-flex items-center justify-center gap-2 font-semibold rounded-lg transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-tesla/60 disabled:opacity-40 disabled:cursor-not-allowed select-none";
  const sizes = {
    sm: "px-2.5 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-3 text-base",
  };
  const variants = {
    primary:
      "bg-tesla text-white hover:bg-tesla-hot shadow-lg shadow-tesla/25 active:scale-[0.98]",
    secondary:
      "bg-raised text-snow border border-edge hover:border-fog/50 hover:bg-edge/60 active:scale-[0.98]",
    ghost: "text-fog hover:text-snow hover:bg-raised",
    danger:
      "bg-transparent text-tesla border border-tesla/40 hover:bg-tesla/10 active:scale-[0.98]",
  };
  return (
    <button
      type="button"
      title={title}
      className={cx(base, sizes[size], variants[variant], className)}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

/* ── Card ───────────────────────────────────────────────────────────── */
export function Card({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cx(
        "bg-surface border border-edge/70 rounded-xl",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  children,
  hint,
}: {
  children: ReactNode;
  hint?: string;
}) {
  return (
    <div className="flex items-baseline justify-between mb-3">
      <h3 className="text-[11px] font-bold uppercase tracking-[0.14em] text-fog">
        {children}
      </h3>
      {hint ? <span className="text-[11px] text-fog/70">{hint}</span> : null}
    </div>
  );
}

/* ── Toggle ─────────────────────────────────────────────────────────── */
export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled,
  accent = "red",
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
  accent?: "red" | "green";
}) {
  return (
    <label
      className={cx(
        "flex items-start gap-3 cursor-pointer group",
        disabled && "opacity-40 cursor-not-allowed",
      )}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx(
          "relative shrink-0 w-9 h-5 mt-0.5 rounded-full transition-colors duration-150",
          checked
            ? accent === "green"
              ? "bg-mint"
              : "bg-tesla"
            : "bg-edge group-hover:bg-edge/70",
        )}
      >
        <span
          className={cx(
            "absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform duration-150 shadow",
            checked && "translate-x-4",
          )}
        />
      </button>
      <span className="min-w-0">
        <span className="block text-sm text-snow leading-5">{label}</span>
        {description ? (
          <span className="block text-xs text-fog mt-0.5">{description}</span>
        ) : null}
      </span>
    </label>
  );
}

/* ── Select ─────────────────────────────────────────────────────────── */
export function Select({
  value,
  onChange,
  options,
  disabled,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
  className?: string;
}) {
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
      className={cx(
        "bg-raised border border-edge rounded-lg px-3 py-1.5 text-sm text-snow",
        "focus:outline-none focus:border-tesla/60 disabled:opacity-40 cursor-pointer",
        className,
      )}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

/* ── Segmented control ──────────────────────────────────────────────── */
export function Segmented({
  value,
  onChange,
  options,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: ReactNode }[];
  className?: string;
}) {
  return (
    <div
      className={cx(
        "inline-flex bg-ink border border-edge rounded-lg p-0.5 gap-0.5",
        className,
      )}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cx(
            "px-3 py-1.5 text-xs font-semibold rounded-md transition-colors",
            value === option.value
              ? "bg-raised text-snow shadow border border-edge"
              : "text-fog hover:text-snow",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/* ── Slider ─────────────────────────────────────────────────────────── */
export function Slider({
  value,
  onChange,
  min,
  max,
  step,
  label,
  format,
  disabled,
}: {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step: number;
  label: string;
  format?: (value: number) => string;
  disabled?: boolean;
}) {
  return (
    <div className={cx("space-y-1", disabled && "opacity-40")}>
      <div className="flex justify-between text-xs">
        <span className="text-fog">{label}</span>
        <span className="text-snow font-medium tabular-nums">
          {format ? format(value) : value}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full h-1.5 rounded-full appearance-none bg-edge accent-tesla cursor-pointer"
      />
    </div>
  );
}

/* ── Badge ──────────────────────────────────────────────────────────── */
export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "red" | "green" | "amber" | "blue";
  className?: string;
}) {
  const tones = {
    neutral: "bg-raised text-fog border-edge",
    red: "bg-tesla/10 text-tesla-hot border-tesla/30",
    green: "bg-mint/10 text-mint border-mint/30",
    amber: "bg-amber/10 text-amber border-amber/30",
    blue: "bg-sky-500/10 text-sky-400 border-sky-500/30",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border whitespace-nowrap",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ── Spinner ────────────────────────────────────────────────────────── */
export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cx(
        "inline-block w-4 h-4 border-2 border-fog/40 border-t-snow rounded-full animate-spin",
        className,
      )}
    />
  );
}

/* ── Modal ──────────────────────────────────────────────────────────── */
export function Modal({
  open,
  onClose,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className={cx(
          "bg-surface border border-edge rounded-2xl shadow-2xl w-full max-h-[90vh] overflow-auto",
          wide ? "max-w-5xl" : "max-w-lg",
        )}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
