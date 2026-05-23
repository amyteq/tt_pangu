import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Card, Empty, Spinner } from "../ui";
import { db, type Artifact } from "../lib/db";
import { canPreview } from "../lib/artifacts";

export function ArtifactDetail(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const [a, setA] = useState<Artifact | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    db.getArtifact(id)
      .then(setA)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <Spinner />;
  if (!a)
    return (
      <Card>
        <Empty>Artifact not found.</Empty>
      </Card>
    );

  const verdict = canPreview(a.storage_path, a.byte_size);

  return (
    <div className="space-y-3">
      <Card title="Metadata">
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <dt className="text-xs text-slate-500">path</dt>
            <dd className="font-mono">{a.storage_path}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">kind</dt>
            <dd>{a.kind}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">size</dt>
            <dd>{a.byte_size?.toLocaleString() ?? "—"} bytes</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">sha256</dt>
            <dd className="font-mono text-xs">{a.content_hash ?? "—"}</dd>
          </div>
        </dl>
      </Card>
      <Card title="Preview">
        {!verdict.preview && (
          <div className="rounded bg-amber-50 px-3 py-2 text-sm text-amber-900">
            Preview unavailable: {verdict.reason}. Use the storage path to
            download manually.
          </div>
        )}
        {verdict.preview && (
          <p className="text-xs text-slate-500">
            Inline preview requires a storage HEAD/GET endpoint, planned for
            M9. Until then, the artifact is downloadable via{" "}
            <code className="rounded bg-slate-100 px-1">
              {a.storage_path}
            </code>
            .
          </p>
        )}
      </Card>
    </div>
  );
}
