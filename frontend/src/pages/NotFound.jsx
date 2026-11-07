import { Button, Card, EmptyState } from '../components/ui';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

export function NotFound() {
  useDocumentTitle('Page not found');

  return (
    <Card className="mx-auto max-w-lg overflow-hidden">
      <EmptyState
        icon="search"
        title="This page does not exist"
        description="The link may be out of date. Head back to the overview to pick up where you left off."
        action={
          <Button variant="primary" size="sm" to="/" icon="home">
            Back to overview
          </Button>
        }
      />
    </Card>
  );
}
