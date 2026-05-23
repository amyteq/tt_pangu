import clsx from "clsx";
import { type ButtonHTMLAttributes, type ReactNode } from "react";

type ButtonVariant = "default" | "primary" | "danger" | "caution" | "ghost";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({
  variant = "default",
  className,
  ...rest
}: ButtonProps): JSX.Element {
  const styles: Record<ButtonVariant, string> = {
    default: "bg-slate-100 hover:bg-slate-200 text-slate-800",
    primary: "bg-indigo-600 hover:bg-indigo-700 text-white",
    danger: "bg-red-600 hover:bg-red-700 text-white",
    caution: "bg-amber-500 hover:bg-amber-600 text-white",
    ghost: "bg-transparent hover:bg-slate-100 text-slate-700",
  };
  return (
    <button
      type="button"
      className={clsx(
        "inline-flex items-center justify-center rounded px-3 py-1.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed",
        styles[variant],
        className,
      )}
      {...rest}
    />
  );
}

export function Card({
  title,
  children,
  className,
}: {
  title?: ReactNode;
  children: ReactNode;
  className?: string;
}): JSX.Element {
  return (
    <section
      className={clsx(
        "rounded-lg border border-slate-200 bg-white p-4 shadow-sm",
        className,
      )}
    >
      {title && (
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-600">
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}

export function Table<T>({
  rows,
  columns,
  empty = <Empty>No rows</Empty>,
}: {
  rows: T[];
  columns: {
    key: string;
    header: ReactNode;
    render: (row: T) => ReactNode;
    align?: "left" | "right";
    sortable?: boolean;
    onSort?: () => void;
  }[];
  empty?: ReactNode;
}): JSX.Element {
  if (rows.length === 0) {
    return <div className="text-sm text-slate-500">{empty}</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
            {columns.map((c) => (
              <th
                key={c.key}
                className={clsx(
                  "py-2 pr-4",
                  c.align === "right" && "text-right font-mono",
                )}
              >
                {c.sortable && c.onSort ? (
                  <button
                    type="button"
                    onClick={c.onSort}
                    className="font-semibold text-slate-700 hover:text-slate-900"
                  >
                    {c.header}
                  </button>
                ) : (
                  c.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className="border-b border-slate-100 last:border-b-0 hover:bg-slate-50"
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={clsx(
                    "py-2 pr-4",
                    c.align === "right" && "text-right font-mono",
                  )}
                >
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Badge({
  children,
  color = "slate",
}: {
  children: ReactNode;
  color?: "slate" | "green" | "red" | "amber" | "indigo";
}): JSX.Element {
  const colors: Record<string, string> = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-green-100 text-green-800",
    red: "bg-red-100 text-red-800",
    amber: "bg-amber-100 text-amber-800",
    indigo: "bg-indigo-100 text-indigo-800",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded px-2 py-0.5 text-xs font-medium",
        colors[color],
      )}
    >
      {children}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }): JSX.Element {
  return (
    <div className="rounded border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">
      {children}
    </div>
  );
}

export function Spinner(): JSX.Element {
  return (
    <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
  );
}

export function Modal({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}): JSX.Element | null {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="max-w-lg rounded-lg bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

export function Toast({ message }: { message: string }): JSX.Element {
  return (
    <div className="fixed bottom-4 right-4 rounded bg-slate-900 px-4 py-2 text-sm text-white shadow-lg">
      {message}
    </div>
  );
}
