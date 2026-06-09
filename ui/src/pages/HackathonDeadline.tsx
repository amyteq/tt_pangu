/**
 * HackathonDeadline — M12-T005.
 *
 * Route: `/hackathons/:slug/deadline`.
 *
 * Reads:
 *  - `competitions` row by slug (uses `competitions.deadline` +
 *    `competitions.competition_type` from migration 0008).
 *  - `teams` (filtered by `competition_id`) + `team_memberships` for the
 *    slug's team. Per ADR-0016, M12 ships read-only team membership; the
 *    UI just renders the roster.
 *
 * Renders:
 *  - Live countdown (re-rendered every second from the client clock).
 *  - Phase chip: `deadline > now()` → "open"; else "closed". Richer
 *    phase strings (submission-pending, judging, …) are deferred per the
 *    task spec.
 *  - Team roster table (name + role; read-only).
 *
 * No mutation. No new UI library.
 */
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Badge, Card, Empty, Spinner, Table } from "../ui";
import {
  db,
  type Competition,
  type Team,
  type TeamMembership,
} from "../lib/db";

interface CountdownParts {
  expired: boolean;
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  totalMs: number;
}

function diffParts(deadlineIso: string | null | undefined, nowMs: number): CountdownParts {
  if (!deadlineIso) {
    return { expired: true, days: 0, hours: 0, minutes: 0, seconds: 0, totalMs: 0 };
  }
  const total = new Date(deadlineIso).getTime() - nowMs;
  if (isNaN(total) || total <= 0) {
    return { expired: true, days: 0, hours: 0, minutes: 0, seconds: 0, totalMs: 0 };
  }
  const s = Math.floor(total / 1000);
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const seconds = s % 60;
  return { expired: false, days, hours, minutes, seconds, totalMs: total };
}

function formatCountdown(p: CountdownParts): string {
  if (p.expired) return "closed";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${p.days}d ${pad(p.hours)}h ${pad(p.minutes)}m ${pad(p.seconds)}s`;
}

export function HackathonDeadline(): JSX.Element {
  const { slug = "" } = useParams<{ slug: string }>();
  const [competition, setCompetition] = useState<Competition | null>(null);
  const [team, setTeam] = useState<Team | null>(null);
  const [members, setMembers] = useState<TeamMembership[]>([]);
  const [loading, setLoading] = useState(true);
  const [nowMs, setNowMs] = useState<number>(() => Date.now());

  useEffect(() => {
    let live = true;
    setLoading(true);
    db.getCompetitionBySlug(slug)
      .then(async (c) => {
        if (!live) return;
        setCompetition(c);
        if (!c) return;
        const teams = await db.listTeamsForCompetition(c.id);
        if (!live) return;
        const first = teams[0] ?? null;
        setTeam(first);
        if (first) {
          const ms = await db.listTeamMemberships(first.id);
          if (live) setMembers(ms);
        }
      })
      .catch(() => {
        if (live) {
          setCompetition(null);
          setTeam(null);
          setMembers([]);
        }
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [slug]);

  // Re-render every second so the countdown ticks.
  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const parts = useMemo(
    () => diffParts(competition?.deadline ?? null, nowMs),
    [competition, nowMs],
  );
  const phase: "open" | "closed" = parts.expired ? "closed" : "open";

  if (loading) return <Spinner />;

  if (!competition) {
    return (
      <Card title="Hackathon deadline">
        <Empty>
          No competition with slug <code className="font-mono">{slug}</code> —
          register it via <code className="font-mono">kca devpost register</code>.
        </Empty>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card title={competition.title ?? competition.slug}>
        <div className="flex flex-wrap items-baseline gap-4">
          <div className="flex flex-col">
            <span className="text-xs uppercase tracking-wide text-slate-500">
              Countdown
            </span>
            <span
              data-testid="countdown"
              className="font-mono text-2xl text-slate-800"
            >
              {formatCountdown(parts)}
            </span>
            <span className="mt-1 text-xs text-slate-500">
              deadline{" "}
              <span className="font-mono">
                {competition.deadline ? competition.deadline.slice(0, 19) : "—"}
              </span>
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs uppercase tracking-wide text-slate-500">
              Phase
            </span>
            <Badge color={phase === "open" ? "green" : "red"}>{phase}</Badge>
          </div>
          <div className="flex flex-col">
            <span className="text-xs uppercase tracking-wide text-slate-500">
              Type
            </span>
            <Badge color="indigo">
              {competition.competition_type ?? competition.platform}
            </Badge>
          </div>
        </div>
      </Card>

      <Card title={team ? `Team: ${team.name}` : "Team"}>
        {team ? (
          <Table
            rows={members}
            columns={[
              {
                key: "user_id",
                header: "Member",
                render: (m) => (
                  <span className="font-mono text-xs">{m.user_id}</span>
                ),
              },
              {
                key: "role",
                header: "Role",
                render: (m) => <Badge color="slate">{m.role}</Badge>,
              },
              {
                key: "joined",
                header: "Joined",
                render: (m) => m.created_at.slice(0, 19),
              },
            ]}
            empty={<Empty>No members on this team yet.</Empty>}
          />
        ) : (
          <Empty>No team registered for this hackathon yet.</Empty>
        )}
      </Card>
    </div>
  );
}
