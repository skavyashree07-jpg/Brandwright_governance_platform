import type { ReactNode } from "react";
import { Finding, isRisky } from "@/lib/api";

/** Draft text with findings marked. Interactive (buttons) when onPick is given, read-only (<mark>) otherwise.
 *  Risk is encoded by underline style and weight plus the issue number, not by colour alone. */
export function Annotated({ body, findings, num, activeId, onPick }: {
  body: string; findings: Finding[]; num: Record<string, number>; activeId?: string | null; onPick?: (x: Finding) => void;
}) {
  const parts: ReactNode[] = [];
  let p = 0;
  [...findings].filter(x => x.span.end > x.span.start).sort((a, b) => a.span.start - b.span.start).forEach(x => {
    if (x.span.start < p) return; // overlapping span: the card is still listed, only the inline mark is skipped
    parts.push(body.slice(p, x.span.start));
    const text = body.slice(x.span.start, x.span.end);
    const cls = `mk${isRisky(x) ? " rk" : ""}${activeId === x.id ? " on" : ""}`;
    const n = num[x.id];
    parts.push(onPick ? (
      <button key={x.id} id={`m-${x.id}`} type="button" className={cls} onClick={() => onPick(x)}
        aria-label={`Issue ${n}${isRisky(x) ? ", needs attention" : ""}: ${text}. Show details.`}>
        {text}<sup aria-hidden="true">{n}</sup>
      </button>
    ) : (
      <mark key={x.id} className={cls}><span className="sr-only">Issue {n}: </span>{text}<sup aria-hidden="true">{n}</sup></mark>
    ));
    p = x.span.end;
  });
  parts.push(body.slice(p));
  return <div className="doc">{parts}</div>;
}
