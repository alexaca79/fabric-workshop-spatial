import { coverageTone, daysAgo, hectares, percent } from '../format';
import type { PeriodSummary } from '../../rayfin/data/PeriodSummary';

type Props = { summary: PeriodSummary };

export function KpiRow({ summary }: Props) {
  const tone = coverageTone(summary.trustedCoverage);

  return (
    <section className="kpi-row" aria-label="Period summary">
      <Kpi
        label="Area classified"
        value={hectares(summary.areaTotalHa)}
        note={`${summary.standsClassified} of ${summary.standsTotal} stands`}
      />
      <Kpi
        label="Usable imagery"
        value={percent(summary.trustedCoverage)}
        note={
          tone === 'good'
            ? 'Enough cloud-free pixels to trust'
            : 'Low coverage, read the numbers with care'
        }
        tone={tone}
      />
      <Kpi
        label="Harvested this period"
        value={hectares(summary.areaHarvestedHa)}
        note={`${percent(summary.areaHarvestedHa / Math.max(summary.areaTotalHa, 1), 1)} of classified area`}
      />
      <Kpi
        label="Needs a look"
        value={String(summary.standsNeedingReview)}
        note="Stands flagged for review"
        tone={summary.standsNeedingReview > 0 ? 'warn' : 'good'}
      />
      <Kpi
        label="Last refreshed"
        value={daysAgo(summary.publishedAt)}
        note={`Method ${summary.classMethod} · ${summary.sceneCount} scenes`}
      />
    </section>
  );
}

function Kpi({
  label,
  value,
  note,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  note: string;
  tone?: 'neutral' | 'good' | 'warn' | 'bad';
}) {
  return (
    <article className={`kpi kpi--${tone}`}>
      <p className="kpi__label">{label}</p>
      <p className="kpi__value">{value}</p>
      <p className="kpi__note">{note}</p>
    </article>
  );
}
