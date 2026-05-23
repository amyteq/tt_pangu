import { useRoutes } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { routes } from "./routes";

function AppRoutes(): JSX.Element {
  const element = useRoutes(routes);
  return element ?? <h1 className="p-4 text-2xl">kaggle-code-agent</h1>;
}

export function App(): JSX.Element {
  return (
    <ErrorBoundary>
      <AppRoutes />
    </ErrorBoundary>
  );
}
