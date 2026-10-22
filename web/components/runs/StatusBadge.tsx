import { Badge, type Tone } from "@/components/ui";

const STATUS: Record<string, { tone: Tone; label: string }> = {
  queued: { tone: "neutral", label: "Queued" },
  running: { tone: "neutral", label: "Running" },
  succeeded: { tone: "ok", label: "Succeeded" },
  failed: { tone: "danger", label: "Failed" },
  cancelled: { tone: "neutral", label: "Cancelled" },
  stopped_at_budget: { tone: "warn", label: "Stopped at budget" },
};

/** Every status carries a glyph as well as a word, so colour never carries it alone. */
export function StatusGlyph({ status }: { status: string }) {
  const common = {
    width: 10,
    height: 10,
    viewBox: "0 0 10 10",
    "aria-hidden": true,
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (status) {
    case "queued":
      return (
        <svg {...common}>
          <circle cx={5} cy={5} r={3.4} />
        </svg>
      );
    case "running":
      return (
        <svg {...common} className="ag-glyph-running">
          <circle cx={5} cy={5} r={3.6} fill="var(--color-accent)" stroke="none" />
        </svg>
      );
    case "succeeded":
      return (
        <svg {...common}>
          <path d="M1.8 5.3 4 7.4 8.2 2.8" />
        </svg>
      );
    case "failed":
      return (
        <svg {...common}>
          <path d="M2.4 2.4 7.6 7.6M7.6 2.4 2.4 7.6" />
        </svg>
      );
    case "cancelled":
      return (
        <svg {...common}>
          <path d="M2 5h6" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <path d="M3.5 2v6M6.5 2v6" />
        </svg>
      );
  }
}

export function statusLabel(status: string): string {
  return STATUS[status]?.label ?? status;
}

export function StatusBadge({ status }: { status: string }) {
  const known = STATUS[status] ?? { tone: "neutral" as Tone, label: status };
  return (
    <Badge tone={known.tone} icon={<StatusGlyph status={status} />}>
      {known.label}
    </Badge>
  );
}
