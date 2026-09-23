import type { components } from "./schema";

export type MessageOut = components["schemas"]["MessageOut"];

/** Mirrors api-contract.md §4 (Server-Sent Events). */
export type ChatStreamEvent =
  | { event: "user_message"; data: MessageOut }
  | { event: "delta"; data: { text: string } }
  | { event: "assistant_message"; data: MessageOut }
  | { event: "done"; data: { user_turns: number; turns_left: number } }
  | { event: "error"; data: { code: string; message: string } };

export type VoiceInputMode = components["schemas"]["VoiceInputMode"];

/** Mirrors voice-and-pronunciation.md §2.2 (client → server text frames). */
export type VoiceClientMessage =
  | { type: "start"; input_mode: VoiceInputMode }
  | { type: "ptt_down" }
  | { type: "ptt_up" }
  | { type: "cancel_turn" }
  | { type: "resume" }
  | { type: "end_session" }
  | { type: "ping" };

/** Mirrors voice-and-pronunciation.md §2.3 (server → client text frames; binary audio is separate). */
export type VoiceServerJsonEvent =
  | { type: "ready"; state: "idle" | "listening"; stt_model: string }
  | { type: "state"; value: "idle" | "listening" | "thinking" | "speaking" }
  | { type: "transcript"; text: string; is_final: boolean }
  | { type: "user_turn"; message: MessageOut }
  | { type: "assistant_delta"; text: string }
  | { type: "assistant_turn"; message: MessageOut }
  | { type: "audio_end" }
  | {
      type: "limit";
      reason: "turn_too_long" | "session_too_long" | "turn_limit_reached" | "daily_voice_limit";
    }
  | { type: "error"; code: string; message: string; fatal: boolean }
  | { type: "session_ended"; status: "ended" | "abandoned"; report_status: "pending" | null }
  | { type: "paused"; reason: "no_speech" }
  | { type: "pong" };
