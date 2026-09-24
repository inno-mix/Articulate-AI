import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SpeakingStats } from "@/features/reports/components/speaking-stats";

function metrics(overrides: Partial<Parameters<typeof SpeakingStats>[0]["metrics"]> = {}) {
  return {
    speaking_seconds: 42,
    words: 90,
    wpm: 128,
    pace_measured: true,
    filler_count: 3,
    filler_rate_per_100: 3.3,
    filler_examples: ["um", "uh"],
    long_pause_count: 1,
    long_pauses_per_min: 1.43,
    hard_to_catch_words: ["asynchronous"],
    fluency_score: 4,
    ...overrides,
  };
}

describe("SpeakingStats", () => {
  it("renders pace, filler, and long-pause values", () => {
    render(<SpeakingStats metrics={metrics()} />);

    expect(screen.getByText("128 words per minute")).toBeInTheDocument();
    expect(screen.getByText("3 (3.3 per 100 words)")).toBeInTheDocument();
    expect(screen.getByText("um")).toBeInTheDocument();
    expect(screen.getByText("uh")).toBeInTheDocument();
    expect(screen.getByText("1.4 per minute")).toBeInTheDocument();
  });

  it("renders nothing when metrics is null", () => {
    const { container } = render(<SpeakingStats metrics={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("shows the hard-to-catch words with the caveat note", () => {
    render(<SpeakingStats metrics={metrics({ hard_to_catch_words: ["asynchronous"] })} />);

    expect(screen.getByText("Words that were hard to catch")).toBeInTheDocument();
    expect(screen.getByText("asynchronous")).toBeInTheDocument();
    expect(
      screen.getByText(
        "This can be caused by background noise or speaking fast — it doesn't necessarily mean mispronunciation.",
      ),
    ).toBeInTheDocument();
  });

  it("hides the hard-to-catch section when there are none", () => {
    render(<SpeakingStats metrics={metrics({ hard_to_catch_words: [] })} />);

    expect(screen.queryByText("Words that were hard to catch")).not.toBeInTheDocument();
  });

  it("shows 'not enough speech' text when pace_measured is false", () => {
    render(<SpeakingStats metrics={metrics({ pace_measured: false })} />);

    expect(screen.getByText("Not enough speech to measure pace yet")).toBeInTheDocument();
    expect(screen.queryByText(/words per minute/)).not.toBeInTheDocument();
  });
});
