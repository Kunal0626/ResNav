import { useEffect, useState } from 'react';
import { exampleQueries, isDemo } from '../lib/demo';
import { Icon } from './ui/Icon';

/**
 * The searches the demo can actually answer.
 *
 * Free-text search runs on the server, and the demo has no server, so the
 * snapshot carries a fixed set of queries that were put through the real
 * ranker. Offering them as buttons turns a dead search box into a working
 * one for those inputs, without pretending the rest work.
 */
export function DemoExamples({ onPick, className }) {
  const [queries, setQueries] = useState([]);

  useEffect(() => {
    if (!isDemo) return undefined;
    let live = true;
    exampleQueries().then((q) => {
      if (live) setQueries(q);
    });
    return () => {
      live = false;
    };
  }, []);

  if (!isDemo || queries.length === 0) return null;

  return (
    <div className={className}>
      <p className="mb-2 flex items-center gap-1.5 text-[0.6875rem] text-[var(--rn-text-3)]">
        <Icon name="search" className="h-3 w-3" aria-hidden="true" />
        Searches this demo can answer
      </p>
      <div className="flex flex-wrap gap-1.5">
        {queries.map((q) => (
          <button key={q} type="button" className="demo-chip" onClick={() => onPick(q)}>
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
