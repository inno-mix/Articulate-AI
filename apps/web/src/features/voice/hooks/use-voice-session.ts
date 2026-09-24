"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { errorMessage } from "@/lib/api/errors";
import type { VoiceInputMode } from "@/lib/api/events";
import type { MessageOut } from "@/lib/api/events";
import { type AudioSource, MicCapture, MicPermissionError } from "@/lib/audio/mic-capture";
import { type AudioSink, PcmPlayer } from "@/lib/audio/pcm-player";
import { type VoiceServerEvent, VoiceSocket } from "@/lib/audio/voice-socket";

import { sessionKeys } from "@/features/sessions/query-keys";

import { voiceSocketUrl } from "../api";

export type VoicePhase = "not_started" | "connecting" | "ready" | "ended" | "failed";
export type VoiceCallState = "idle" | "listening" | "thinking" | "speaking";

const LEVEL_POLL_MS = 100;

const LIMIT_MESSAGES: Record<string, string> = {
  turn_too_long: "That turn ran long, so it was wrapped up automatically.",
  session_too_long: "You've reached the 20-minute session limit. Ending the session…",
  turn_limit_reached: "You've reached the turn limit for this session.",
  daily_voice_limit: "You've reached today's voice practice limit.",
};

export interface UseVoiceSessionOptions {
  sessionId: string;
  inputMode: VoiceInputMode;
  source?: AudioSource;
  sink?: AudioSink;
  socketFactory?: (url: string) => VoiceSocket;
}

export function useVoiceSession(opts: UseVoiceSessionOptions) {
  const { sessionId, inputMode } = opts;
  const queryClient = useQueryClient();

  const [phase, setPhase] = useState<VoicePhase>("not_started");
  const [state, setState] = useState<VoiceCallState>("idle");
  const [paused, setPaused] = useState(false);
  const [interimText, setInterimText] = useState("");
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [assistantDraft, setAssistantDraft] = useState("");
  const [level, setLevel] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  const socketRef = useRef<VoiceSocket | null>(null);
  const sourceRef = useRef<AudioSource | null>(opts.source ?? null);
  const sinkRef = useRef<AudioSink | null>(opts.sink ?? null);
  const stateRef = useRef<VoiceCallState>("idle");
  const expectingCloseRef = useRef(false);
  const startTimeRef = useRef<number | null>(null);
  const levelIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const elapsedIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const cleanupTimers = useCallback(() => {
    if (levelIntervalRef.current) clearInterval(levelIntervalRef.current);
    if (elapsedIntervalRef.current) clearInterval(elapsedIntervalRef.current);
    levelIntervalRef.current = null;
    elapsedIntervalRef.current = null;
  }, []);

  const stopAudio = useCallback(() => {
    cleanupTimers();
    sourceRef.current?.stop();
    sinkRef.current?.stop();
    setLevel(0);
  }, [cleanupTimers]);

  const handleClose = useCallback(() => {
    if (expectingCloseRef.current) return;
    stopAudio();
    setError({ code: "connection_lost", message: errorMessage("connection_lost") });
    setPhase("failed");
  }, [stopAudio]);

  const handleEvent = useCallback(
    (event: VoiceServerEvent) => {
      switch (event.type) {
        case "ready":
          setState(event.state);
          setPhase("ready");
          break;
        case "state":
          setState(event.value);
          if (event.value !== "idle") setPaused(false);
          break;
        case "transcript":
          setInterimText(event.is_final ? "" : event.text);
          break;
        case "user_turn":
          setMessages((prev) => [...prev, event.message]);
          setInterimText("");
          break;
        case "assistant_delta":
          setAssistantDraft((prev) => prev + event.text);
          break;
        case "assistant_turn":
          setMessages((prev) => [...prev, event.message]);
          setAssistantDraft("");
          break;
        case "audio":
          sinkRef.current?.enqueue(event.data);
          break;
        case "audio_end":
          break;
        case "paused":
          setPaused(true);
          break;
        case "limit":
          toast.warning(LIMIT_MESSAGES[event.reason] ?? "You've reached a session limit.");
          break;
        case "error":
          if (event.fatal) {
            expectingCloseRef.current = true;
            stopAudio();
            setError({ code: event.code, message: errorMessage(event.code) });
            setPhase("failed");
          } else {
            toast.error(errorMessage(event.code));
          }
          break;
        case "session_ended":
          expectingCloseRef.current = true;
          stopAudio();
          setPhase("ended");
          void queryClient.invalidateQueries({ queryKey: sessionKeys.detail(sessionId) });
          break;
        case "pong":
          break;
      }
    },
    [queryClient, sessionId, stopAudio],
  );

  const connect = useCallback(async () => {
    if (phase === "connecting" || phase === "ready") return;

    setPhase("connecting");
    setError(null);
    setPaused(false);
    expectingCloseRef.current = false;

    if (!sourceRef.current) sourceRef.current = new MicCapture();
    if (!sinkRef.current) sinkRef.current = new PcmPlayer();
    const source = sourceRef.current;
    const sink = sinkRef.current;

    try {
      await source.start((chunk) => {
        if (stateRef.current === "listening") socketRef.current?.sendAudio(chunk);
      });
      await sink.resume();

      const makeSocket = opts.socketFactory ?? ((url: string) => new VoiceSocket(url));
      const socket = makeSocket(voiceSocketUrl(sessionId));
      socketRef.current = socket;
      socket.onEvent(handleEvent);
      socket.onClose(handleClose);

      await socket.connect();
      socket.send({ type: "start", input_mode: inputMode });

      startTimeRef.current = Date.now();
      elapsedIntervalRef.current = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - (startTimeRef.current ?? Date.now())) / 1000));
      }, 1000);
      levelIntervalRef.current = setInterval(() => setLevel(source.level), LEVEL_POLL_MS);
    } catch (err) {
      stopAudio();
      const code = err instanceof MicPermissionError ? "mic_permission_denied" : "connection_lost";
      setError({ code, message: errorMessage(code) });
      setPhase("failed");
    }
  }, [phase, sessionId, inputMode, opts.socketFactory, handleEvent, handleClose, stopAudio]);

  const pttDown = useCallback(() => {
    socketRef.current?.send({ type: "ptt_down" });
  }, []);

  const pttUp = useCallback(() => {
    socketRef.current?.send({ type: "ptt_up" });
  }, []);

  const resume = useCallback(() => {
    socketRef.current?.send({ type: "resume" });
  }, []);

  const end = useCallback(async () => {
    expectingCloseRef.current = true;
    socketRef.current?.send({ type: "end_session" });
  }, []);

  useEffect(
    () => () => {
      expectingCloseRef.current = true;
      stopAudio();
      socketRef.current?.close();
    },
    [stopAudio],
  );

  return {
    phase,
    state,
    paused,
    interimText,
    messages,
    assistantDraft,
    level,
    elapsedSeconds,
    error,
    start: connect,
    pttDown,
    pttUp,
    resume,
    end,
    reconnect: connect,
  };
}
