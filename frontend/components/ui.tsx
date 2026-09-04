/**
 * The primitives every screen repeats.
 *
 * Not one of the nine components the plan names, but writing the same class string
 * forty times across four routes is exactly how a design system drifts into six
 * slightly-different buttons. One file is cheaper than that drift.
 */

import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

// --- buttons ----------------------------------------------------------------

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  // Black, not accent-coloured. Colour is reserved for meaning.
  primary: "bg-ink text-paper hover:bg-black disabled:bg-faint",
  secondary: "border border-rule text-ink hover:border-ink disabled:text-faint",
  ghost: "text-muted hover:text-ink disabled:text-faint",
  danger: "border border-rule text-negative hover:border-negative",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
}

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cx(
        // 2px, not square: a control has to read as pressable, and this is the least
        // rounding that does that without softening the page.
        "inline-flex items-center justify-center gap-1.5 rounded-[2px]",
        "transition-colors disabled:cursor-not-allowed",
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-9 px-3.5 text-sm",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}

// --- form controls ----------------------------------------------------------

const CONTROL =
  "w-full rounded-[2px] border border-rule bg-paper px-2.5 py-1.5 text-sm " +
  "placeholder:text-faint focus:border-ink focus:outline-none " +
  "focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-0 " +
  "disabled:bg-wash disabled:text-muted";

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(CONTROL, className)} {...props} />;
}

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea className={cx(CONTROL, "resize-y leading-relaxed", className)} {...props} />
  );
}

export function Select({
  className,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cx(CONTROL, "h-9 py-0", className)} {...props} />;
}

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cx("block", className)}>
      <span className="label-xs mb-1.5 block text-muted">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  );
}

// --- structure --------------------------------------------------------------

/** The hairline that does the work borders and shadows would do elsewhere. */
export function Rule({ className }: { className?: string }) {
  return <hr className={cx("border-0 border-t border-rule", className)} />;
}

export function PageHeader({
  title,
  children,
  actions,
}: {
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-10 flex items-end justify-between gap-6 border-b border-rule pb-5">
      <div>
        <h1 className="display text-3xl font-semibold">{title}</h1>
        {children && <p className="mt-1.5 text-sm text-muted">{children}</p>}
      </div>
      {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
    </header>
  );
}

/** Consistent page frame: one measure, one set of margins, on every route. */
export function Page({ children }: { children: ReactNode }) {
  return <main className="mx-auto w-full max-w-5xl px-6 py-12">{children}</main>;
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="border-t border-rule py-10 text-center text-sm text-muted">
      {children}
    </p>
  );
}
