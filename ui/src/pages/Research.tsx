import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, Empty, Spinner } from "../ui";
import {
  db,
  type ResearchCitation,
  type ResearchItem,
} from "../lib/db";
import { renderMarkdown } from "../lib/markdown";

function trustColor(trust: string): "green" | "amber" | "red" {
  if (trust === "high") return "green";
  if (trust === "medium") return "amber";
  return "red";
}

export function Research(): JSX.Element {
  const [items, setItems] = useState<ResearchItem[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [citations, setCitations] = useState<ResearchCitation[]>([]);
  const [showSource, setShowSource] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    db.listResearchItems(50)
      .then((r) => {
        if (!live) return;
        setItems(r);
        if (r.length > 0) setSelected(r[0].id);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    db.listCitationsForRun(selected).then(setCitations).catch(() => setCitations([]));
  }, [selected]);

  const active = useMemo(
    () => items.find((i) => i.id === selected) ?? null,
    [items, selected],
  );

  if (loading) return <Spinner />;
  if (items.length === 0)
    return (
      <Card title="Research">
        <Empty>No research items yet.</Empty>
      </Card>
    );

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card title="Items" className="lg:col-span-1">
        <ul className="space-y-2">
          {items.map((it) => (
            <li key={it.id}>
              <button
                type="button"
                onClick={() => setSelected(it.id)}
                className={`block w-full rounded p-2 text-left text-sm hover:bg-slate-50 ${
                  selected === it.id ? "bg-indigo-50" : ""
                }`}
              >
                <div className="font-medium">{it.title ?? it.url}</div>
                <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                  <Badge color={trustColor(it.trust)}>{it.trust}</Badge>
                  <a
                    href={it.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="truncate hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {it.url}
                  </a>
                </div>
                <div className="mt-0.5 text-xs text-slate-400">
                  fetched {it.fetched_at?.slice(0, 19) ?? "—"}
                </div>
              </button>
            </li>
          ))}
        </ul>
      </Card>
      <Card title={active?.title ?? "Item"} className="lg:col-span-2">
        {active ? (
          <div>
            <div className="mb-3 flex items-center gap-2 text-xs">
              <Badge color={trustColor(active.trust)}>{active.trust}</Badge>
              <a
                href={active.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-700 hover:underline"
              >
                source ↗
              </a>
            </div>
            <article
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{
                __html: renderMarkdown(active.summary ?? ""),
              }}
            />
            <h3 className="mt-6 text-sm font-semibold text-slate-700">
              Citations
            </h3>
            {citations.length === 0 ? (
              <Empty>No citations for this run.</Empty>
            ) : (
              <ul className="mt-2 space-y-1 text-xs text-slate-700">
                {citations.map((c) => (
                  <li key={c.id} className="rounded border border-slate-100 p-2">
                    {c.quote && <p className="italic">"{c.quote}"</p>}
                    {c.job_id && (
                      <Link
                        to={`/runs/${c.job_id}`}
                        className="text-indigo-700 hover:underline"
                      >
                        job {c.job_id.slice(0, 8)}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <details
              className="mt-6"
              open={showSource}
              onToggle={(e) => setShowSource((e.target as HTMLDetailsElement).open)}
            >
              <summary className="cursor-pointer text-xs text-slate-500">
                raw source
              </summary>
              <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 text-[10px] text-slate-700">
                {active.url}
              </pre>
            </details>
          </div>
        ) : (
          <Empty>Select an item.</Empty>
        )}
      </Card>
    </div>
  );
}
