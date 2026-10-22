"use client";

import { useEffect, useState } from "react";

import { Field, formatNumber } from "@/components/ui";
import { estimateRun, type RunEstimateOut, type RunKind } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

/**
 * What a launch is likely to use, from recent finished runs of the same kind, beside the
 * budget the run stops at. The budget can be lowered or raised here.
 */
export function LaunchEstimate({
  kind,
  samples,
  unit = "sample",
  budget,
  onBudget,
}: {
  kind: RunKind;
  samples: number;
  unit?: string;
  budget: number | null;
  onBudget: (value: number | null) => void;
}) {
  const [estimate, setEstimate] = useState<RunEstimateOut | null>(null);

  useEffect(() => {
    if (samples < 1) return;
    let cancelled = false;
    void estimateRun({ client: browserClient, query: { kind, samples } }).then(({ data }) => {
      if (!cancelled && data) setEstimate(data);
    });
    return () => {
      cancelled = true;
    };
  }, [kind, samples]);

  const cap = budget ?? estimate?.default_budget ?? null;
  const over =
    estimate?.estimated_tokens !== null && estimate?.estimated_tokens !== undefined && cap !== null
      ? estimate.estimated_tokens > cap
      : false;
  return (
    <div className="ag-form-row">
      <div className="ag-estimate" aria-live="polite">
        <p className="ag-label" style={{ margin: 0 }}>
          Estimate
        </p>
        {!estimate ? (
          <p className="ag-hint">Working it out.</p>
        ) : estimate.estimated_tokens === null || estimate.estimated_tokens === undefined ? (
          <p className="ag-hint">No finished runs of this kind yet, so there is nothing to estimate from.</p>
        ) : (
          <p className="ag-hint">
            About <b className="ag-num">{formatNumber(estimate.estimated_tokens)}</b> tokens and{" "}
            <b className="ag-num">US${(estimate.estimated_cost_usd ?? 0).toFixed(2)}</b> for {samples} {unit}
            {samples === 1 ? "" : "s"}, from the last {estimate.basis_runs} finished{" "}
            {estimate.basis_runs === 1 ? "run" : "runs"} ({formatNumber(estimate.tokens_per_sample ?? 0)} tokens a{" "}
            {unit}).
            {over ? " That is more than the budget, so the run would stop at it." : ""}
          </p>
        )}
      </div>
      <Field
        label="Budget cap (tokens)"
        type="number"
        min={10000}
        step={10000}
        value={cap ?? ""}
        hint="The run stops cleanly when it reaches this."
        onChange={(event) => onBudget(event.target.value ? Number(event.target.value) : null)}
      />
    </div>
  );
}
