import type { ReportOut } from "../api";

type VoiceMetrics = NonNullable<ReportOut["voice_metrics"]>;

const PACE_MIN = 110;
const PACE_MAX = 170;

function Chips({ words }: { words: string[] }) {
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {words.map((word) => (
        <span
          key={word}
          className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
        >
          {word}
        </span>
      ))}
    </div>
  );
}

export function SpeakingStats({ metrics }: { metrics: VoiceMetrics | null }) {
  if (!metrics) return null;

  return (
    <section>
      <h2 className="font-heading text-lg font-semibold">Speaking stats</h2>
      <div className="mt-2 grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-xs font-medium text-muted-foreground">Pace</p>
          {metrics.pace_measured ? (
            <p className="mt-1 text-sm">
              {Math.round(metrics.wpm)} words per minute{" "}
              <span className="text-muted-foreground">
                (target {PACE_MIN}–{PACE_MAX})
              </span>
            </p>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">
              Not enough speech to measure pace yet
            </p>
          )}
        </div>

        <div>
          <p className="text-xs font-medium text-muted-foreground">Filler words</p>
          <p className="mt-1 text-sm">
            {metrics.filler_count} ({metrics.filler_rate_per_100.toFixed(1)} per 100 words)
          </p>
          {metrics.filler_examples.length > 0 && <Chips words={metrics.filler_examples} />}
        </div>

        <div>
          <p className="text-xs font-medium text-muted-foreground">Long pauses</p>
          <p className="mt-1 text-sm">{metrics.long_pauses_per_min.toFixed(1)} per minute</p>
        </div>

        {metrics.hard_to_catch_words.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground">
              Words that were hard to catch
            </p>
            <Chips words={metrics.hard_to_catch_words} />
            <p className="mt-1.5 text-xs text-muted-foreground">
              This can be caused by background noise or speaking fast — it doesn&apos;t necessarily
              mean mispronunciation.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
