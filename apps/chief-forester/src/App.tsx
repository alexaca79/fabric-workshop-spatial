import { useEffect, useMemo, useState } from 'react';

import { client, signIn } from './client';
import { ClassBar } from './components/ClassBar';
import { KpiRow } from './components/KpiRow';
import { ReviewQueue } from './components/ReviewQueue';
import { StandDetail } from './components/StandDetail';
import { shortDate } from './format';

import type { ClassBreakdown } from '../rayfin/data/ClassBreakdown';
import type { PeriodSummary } from '../rayfin/data/PeriodSummary';
import type { StandSnapshot } from '../rayfin/data/StandSnapshot';

const SEVERITY_RANK: Record<string, number> = { high: 0, moderate: 1, low: 2 };

export function App() {
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [message, setMessage] = useState<string>('Signing in');
  const [summary, setSummary] = useState<PeriodSummary | null>(null);
  const [breakdown, setBreakdown] = useState<ClassBreakdown[]>([]);
  const [stands, setStands] = useState<StandSnapshot[]>([]);
  const [selected, setSelected] = useState<StandSnapshot | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        await signIn();
        if (cancelled) return;
        setMessage('Loading the latest period');

        // Newest period first. One row is all the header needs.
        const summaries = await client.data.PeriodSummary.select([
          'id',
          'aoiName',
          'periodStart',
          'periodEnd',
          'standsTotal',
          'standsClassified',
          'trustedCoverage',
          'areaTotalHa',
          'areaHarvestedHa',
          'areaStressedHa',
          'standsNeedingReview',
          'narrativesGenerated',
          'classMethod',
          'sceneCount',
          'publishedAt',
          'pipelineRunId',
        ])
          .orderBy({ periodEnd: 'desc' })
          .first(1)
          .execute();

        if (cancelled) return;

        const latest = summaries[0] ?? null;
        setSummary(latest);

        if (!latest) {
          setStatus('ready');
          return;
        }

        const [classRows, queueRows] = await Promise.all([
          client.data.ClassBreakdown.select([
            'id',
            'periodEnd',
            'forestClass',
            'standCount',
            'areaHa',
            'areaShare',
            'displayOrder',
            'colourHex',
            'pipelineRunId',
          ])
            .where({ pipelineRunId: { eq: latest.pipelineRunId } })
            .execute(),

          client.data.StandSnapshot.select([
            'id',
            'standId',
            'licenceBlock',
            'periodEnd',
            'forestClass',
            'classConfidence',
            'areaHa',
            'changeType',
            'severity',
            'requiresReview',
            'isTrusted',
            'lat',
            'lon',
            'narrative',
            'narrativeStatus',
            'pipelineRunId',
          ])
            .where({ pipelineRunId: { eq: latest.pipelineRunId } })
            .where({ requiresReview: { eq: true } })
            .execute(),
        ]);

        if (cancelled) return;

        setBreakdown(classRows);
        setStands(queueRows);
        setStatus('ready');
      } catch (error) {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : 'Something went wrong');
        setStatus('error');
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const queue = useMemo(
    () =>
      [...stands].sort(
        (a, b) =>
          (SEVERITY_RANK[a.severity] ?? 3) - (SEVERITY_RANK[b.severity] ?? 3) ||
          b.areaHa - a.areaHa,
      ),
    [stands],
  );

  if (status === 'loading') {
    return <Splash title="Woodlands" note={message} />;
  }

  if (status === 'error') {
    return <Splash title="Cannot load the dashboard" note={message} tone="bad" />;
  }

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <p className="eyebrow">Woodlands · Chief Forester</p>
          <h1>Forest condition</h1>
        </div>
        {summary && (
          <p className="page__period">
            {summary.aoiName} · {shortDate(summary.periodStart)} to {shortDate(summary.periodEnd)}
          </p>
        )}
      </header>

      {summary ? (
        <>
          <KpiRow summary={summary} />
          <div className="grid">
            <div className="grid__main">
              <ClassBar rows={breakdown} />
              <ReviewQueue rows={queue} selectedId={selected?.id ?? null} onSelect={setSelected} />
            </div>
            <StandDetail stand={selected} />
          </div>
        </>
      ) : (
        <p className="empty">
          No period has been published yet. Run the pipeline, then notebook 06.
        </p>
      )}

      <footer className="page__footer">
        Classification is a decision support signal, not a substitute for field cruising. Every
        figure traces back to a Sentinel-2 scene through the silver layer.
      </footer>
    </div>
  );
}

function Splash({
  title,
  note,
  tone = 'neutral',
}: {
  title: string;
  note: string;
  tone?: 'neutral' | 'bad';
}) {
  return (
    <div className={`splash splash--${tone}`}>
      <h1>{title}</h1>
      <p>{note}</p>
    </div>
  );
}
