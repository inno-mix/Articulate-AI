import type { components } from "./schema";

export type MessageOut = components["schemas"]["MessageOut"];

/** Mirrors api-contract.md §4 (Server-Sent Events). */
export type ChatStreamEvent =
  | { event: "user_message"; data: MessageOut }
  | { event: "delta"; data: { text: string } }
  | { event: "assistant_message"; data: MessageOut }
  | { event: "done"; data: { user_turns: number; turns_left: number } }
  | { event: "error"; data: { code: string; message: string } };
