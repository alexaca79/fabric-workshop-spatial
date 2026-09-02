import { CLASS_LABELS, hectares, percent } from '../format';
import type { ClassBreakdown } from '../../rayfin/data/ClassBreakdown';

type Props = { rows: ClassBreakdown[] };

export function ClassBar({ rows }: Props) {
  const ordered = [...rows].sort((a, b) => a.displayOrder - b.displayOrder);
  const total = ordered.reduce((sum, row) => sum + row.areaHa, 0);

  if (total === 0) {
    return <p className="empty">No classified area for this period.</p>;
  }

  return (
    <section className="panel" aria-label="Area by forest class">
      <header className="panel__header">
        <h2>Area by forest class</h2>
        <span className="panel__meta">{hectares(total)} total</span>
      </header>

      <div className="stack" role="img" aria-label="Proportion of area by forest class">
        {ordered.map((row) => (
          <div
            key={row.forestClass}
            className="stack__segment"
            style={{ width: `${row.areaShare * 100}%`, background: row.colourHex }}
            title={`${CLASS_LABELS[row.forestClass]} · ${hectares(row.areaHa)}`}
          />
        ))}
      </div>

      <ul className="legend">
        {ordered.map((row) => (
          <li key={row.forestClass} className="legend__item">
            <span className="legend__swatch" style={{ background: row.colourHex }} aria-hidden />
            <span className="legend__label">{CLASS_LABELS[row.forestClass] ?? row.forestClass}</span>
            <span className="legend__value">{hectares(row.areaHa)}</span>
            <span className="legend__share">{percent(row.areaShare, 1)}</span>
            <span className="legend__count">{row.standCount} stands</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
