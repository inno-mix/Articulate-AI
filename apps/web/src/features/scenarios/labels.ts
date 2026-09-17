import type { ScenarioCategory } from "./api";

export const CATEGORY_LABELS: Record<ScenarioCategory, string> = {
  status_updates: "Status updates",
  stakeholder_communication: "Stakeholder communication",
  interviews: "Interviews",
  code_review: "Code review",
  negotiation: "Negotiation",
  meetings: "Meetings",
  career: "Career",
};

export const CATEGORY_OPTIONS = Object.entries(CATEGORY_LABELS).map(([value, label]) => ({
  value: value as ScenarioCategory,
  label,
}));
