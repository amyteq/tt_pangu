import { NavLink, Outlet } from "react-router-dom";
import clsx from "clsx";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/runs", label: "Runs" },
  { to: "/experiments", label: "Experiments" },
  { to: "/research", label: "Research" },
  { to: "/approvals", label: "Approvals" },
  { to: "/artifacts", label: "Artifacts" },
];

const env = import.meta.env.VITE_KCA_ENV ?? "local";

export function Layout(): JSX.Element {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="text-lg font-semibold">kaggle-code-agent</span>
            <span
              className={clsx(
                "rounded px-2 py-0.5 text-xs uppercase tracking-wide",
                env === "prod"
                  ? "bg-red-100 text-red-800"
                  : env === "dev"
                    ? "bg-amber-100 text-amber-800"
                    : "bg-slate-200 text-slate-700",
              )}
            >
              {env}
            </span>
            <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs text-indigo-800">
              M8 preview
            </span>
          </div>
          <a
            className="text-sm text-slate-600 hover:text-slate-900"
            href="https://github.com/"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </a>
        </div>
      </header>
      <div className="flex">
        <nav className="w-44 border-r border-slate-200 bg-white px-3 py-4">
          <ul className="space-y-1">
            {NAV.map(({ to, label, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={Boolean(end)}
                  className={({ isActive }) =>
                    clsx(
                      "block rounded px-3 py-2 text-sm",
                      isActive
                        ? "bg-indigo-50 font-medium text-indigo-700"
                        : "text-slate-700 hover:bg-slate-100",
                    )
                  }
                >
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main className="flex-1 px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
