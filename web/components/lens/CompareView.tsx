import Link from "next/link";

import { Card, PageHeader, sentenceCase } from "@/components/ui";
import type { LabelPrevalenceOut, LensCompareOut } from "@/lib/api";

import { LENS_QUIET, familyColour, labelName } from "./family";
import styles from "./lens.module.css";

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not read" : `${Math.round(value * 100)}%`;
}

function share(item: LabelPrevalenceOut): string {
  const range = item.interval ? ` (${percent(item.interval.low)} to ${percent(item.interval.high)})` : "";
  return `${percent(item.share)}${range}`;
}

/** Both runs' shares and intervals on one 0 to 100% track: A hollow, B filled. */
function Pair({ a, b }: { a: LabelPrevalenceOut; b: LabelPrevalenceOut }) {
  const x = (value: number) => 6 + value * 188;
  const mark = (item: LabelPrevalenceOut, y: number, filled: boolean) =>
    item.share === null || item.share === undefined ? null : (
      <g>
        {item.interval ? (
          <line
            x1={x(item.interval.low)}
            x2={x(item.interval.high)}
            y1={y}
            y2={y}
            stroke="var(--color-text-muted)"
            strokeWidth={1.5}
          />
        ) : null}
        <circle
          cx={x(item.share)}
          cy={y}
          r={4}
          fill={filled ? "var(--color-chart-1)" : "var(--color-surface)"}
          stroke={filled ? "var(--color-surface)" : "var(--color-text)"}
          strokeWidth={filled ? 2 : 1.5}
        />
      </g>
    );
  return (
    <svg width={200} height={24} viewBox="0 0 200 24" aria-hidden="true">
      <line x1={6} x2={194} y1={12} y2={12} stroke="var(--color-chart-grid)" />
      {mark(a, 7, false)}
      {mark(b, 17, true)}
    </svg>
  );
}

/** Prompt A beside prompt B on the scenarios both read: shares, intervals, difference. */
export function CompareView({ data }: { data: LensCompareOut }) {
  const families = [...new Set(data.labels.map((l) => l.family))];
  const versionOf = (run: LensCompareOut["a"]) =>
    [run.run.config.agent, run.run.config.version].filter(Boolean).join(" ") || run.run.title;
  return (
    <>
      <PageHeader title={`Compare: ${versionOf(data.a)} and ${versionOf(data.b)}`} quiet={LENS_QUIET}>
        <p>
          A is <Link href={`/lens/runs/${data.a.run.id}`}>{data.a.run.title}</Link>; B is{" "}
          <Link href={`/lens/runs/${data.b.run.id}`}>{data.b.run.title}</Link>. Only the{" "}
          {data.shared_scenarios} scenarios both read are compared.
        </p>
      </PageHeader>
      <Card title="Labels">
        <p className={styles.quiet}>
          Share of replies expressing each label, with 95% Wilson intervals. On the track, A is
          the hollow circle and B the filled one. Where intervals overlap, the difference may be
          noise.
        </p>
        <table className={styles.numbers}>
          <thead>
            <tr>
              <th scope="col">Label</th>
              <th scope="col">A</th>
              <th scope="col">B</th>
              <th scope="col">
                <span className="visually-hidden">A and B on a track</span>
              </th>
              <th scope="col">B minus A</th>
            </tr>
          </thead>
          {families.map((family) => (
            <tbody key={family}>
              <tr>
                <th scope="rowgroup" colSpan={5}>
                  <span className={styles.swatch} style={{ background: familyColour(family) }} />
                  {sentenceCase(family)}
                </th>
              </tr>
              {data.labels
                .filter((l) => l.family === family)
                .map((row) => (
                  <tr key={row.label}>
                    <td>{labelName(row.label)}</td>
                    <td>
                      <Link href={`/lens/runs/${data.a.run.id}?label=${row.label}#evidence`}>{share(row.a)}</Link>
                    </td>
                    <td>
                      <Link href={`/lens/runs/${data.b.run.id}?label=${row.label}#evidence`}>{share(row.b)}</Link>
                    </td>
                    <td>
                      <Pair a={row.a} b={row.b} />
                    </td>
                    <td>
                      {row.difference === null || row.difference === undefined
                        ? "Not read"
                        : `${row.difference > 0 ? "+" : ""}${Math.round(row.difference * 100)} points`}
                    </td>
                  </tr>
                ))}
            </tbody>
          ))}
        </table>
      </Card>
      <Card title="Fit by scenario">
        <table className={styles.numbers}>
          <thead>
            <tr>
              <th scope="col">Scenario</th>
              <th scope="col">A</th>
              <th scope="col">B</th>
            </tr>
          </thead>
          <tbody>
            {data.scenarios.map((row) => (
              <tr key={row.scenario_key}>
                <td>{sentenceCase(row.scenario_key.split("/").pop()!.replaceAll(/[-_]/g, " "))}</td>
                <td>
                  {row.a_transcripts[0] ? (
                    <Link href={`/lens/runs/${data.a.run.id}/transcripts/${row.a_transcripts[0]}`}>
                      {row.a_fit === null || row.a_fit === undefined ? "No profile" : percent(row.a_fit)}
                    </Link>
                  ) : null}
                </td>
                <td>
                  {row.b_transcripts[0] ? (
                    <Link href={`/lens/runs/${data.b.run.id}/transcripts/${row.b_transcripts[0]}`}>
                      {row.b_fit === null || row.b_fit === undefined ? "No profile" : percent(row.b_fit)}
                    </Link>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}
