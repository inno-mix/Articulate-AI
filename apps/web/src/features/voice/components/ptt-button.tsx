"use client";

import type { PointerEvent as ReactPointerEvent } from "react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function capturePointer(event: ReactPointerEvent<HTMLButtonElement>): void {
  try {
    event.currentTarget.setPointerCapture(event.pointerId);
  } catch {
    // Pointer capture isn't implemented everywhere (e.g. jsdom) — plain pointerup still fires.
  }
}

/** Hold-to-talk button: pointer press/release, Space bar, released on window blur. */
export function PttButton({
  active,
  disabled,
  onDown,
  onUp,
}: {
  active: boolean;
  disabled: boolean;
  onDown: () => void;
  onUp: () => void;
}) {
  const heldRef = useRef(false);
  const disabledRef = useRef(disabled);
  useEffect(() => {
    disabledRef.current = disabled;
  }, [disabled]);

  function down() {
    if (heldRef.current || disabledRef.current) return;
    heldRef.current = true;
    onDown();
  }

  function up() {
    if (!heldRef.current) return;
    heldRef.current = false;
    onUp();
  }

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.code !== "Space" || event.repeat) return;
      event.preventDefault();
      down();
    }
    function handleKeyUp(event: KeyboardEvent) {
      if (event.code !== "Space") return;
      event.preventDefault();
      up();
    }
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    window.addEventListener("blur", up);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("blur", up);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- down/up read disabled via a ref
  }, []);

  return (
    <Button
      type="button"
      disabled={disabled}
      aria-pressed={active}
      onPointerDown={(event) => {
        capturePointer(event);
        down();
      }}
      onPointerUp={up}
      onPointerCancel={up}
      className={cn(
        "h-24 w-24 rounded-full text-base",
        active && "bg-primary/80 ring-4 ring-primary/30",
      )}
    >
      {active ? "Listening…" : "Hold to talk"}
    </Button>
  );
}
