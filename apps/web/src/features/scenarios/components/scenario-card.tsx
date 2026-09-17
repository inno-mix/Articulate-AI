import { AudioLines, MessageSquareText, Shuffle } from "lucide-react";
import Link from "next/link";

import { DifficultyBadge } from "@/components/difficulty-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { ScenarioSummary } from "../api";
import { CATEGORY_LABELS } from "../labels";

const MODE_ICON = { text: MessageSquareText, voice: AudioLines, either: Shuffle } as const;
const MODE_LABEL = { text: "Text", voice: "Voice", either: "Either" } as const;
const MODE_TITLE = { text: "Text", voice: "Voice", either: "Text or voice" } as const;

export function ScenarioCard({ scenario }: { scenario: ScenarioSummary }) {
  const ModeIcon = MODE_ICON[scenario.recommended_mode];
  return (
    <Link
      href={`/practice/${scenario.slug}`}
      className="block rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <Card className="h-full transition-shadow hover:shadow-md">
        <CardHeader>
          <p className="text-sm text-muted-foreground">{CATEGORY_LABELS[scenario.category]}</p>
          <CardTitle>{scenario.title}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-1 flex-col gap-3">
          <p className="line-clamp-2 text-sm text-muted-foreground">{scenario.summary}</p>
          <div className="mt-auto flex items-center justify-between pt-1">
            <DifficultyBadge difficulty={scenario.difficulty as 1 | 2 | 3} />
            <span
              className="flex shrink-0 items-center gap-1.5 text-sm text-muted-foreground"
              title={MODE_TITLE[scenario.recommended_mode]}
            >
              <ModeIcon className="size-4" aria-hidden />
              {MODE_LABEL[scenario.recommended_mode]}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
