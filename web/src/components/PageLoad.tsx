import { Component, Suspense, type ReactNode } from 'react';
import { useLocation } from 'react-router';
import { btn } from './ui';

/** Pages load on demand, and that can fail after a deploy or on bad Wi-Fi. Without this, the whole app goes blank. */
class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="flex flex-col items-start gap-2">
        <p className="text-crit">This page couldn't load. Check the connection, then reload.</p>
        <button className={`${btn.base} ${btn.primary} min-h-11`} onClick={() => window.location.reload()}>Reload</button>
      </div>
    );
  }
}

export function PageLoad({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return (
    <Boundary key={pathname}>
      <Suspense fallback={<p className="text-muted">Loading…</p>}>{children}</Suspense>
    </Boundary>
  );
}
