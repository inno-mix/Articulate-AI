import { cn } from "@/lib/utils";

const LABELS = { 1: "Easy", 2: "Medium", 3: "Hard" } as const;

export function DifficultyBadge({
  difficulty,
  className,
}: {
  difficulty: 1 | 2 | 3;
  className?: string;
}) {
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 text-sm text-muted-foreground", className)}
    >
      <span className="flex items-center gap-0.5" aria-hidden>
        {[1, 2, 3].map((dot) => (
          <span
            key={dot}
            className={cn("size-1.5 rounded-full", dot <= difficulty ? "bg-primary" : "bg-border")}
          />
        ))}
      </span>
      {LABELS[difficulty]}
    </span>
  );
}
