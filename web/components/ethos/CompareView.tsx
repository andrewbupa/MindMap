import Link from "next/link";

import { DataTable, type Row } from "@/components/data/DataTable";
import { Card, PageHeader, sentenceCase } from "@/components/ui";
import type { EthosCompareOut } from "@/lib/api";

import { ETHOS_NOTE } from "./family";
import { LabelChip } from "./LabelChip";

const SPAN = 0.4;

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not read" : `${Math.round(value * 100)}%`;
}

function points(value: number): string {
  const whole = Math.round(value * 100);
  return `${whole > 0 ? "+" : ""}${whole}`;
}

/** Prompt A beside prompt B on the scenarios both read: shares, and the difference with its interval. */
export function CompareView({ data }: { data: EthosCompareOut }) {
  const versionOf = (run: EthosCompareOut["a"]) =>
    [run.run.config.agent, run.run.config.version].filter(Boolean).join(" ") || run.run.title;
  const a = versionOf(data.a);
  const b = versionOf(data.b);
  const pc = (v: number) => `${50 + (Math.max(-SPAN, Math.min(SPAN, v)) / SPAN) * 50}%`;
  return (
    <>
      <PageHeader
        title={`Compare ${a} with ${b}`}
        note={ETHOS_NOTE}
        actions={
          <span className="ag-row">
            <a className="ag-btn" href={`/api/record/compare.pdf?a=${data.a.run.id}&b=${data.b.run.id}`}>
              Download report (PDF)
            </a>
            <a className="ag-btn" href={`/api/record/compare.csv?a=${data.a.run.id}&b=${data.b.run.id}`}>
              Download labels (CSV)
            </a>
          </span>
        }
      >
        <p>
          A is <Link href={`/ethos/runs/${data.a.run.id}`}>{data.a.run.title}</Link>; B is{" "}
          <Link href={`/ethos/runs/${data.b.run.id}`}>{data.b.run.title}</Link>. Only the {data.shared_scenarios}{" "}
          scenarios both read are compared.
        </p>
      </PageHeader>
      <Card title="Labels">
        <p className="ag-quiet">
          The share of replies expressing each label. The track shows B minus A with its 95% interval (Newcombe&apos;s
          method, from each share&apos;s Wilson interval); where the interval crosses the middle line, the difference
          may be noise. Each share opens the findings behind it.
        </p>
        <div className="ag-cmp" role="table" aria-label={`Prompt ${a} beside prompt ${b}`}>
          <div role="row" className="ag-row">
            <span className="ag-cmp-h" role="columnheader">
              Label
            </span>
            <span className="ag-cmp-h" role="columnheader">
              A
            </span>
            <span className="ag-cmp-h" role="columnheader">
              B
            </span>
            <span className="ag-cmp-h" role="columnheader">
              Difference, B minus A, with 95% interval
            </span>
            <span className="ag-cmp-h" role="columnheader">
              <span className="ag-sr">In words</span>
            </span>
          </div>
          {data.labels.map((row) => {
            // Newcombe's interval, worked out by the API so exports carry the same one.
            const interval = row.difference_interval ?? null;
            const diff = row.difference;
            const words =
              diff === null || diff === undefined || !interval
                ? "Not read in both runs"
                : `${points(diff)} points (${points(interval.low)} to ${points(interval.high)})`;
            return (
              <div key={row.label} role="row" className="ag-row">
                <span role="rowheader">
                  <LabelChip family={row.family} label={row.label} />
                </span>
                <span role="cell" className="ag-num">
                  <Link href={`/ethos/runs/${data.a.run.id}?label=${row.label}#evidence`}>{percent(row.a.share)}</Link>
                </span>
                <span role="cell" className="ag-num">
                  <Link href={`/ethos/runs/${data.b.run.id}?label=${row.label}#evidence`}>{percent(row.b.share)}</Link>
                </span>
                <div role="cell" className="ag-diverge ag-channel" aria-label={words}>
                  {interval && diff !== null && diff !== undefined ? (
                    <>
                      <span
                        className="ag-ib-band"
                        aria-hidden="true"
                        style={{ left: pc(interval.low), width: `calc(${pc(interval.high)} - ${pc(interval.low)})` }}
                      />
                      <span className="ag-bead" aria-hidden="true" style={{ left: pc(diff) }} />
                    </>
                  ) : null}
                </div>
                <span role="cell" className="ag-num">
                  {words}
                </span>
              </div>
            );
          })}
        </div>
      </Card>
      <Card title="Fit by scenario">
        <DataTable
          columns={[
            { key: "scenario", label: "Scenario" },
            { key: "a", label: `A: ${a}`, align: "right" },
            { key: "b", label: `B: ${b}`, align: "right" },
          ]}
          rows={data.scenarios.map(
            (row): Row => ({
              id: row.scenario_key,
              cells: {
                scenario: sentenceCase(row.scenario_key.split("/").pop()!.replaceAll(/[-_]/g, " ")),
                a: row.a_transcripts[0] ? (
                  <Link href={`/ethos/runs/${data.a.run.id}/transcripts/${row.a_transcripts[0]}`}>
                    {row.a_fit === null || row.a_fit === undefined ? "No profile" : percent(row.a_fit)}
                  </Link>
                ) : null,
                b: row.b_transcripts[0] ? (
                  <Link href={`/ethos/runs/${data.b.run.id}/transcripts/${row.b_transcripts[0]}`}>
                    {row.b_fit === null || row.b_fit === undefined ? "No profile" : percent(row.b_fit)}
                  </Link>
                ) : null,
              },
              sort: { scenario: row.scenario_key, a: row.a_fit, b: row.b_fit },
            }),
          )}
        />
      </Card>
    </>
  );
}
