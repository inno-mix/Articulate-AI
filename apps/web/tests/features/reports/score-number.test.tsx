import { describe, expect, it } from "vitest";

import { scoreLabel } from "@/components/score-number";

describe("scoreLabel", () => {
  it.each([
    [0, "Needs work"],
    [39, "Needs work"],
    [40, "Getting there"],
    [69, "Getting there"],
    [70, "Good"],
    [84, "Good"],
    [85, "Excellent"],
    [100, "Excellent"],
  ])("scoreLabel(%i) === %s", (score, expected) => {
    expect(scoreLabel(score)).toBe(expected);
  });
});
