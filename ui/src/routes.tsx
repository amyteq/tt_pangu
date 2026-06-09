import { Navigate, type RouteObject } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Runs } from "./pages/Runs";
import { RunTimeline } from "./pages/RunTimeline";
import { Experiments } from "./pages/Experiments";
import { RunDetail } from "./pages/RunDetail";
import { Research } from "./pages/Research";
import { ApprovalInbox } from "./pages/ApprovalInbox";
import { DecisionGate } from "./pages/DecisionGate";
import { Artifacts } from "./pages/Artifacts";
import { ArtifactDetail } from "./pages/ArtifactDetail";
import { HackathonDeadline } from "./pages/HackathonDeadline";
import { SubmissionChecklist } from "./pages/SubmissionChecklist";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "runs", element: <Runs /> },
      { path: "runs/:jobId", element: <RunTimeline /> },
      { path: "experiments", element: <Experiments /> },
      { path: "experiments/:experimentId", element: <RunDetail /> },
      { path: "research", element: <Research /> },
      { path: "approvals", element: <ApprovalInbox /> },
      { path: "approvals/:id", element: <DecisionGate /> },
      { path: "artifacts", element: <Artifacts /> },
      { path: "artifacts/:id", element: <ArtifactDetail /> },
      // M12-T005 hackathon pages.
      { path: "hackathons/:slug/deadline", element: <HackathonDeadline /> },
      {
        path: "hackathons/:slug/runs/:run_id/checklist",
        element: <SubmissionChecklist />,
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
];
