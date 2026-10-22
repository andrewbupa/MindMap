import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";

import { cx } from "./format";

export type Tone = "neutral" | "ok" | "warn" | "danger";

const TONE_COLOUR: Record<Tone | "info", string> = {
  ok: "var(--color-ok)",
  warn: "var(--color-warn)",
  danger: "var(--color-danger)",
  info: "var(--color-accent)",
  neutral: "var(--color-text-muted)",
};

/** A small raised drop that sits in channels. */
export function Bead({ colour, size, className }: { colour?: string; size?: number; className?: string }) {
  const style: CSSProperties & Record<string, string | number> = {};
  if (colour) style["--ag-bead"] = colour;
  if (size) Object.assign(style, { width: size, height: size });
  return <span className={cx("ag-bead", className)} aria-hidden="true" style={style} />;
}

export function Button({
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" }) {
  return (
    <button
      type="button"
      className={cx("ag-btn", variant === "primary" && "ag-btn-primary", className)}
      {...props}
    />
  );
}

type LinkButtonProps =
  | (ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined })
  | (AnchorHTMLAttributes<HTMLAnchorElement> & { href: string });

/** An action that reads as a link, such as opening the evidence behind a number. */
export function LinkButton(props: LinkButtonProps) {
  if (props.href !== undefined) {
    const { className, href, ...rest } = props;
    return <Link href={href} className={cx("ag-link", className)} {...rest} />;
  }
  const { className, ...rest } = props;
  return <button type="button" className={cx("ag-link", className)} {...rest} />;
}

export function Badge({
  tone = "neutral",
  icon,
  children,
}: {
  tone?: Tone;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <span className={cx("ag-badge", tone !== "neutral" && `ag-badge-${tone}`)}>
      {icon}
      {children}
    </span>
  );
}

/** Hashes, IDs and model names. Long values can be truncated, with the whole value on hover. */
export function Mono({
  children,
  truncate,
  plain = false,
  title,
}: {
  children: ReactNode;
  truncate?: number;
  plain?: boolean;
  title?: string;
}) {
  const text = typeof children === "string" ? children : null;
  const shown = text && truncate && text.length > truncate ? `${text.slice(0, truncate)}…` : children;
  return (
    <span className={cx("ag-mono", plain && "ag-mono-plain")} title={shown !== children ? (text ?? undefined) : title}>
      {shown}
    </span>
  );
}

export function Card({
  title,
  actions,
  label,
  className,
  id,
  children,
}: {
  title?: string;
  actions?: ReactNode;
  label?: string;
  className?: string;
  id?: string;
  children?: ReactNode;
}) {
  return (
    <section id={id} className={cx("ag-card", className)} aria-label={title ? undefined : label}>
      {title || actions ? (
        <div className="ag-card-head">
          {title ? <h2 className="ag-card-title">{title}</h2> : <span />}
          {actions}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "danger";
  title?: string;
  children: ReactNode;
}) {
  return (
    <div role={tone === "danger" ? "alert" : "note"} className={cx("ag-notice", `ag-notice-${tone}`)}>
      <Bead colour={TONE_COLOUR[tone]} />
      <div>
        {title ? <p className="ag-notice-title">{title}</p> : null}
        <div>{children}</div>
      </div>
    </div>
  );
}

/** Says what just happened, in the words of the action: "Verdict recorded". */
export function Toast({
  tone = "ok",
  action,
  children,
}: {
  tone?: "ok" | "warn" | "danger" | "info";
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div role="status" className="ag-toast">
      <Bead colour={TONE_COLOUR[tone]} />
      <span>{children}</span>
      {action}
    </div>
  );
}
