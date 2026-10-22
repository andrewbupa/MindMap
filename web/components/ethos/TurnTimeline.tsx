import type { AnnotationOut, ExpectationOut, EthosLabelOut, ReplyEthosOut } from "@/lib/api";

import { familyColour, formatMedian, labelName, tint } from "./family";
import styles from "./ethos.module.css";

/**
 * How each label rises and settles across a conversation: a row per label, a column
 * per reply, each cell the panel's median intensity, linked to the phrase behind it.
 */
export function TurnTimeline({
  replies,
  expected,
  labels,
  annotations,
}: {
  replies: ReplyEthosOut[];
  expected: ExpectationOut[];
  labels: EthosLabelOut[];
  annotations: AnnotationOut[];
}) {
  const present = new Set([
    ...replies.flatMap((r) => r.labels.filter((l) => l.median > 0).map((l) => l.label)),
    ...expected.filter((e) => e.expect === "present").map((e) => e.label),
  ]);
  const rows = labels.filter((l) => present.has(l.key));
  if (!rows.length || !replies.length) return <p>No labels were found in this conversation.</p>;
  return (
    <div className={styles.timeline}>
      <table>
        <caption className={styles.quiet}>
          Each cell is the panel&apos;s median intensity for the label in that reply, from 0 to 3.
        </caption>
        <thead>
          <tr>
            <th scope="col">Label</th>
            {replies.map((reply, index) => (
              <th key={reply.message_id} scope="col">
                <a href={`#r-${reply.message_id}`}>Reply {index + 1}</a>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((label) => (
            <tr key={label.key}>
              <th scope="row">
                <span className={styles.swatch} style={{ background: familyColour(label.family) }} />
                {labelName(label.key)}
              </th>
              {replies.map((reply) => {
                const median = reply.labels.find((l) => l.label === label.key)?.median ?? 0;
                const first = annotations.find(
                  (a) => a.message_id === reply.message_id && a.label === label.key && a.channel === "content",
                );
                return (
                  <td key={reply.message_id}>
                    {first ? (
                      <a href={`#a-${first.id}`} style={{ background: tint(label.family, median) }}>
                        {formatMedian(median)}
                      </a>
                    ) : (
                      <span className={styles.quiet}>0</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
