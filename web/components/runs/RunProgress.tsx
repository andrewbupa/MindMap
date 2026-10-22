import { StatusGlyph, statusLabel } from "./StatusBadge";

const ORDER = ["succeeded", "failed", "stopped_at_budget", "cancelled", "running", "queued"];
const SEGMENT: Record<string, string> = {
  succeeded: "ag-seg-succeeded",
  failed: "ag-seg-failed",
  stopped_at_budget: "ag-seg-stopped",
  cancelled: "ag-seg-cancelled",
  running: "ag-seg-running",
};
const FINISHED = ["succeeded", "failed", "stopped_at_budget", "cancelled"];

/** How far a run has got: a channel filled by status, and the counts in words. */
export function RunProgress({ counts, unit = "samples" }: { counts: Record<string, number>; unit?: string }) {
  const total = ORDER.reduce((sum, status) => sum + (counts[status] ?? 0), 0);
  const done = FINISHED.reduce((sum, status) => sum + (counts[status] ?? 0), 0);
  return (
    <div className="ag-progress">
      <div className="ag-progress-head">
        <span>
          {done} of {total} {unit} finished
        </span>
        <span className="ag-muted ag-num">{Math.round((done / (total || 1)) * 100)}%</span>
      </div>
      <div
        className="ag-progress-track ag-channel"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={done}
        aria-label={`${unit} finished`}
      >
        {ORDER.filter((status) => SEGMENT[status] && counts[status]).map((status) => (
          <span
            key={status}
            className={SEGMENT[status]}
            style={{ width: `${((counts[status] ?? 0) / (total || 1)) * 100}%` }}
          />
        ))}
      </div>
      <ul className="ag-progress-legend">
        {ORDER.filter((status) => counts[status]).map((status) => (
          <li key={status}>
            <StatusGlyph status={status} />
            <b>{counts[status]}</b> {statusLabel(status).toLowerCase()}
          </li>
        ))}
      </ul>
    </div>
  );
}
