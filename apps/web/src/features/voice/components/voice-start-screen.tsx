"use client";

import { Loader2Icon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { VoiceInputMode } from "@/lib/api/events";

export function VoiceStartScreen({
  inputMode,
  onInputModeChange,
  onStart,
  connecting,
}: {
  inputMode: VoiceInputMode;
  onInputModeChange: (mode: VoiceInputMode) => void;
  onStart: () => void;
  connecting: boolean;
}) {
  return (
    <div className="mx-auto max-w-md space-y-6 py-12 text-center">
      <div>
        <h1 className="font-heading text-xl font-semibold">Ready for voice practice?</h1>
        <p className="mt-1 text-sm text-muted-foreground">Hold Space or the button to talk.</p>
      </div>

      <Tabs value={inputMode} onValueChange={(value) => onInputModeChange(value as VoiceInputMode)}>
        <TabsList className="mx-auto">
          <TabsTrigger value="push_to_talk">Push to talk</TabsTrigger>
          <TabsTrigger value="hands_free">Hands-free</TabsTrigger>
        </TabsList>
      </Tabs>

      <Button type="button" size="lg" onClick={onStart} disabled={connecting}>
        {connecting && <Loader2Icon className="animate-spin" aria-hidden />}
        Start voice session
      </Button>
    </div>
  );
}
