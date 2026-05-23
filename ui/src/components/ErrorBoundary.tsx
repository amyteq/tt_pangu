import { Component, type ReactNode } from "react";

interface State {
  error: Error | null;
}

const isDev = import.meta.env.DEV;

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error): void {
    console.error("[ErrorBoundary]", error);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="p-6">
          <h2 className="text-lg font-semibold text-red-700">
            Something went wrong.
          </h2>
          {isDev && (
            <pre className="mt-4 whitespace-pre-wrap rounded bg-red-50 p-4 text-xs text-red-900">
              {this.state.error.stack || this.state.error.message}
            </pre>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}
