import { cn } from "cn";

export function ScoreDots({ score, max = 5 }: { score: number; max?: number }) {
  return (
    <span className="inline-flex items-center gap-1" aria-hidden>
      {Array.from({ length: max }, (_, index) => (
        <span
          key={index}
          className={cn("size-2 rounded-full", index < score ? "bg-primary" : "bg-muted")}
        />
      ))}
    </span>
  );
}
