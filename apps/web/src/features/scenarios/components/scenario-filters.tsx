"use client";

import type { ReactNode } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

import type { RecommendedMode, ScenarioCategory } from "../api";
import { CATEGORY_LABELS, CATEGORY_OPTIONS } from "../labels";

const CATEGORY_SELECT_LABELS: Record<ScenarioCategory | "all", string> = {
  all: "All categories",
  ...CATEGORY_LABELS,
};

export type ScenarioFilterValues = {
  category: ScenarioCategory | "all";
  difficulty: "all" | "1" | "2" | "3";
  mode: RecommendedMode | "all";
};

const DIFFICULTY_OPTIONS = [
  { value: "all", label: "All" },
  { value: "1", label: "Easy" },
  { value: "2", label: "Medium" },
  { value: "3", label: "Hard" },
] as const;

const MODE_OPTIONS = [
  { value: "all", label: "Any" },
  { value: "text", label: "Text" },
  { value: "voice", label: "Voice" },
] as const;

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-3 py-1 text-sm transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border text-muted-foreground hover:bg-muted",
      )}
    >
      {children}
    </button>
  );
}

export function ScenarioFilters({
  value,
  onChange,
}: {
  value: ScenarioFilterValues;
  onChange: (next: ScenarioFilterValues) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
      <Select<ScenarioCategory | "all">
        value={value.category}
        onValueChange={(category) => onChange({ ...value, category: category ?? "all" })}
      >
        <SelectTrigger className="w-60" aria-label="Category">
          <SelectValue>
            {(category: ScenarioCategory | "all") => CATEGORY_SELECT_LABELS[category]}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All categories</SelectItem>
          {CATEGORY_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div role="group" aria-label="Difficulty" className="flex items-center gap-1.5">
        {DIFFICULTY_OPTIONS.map((option) => (
          <Chip
            key={option.value}
            active={value.difficulty === option.value}
            onClick={() => onChange({ ...value, difficulty: option.value })}
          >
            {option.label}
          </Chip>
        ))}
      </div>

      <div role="group" aria-label="Mode" className="flex items-center gap-1.5">
        {MODE_OPTIONS.map((option) => (
          <Chip
            key={option.value}
            active={value.mode === option.value}
            onClick={() => onChange({ ...value, mode: option.value })}
          >
            {option.label}
          </Chip>
        ))}
      </div>
    </div>
  );
}
