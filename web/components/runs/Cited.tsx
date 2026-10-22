import { Fragment } from "react";

const CITE = /(\[M\d+\])/;
const IS_CITE = /^\[M(\d+)\]$/;

/** Judge text where each citation, such as [M3], links to the message it cites. */
export function Cited({ text, cites }: { text: string; cites: Map<string, number | null> }) {
  return (
    <p className="ag-cited">
      {text.split(CITE).map((part, index) => {
        const match = IS_CITE.exec(part);
        if (!match) return <Fragment key={index}>{part}</Fragment>;
        const target = cites.get(part);
        const label = `M${match[1]}`;
        return target === undefined || target === null ? (
          <span key={index} className="ag-cite" title="Cites a message from a branch the auditor rolled back">
            {label}
          </span>
        ) : (
          <a key={index} className="ag-cite" href={`#m-${target}`} aria-label={`Message ${match[1]}`}>
            {label}
          </a>
        );
      })}
    </p>
  );
}
