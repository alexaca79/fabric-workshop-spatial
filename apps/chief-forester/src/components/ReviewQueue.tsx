import { CHANGE_LABELS, CLASS_LABELS, hectares } from '../format';
import type { StandSnapshot } from '../../rayfin/data/StandSnapshot';

type Props = {
  rows: StandSnapshot[];
  selectedId: string | null;
  onSelect: (stand: StandSnapshot) => void;
};

export function ReviewQueue({ rows, selectedId, onSelect }: Props) {
  if (rows.length === 0) {
    return (
      <section className="panel" aria-label="Review queue">
        <header className="panel__header">
          <h2>Review queue</h2>
        </header>
        <p className="empty">
          Nothing flagged this period. That is a result, not an empty state.
        </p>
      </section>
    );
  }

  return (
    <section className="panel" aria-label="Review queue">
      <header className="panel__header">
        <h2>Review queue</h2>
        <span className="panel__meta">{rows.length} stands, highest severity first</span>
      </header>

      <table className="queue">
        <thead>
          <tr>
            <th scope="col">Stand</th>
            <th scope="col">Block</th>
            <th scope="col">Class</th>
            <th scope="col">What changed</th>
            <th scope="col" className="num">Area</th>
            <th scope="col">Severity</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((stand) => (
            <tr
              key={stand.id}
              className={stand.id === selectedId ? 'is-selected' : undefined}
              onClick={() => onSelect(stand)}
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  onSelect(stand);
                }
              }}
            >
              <td className="mono">{stand.standId}</td>
              <td>{stand.licenceBlock}</td>
              <td>{CLASS_LABELS[stand.forestClass] ?? stand.forestClass}</td>
              <td>{CHANGE_LABELS[stand.changeType] ?? stand.changeType}</td>
              <td className="num">{hectares(stand.areaHa)}</td>
              <td>
                <span className={`pill pill--${stand.severity}`}>{stand.severity}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
