import type { ButtonHTMLAttributes, ReactNode } from "react";

import styles from "./ui.module.css";

export function Button({
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" }) {
  const classes = [styles.button, variant === "secondary" ? styles.secondary : "", className ?? ""];
  return <button type="button" className={classes.join(" ").trim()} {...props} />;
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className={styles.card}>
      {title ? <h2 className={styles.cardTitle}>{title}</h2> : null}
      {children}
    </section>
  );
}

/** Page title, an optional quiet line beneath it, and a short lede. */
export function PageHeader({
  title,
  quiet,
  children,
}: {
  title: string;
  quiet?: string;
  children?: ReactNode;
}) {
  return (
    <header className={styles.header}>
      <h1>{title}</h1>
      {quiet ? <p className={styles.quiet}>{quiet}</p> : null}
      {children ? <div className={styles.lede}>{children}</div> : null}
    </header>
  );
}

export type Tone = "neutral" | "ok" | "warn" | "danger";

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  const toneClass = tone === "neutral" ? "" : styles[tone];
  return <span className={`${styles.badge} ${toneClass}`.trim()}>{children}</span>;
}

export function Notice({ tone = "info", children }: { tone?: "info" | "danger"; children: ReactNode }) {
  const classes = tone === "danger" ? `${styles.notice} ${styles.noticeDanger}` : styles.notice;
  return (
    <div className={classes} role={tone === "danger" ? "alert" : "status"}>
      {children}
    </div>
  );
}

/** An action that reads as a link, such as opening the evidence behind a number. */
export function LinkButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" className={styles.linkButton} {...props} />;
}

export function sentenceCase(value: string): string {
  const words = value.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function Mono({ children }: { children: ReactNode }) {
  return <span className={styles.mono}>{children}</span>;
}

export function formatWhen(value: string | null | undefined, fallback = "Not recorded"): string {
  if (!value) return fallback;
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}
