import { ScoreDots } from "@/components/score-dots";

import { DIMENSION_LABELS } from "../dimensions";

export function SkillRow({
  dimension,
  score,
  reason,
}: {
  dimension: string;
  score: number;
  reason: string;
}) {
  const label = DIMENSION_LABELS[dimension] ?? dimension;
  return (
    <div className="flex flex-col gap-1 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium">{label}</span>
        <span
          className="flex items-center gap-2 text-sm text-muted-foreground"
          aria-label={`${label}: ${score} out of 5`}
        >
          <ScoreDots score={score} />
          {score}/5
        </span>
      </div>
      <p className="text-sm text-muted-foreground">{reason}</p>
    </div>
  );
}
