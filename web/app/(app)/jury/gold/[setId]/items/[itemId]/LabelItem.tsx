"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Fragment, useState } from "react";

import { familyColour, intensityName, labelName } from "@/components/ethos/family";
import ethosStyles from "@/components/ethos/ethos.module.css";
import { MessageView } from "@/components/runs/Messages";
import runStyles from "@/components/runs/runs.module.css";
import { Button, Card, Notice, PageHeader, sentenceCase } from "@/components/ui";
import { saveGoldRatings, type GoldItemDetail } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

const INTENSITIES = [0, 1, 2, 3];

/**
 * Blind labelling: the conversation and the labels, never the judges' findings or
 * another expert's ratings. Every label on every reply starts at absent.
 */
export function LabelItem({ item }: { item: GoldItemDetail }) {
  const router = useRouter();
  const key = (message: string, label: string) => `${message}:${label}`;
  const [ratings, setRatings] = useState<Record<string, number>>(() =>
    Object.fromEntries(item.mine.map((r) => [key(r.message_id, r.label), r.intensity])),
  );
  const [saved, setSaved] = useState(item.mine.length > 0);
  const [error, setError] = useState<string | null>(null);
  const families = [...new Set(item.labels.map((l) => l.family))];
  const replies = new Set(item.replies);

  async function save() {
    setError(null);
    const body = item.replies.flatMap((message) =>
      item.labels.map((label) => ({
        message_id: message,
        label: label.key,
        intensity: ratings[key(message, label.key)] ?? 0,
      })),
    );
    const { data, error: failed } = await saveGoldRatings({
      client: browserClient,
      path: { set_id: item.gold_set, item_id: item.id },
      body: { ratings: body },
    });
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "Your ratings were not saved.");
      return;
    }
    setSaved(true);
    if (item.next_item) router.push(`/jury/gold/${item.gold_set}/items/${item.next_item}`);
    else router.push(`/jury/gold/${item.gold_set}`);
  }

  return (
    <>
      <PageHeader title={`Label: ${sentenceCase((item.scenario_key ?? "transcript").split("/").pop()!.replaceAll(/[-_]/g, " "))}`}>
        <p>
          From <Link href={`/jury/gold/${item.gold_set}`}>{item.gold_set_name}</Link>. Rate how
          strongly each reply shows each label, on its own merits. Labels you leave at absent
          are saved as absent.
        </p>
      </PageHeader>
      {item.content_notes.map((note) => (
        <Notice key={note}>Content note: {sentenceCase(note)}.</Notice>
      ))}
      {saved ? <Notice>You have rated this transcript. Saving again replaces your ratings.</Notice> : null}
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <div className={runStyles.thread}>
        {item.messages.map((message) => {
          if (!replies.has(message.id)) {
            return <MessageView key={message.id} message={message} speaker="Member (played by the auditor)" />;
          }
          return (
            <Card key={message.id} title={`Reply ${item.replies.indexOf(message.id) + 1}`}>
              <p className={ethosStyles.reply}>{message.content}</p>
              <table>
                <thead>
                  <tr>
                    <th scope="col">Label</th>
                    {INTENSITIES.map((value) => (
                      <th key={value} scope="col">
                        {sentenceCase(intensityName(value))}
                      </th>
                    ))}
                  </tr>
                </thead>
                {families.map((family) => (
                  <tbody key={family}>
                    <tr>
                      <th scope="rowgroup" colSpan={5}>
                        <span className={ethosStyles.swatch} style={{ background: familyColour(family) }} />
                        {sentenceCase(family)}
                      </th>
                    </tr>
                    {item.labels
                      .filter((label) => label.family === family)
                      .map((label) => (
                        <Fragment key={label.key}>
                          <tr>
                            <td title={label.definition}>
                              <details>
                                <summary>{labelName(label.key)}</summary>
                                <span className={ethosStyles.quiet}>{label.definition}</span>
                              </details>
                            </td>
                            {INTENSITIES.map((value) => (
                              <td key={value}>
                                <input
                                  type="radio"
                                  aria-label={`${labelName(label.key)}: ${intensityName(value)}`}
                                  name={key(message.id, label.key)}
                                  checked={(ratings[key(message.id, label.key)] ?? 0) === value}
                                  onChange={() =>
                                    setRatings((current) => ({ ...current, [key(message.id, label.key)]: value }))
                                  }
                                />
                              </td>
                            ))}
                          </tr>
                        </Fragment>
                      ))}
                  </tbody>
                ))}
              </table>
            </Card>
          );
        })}
      </div>
      <p>
        <Button onClick={save}>{item.next_item ? "Save and label the next" : "Save"}</Button>
      </p>
    </>
  );
}
