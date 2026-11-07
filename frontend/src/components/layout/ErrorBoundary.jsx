import { Component } from 'react';
import { Button, Card, ErrorState } from '../ui';

/**
 * Catches render-time crashes so one broken panel does not blank the whole app.
 * The original had no equivalent: any template error produced a raw JSON
 * traceback in place of the page.
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Left as console.error deliberately: this is the one place a stack trace
    // is genuinely useful, and it never reaches an end user's screen.
    console.error('Unhandled UI error:', error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <Card className="mx-auto my-10 max-w-xl overflow-hidden">
        <ErrorState
          title="Something went wrong on this screen"
          error={{ message: this.state.error.message, isRetryable: false }}
        />
        <div className="flex justify-center gap-2 border-t border-[var(--rn-border)] p-4">
          <Button variant="ghost" size="sm" onClick={() => this.setState({ error: null })}>
            Dismiss
          </Button>
          <Button variant="primary" size="sm" onClick={() => window.location.reload()}>
            Reload the page
          </Button>
        </div>
      </Card>
    );
  }
}
