import { LightbulbIcon } from "lucide-react";

import { Button } from "@/components/ui/button";

export function HintCallout({
  hint,
  onUse,
  onDismiss,
}: {
  hint: string;
  onUse: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="flex items-start gap-2.5 rounded-lg bg-accent px-3.5 py-3 text-sm text-accent-foreground">
      <LightbulbIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p className="flex-1">{hint}</p>
      <div className="flex shrink-0 gap-1.5">
        <Button type="button" size="sm" onClick={onUse}>
          Use this
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    </div>
  );
}
