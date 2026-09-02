import { CHANGE_LABELS, CLASS_LABELS, hectares, percent, shortDate } from '../format';
import type { StandSnapshot } from '../../rayfin/data/StandSnapshot';

type Props = { stand: StandSnapshot | null };

export function StandDetail({ stand }: Props) {
  if (!stand) {
    return (
      <aside className="panel panel--side" aria-label="Stand detail">
        <header className="panel__header">
          <h2>Stand detail</h2>
        </header>
        <p className="empty">Select a stand from the queue.</p>
      </aside>
    );
  }

  const validated = stand.narrativeStatus === 'ok' || stand.narrativeStatus === 'stubbed';

  return (
    <aside className="panel panel--side" aria-label="Stand detail">
      <header className="panel__header">
        <h2>{stand.standId}</h2>
        <span className="panel__meta">{stand.licenceBlock}</span>
      </header>

      <p className={`narrative ${validated ? '' : 'narrative--suppressed'}`}>
        {validated && stand.narrative
          ? stand.narrative
          : 'No validated summary for this stand and period.'}
      </p>

      {!validated && (
        <p className="narrative__flag">
          Suppressed by the guardrail: <span className="mono">{stand.narrativeStatus}</span>. The
          numbers below still stand; only the generated sentence was withheld.
        </p>
      )}

      <dl className="facts">
        <Fact label="Class" value={CLASS_LABELS[stand.forestClass] ?? stand.forestClass} />
        <Fact label="Confidence" value={percent(stand.classConfidence, 0)} />
        <Fact label="Area" value={hectares(stand.areaHa)} />
        <Fact label="Change" value={CHANGE_LABELS[stand.changeType] ?? stand.changeType} />
        <Fact label="Severity" value={stand.severity} />
        <Fact label="Period end" value={shortDate(stand.periodEnd)} />
        <Fact label="Imagery" value={stand.isTrusted ? 'Usable' : 'Too cloudy to trust'} />
      </dl>

      <a
        className="maplink"
        href={`https://www.bing.com/maps?cp=${stand.lat}~${stand.lon}&lvl=14&style=a`}
        target="_blank"
        rel="noreferrer"
      >
        Open location in maps
      </a>

      <p className="provenance">
        Run <span className="mono">{stand.pipelineRunId}</span>. Every number here traces back to a
        silver observation and a Sentinel-2 scene.
      </p>
    </aside>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}
