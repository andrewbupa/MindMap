"use client";

import {
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type Ref,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

import { cx } from "./format";

function describedBy(id: string, hint?: ReactNode, error?: ReactNode): string | undefined {
  const ids = [hint ? `${id}-hint` : "", error ? `${id}-error` : ""].filter(Boolean);
  return ids.length ? ids.join(" ") : undefined;
}

function Foot({ id, hint, error }: { id: string; hint?: ReactNode; error?: ReactNode }) {
  return (
    <>
      {hint ? (
        <p id={`${id}-hint`} className="ag-hint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="ag-error">
          <span aria-hidden="true">!</span>
          {error}
        </p>
      ) : null}
    </>
  );
}

type Labelled = { label: ReactNode; hint?: ReactNode; error?: ReactNode; className?: string };

export function Field({
  label,
  hint,
  error,
  className,
  id: given,
  ...input
}: Labelled & InputHTMLAttributes<HTMLInputElement>) {
  const auto = useId();
  const id = given ?? auto;
  return (
    <div className={cx("ag-field", className)}>
      <label className="ag-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="ag-input"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        {...input}
      />
      <Foot id={id} hint={hint} error={error} />
    </div>
  );
}

export function TextArea({
  label,
  hint,
  error,
  className,
  id: given,
  ref,
  ...input
}: Labelled & TextareaHTMLAttributes<HTMLTextAreaElement> & { ref?: Ref<HTMLTextAreaElement> }) {
  const auto = useId();
  const id = given ?? auto;
  return (
    <div className={cx("ag-field", className)}>
      <label className="ag-label" htmlFor={id}>
        {label}
      </label>
      <textarea
        ref={ref}
        id={id}
        className="ag-input"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        {...input}
      />
      <Foot id={id} hint={hint} error={error} />
    </div>
  );
}

export type Option = string | { value: string; label: string };

export function Select({
  label,
  hint,
  error,
  className,
  id: given,
  options,
  children,
  ...select
}: Labelled & SelectHTMLAttributes<HTMLSelectElement> & { options?: Option[] }) {
  const auto = useId();
  const id = given ?? auto;
  return (
    <div className={cx("ag-field", className)}>
      <label className="ag-label" htmlFor={id}>
        {label}
      </label>
      <div className="ag-select">
        <select
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(id, hint, error)}
          {...select}
        >
          {options
            ? options.map((option) => {
                const { value, label: text } =
                  typeof option === "string" ? { value: option, label: option } : option;
                return (
                  <option key={value} value={value}>
                    {text}
                  </option>
                );
              })
            : children}
        </select>
      </div>
      <Foot id={id} hint={hint} error={error} />
    </div>
  );
}

function Choice({
  type,
  label,
  hint,
  className,
  id: given,
  ...input
}: { type: "checkbox" | "radio"; label: ReactNode; hint?: ReactNode; className?: string } & Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "type"
>) {
  const auto = useId();
  const id = given ?? auto;
  return (
    <label className={cx("ag-check", className)} htmlFor={id}>
      <input id={id} type={type} aria-describedby={hint ? `${id}-hint` : undefined} {...input} />
      <span>{label}</span>
      {hint ? (
        <span id={`${id}-hint`} className="ag-hint">
          {hint}
        </span>
      ) : null}
    </label>
  );
}

export function Checkbox(props: Omit<Parameters<typeof Choice>[0], "type">) {
  return <Choice type="checkbox" {...props} />;
}

export function Radio(props: Omit<Parameters<typeof Choice>[0], "type"> & { name: string }) {
  return <Choice type="radio" {...props} />;
}
