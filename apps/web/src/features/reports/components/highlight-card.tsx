"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";

import type { ReportOut } from "../api";

type Highlight = NonNullable<ReportOut["highlights"]>[number];

export function HighlightCard({ highlight }: { highlight: Highlight }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(highlight.better_version);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <p className="text-xs font-medium text-muted-foreground">You said</p>
      <p className="mt-1 italic">&ldquo;{highlight.quote}&rdquo;</p>
      <p className="mt-3 text-xs font-medium text-muted-foreground">Why</p>
      <p className="mt-1 text-sm">{highlight.issue}</p>
      <p className="mt-3 text-xs font-medium text-muted-foreground">Try</p>
      <div className="mt-1 flex items-start justify-between gap-3">
        <p className="text-sm">{highlight.better_version}</p>
        <Button type="button" variant="ghost" size="sm" onClick={() => void handleCopy()}>
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
    </div>
  );
}
