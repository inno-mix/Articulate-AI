export function scoreLabel(score: number): string {
  if (score >= 85) return "Excellent";
  if (score >= 70) return "Good";
  if (score >= 40) return "Getting there";
  return "Needs work";
}

export function ScoreNumber({ score }: { score: number }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-5xl font-semibold tabular-nums">{score}</span>
      <span className="text-muted-foreground">/100</span>
      <span className="text-sm font-medium text-muted-foreground">{scoreLabel(score)}</span>
    </div>
  );
}
