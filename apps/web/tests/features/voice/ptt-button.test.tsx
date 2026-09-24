import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PttButton } from "@/features/voice/components/ptt-button";

describe("PttButton", () => {
  it("calls onDown/onUp on pointer press and release", () => {
    const onDown = vi.fn();
    const onUp = vi.fn();
    render(<PttButton active={false} disabled={false} onDown={onDown} onUp={onUp} />);
    const button = screen.getByRole("button");

    fireEvent.pointerDown(button, { pointerId: 1 });
    expect(onDown).toHaveBeenCalledTimes(1);

    fireEvent.pointerUp(button, { pointerId: 1 });
    expect(onUp).toHaveBeenCalledTimes(1);
  });

  it("sends down/up once for Space, ignoring key repeat", () => {
    const onDown = vi.fn();
    const onUp = vi.fn();
    render(<PttButton active={false} disabled={false} onDown={onDown} onUp={onUp} />);

    fireEvent.keyDown(window, { code: "Space" });
    fireEvent.keyDown(window, { code: "Space", repeat: true });
    fireEvent.keyDown(window, { code: "Space", repeat: true });
    expect(onDown).toHaveBeenCalledTimes(1);

    fireEvent.keyUp(window, { code: "Space" });
    expect(onUp).toHaveBeenCalledTimes(1);
  });

  it("releases on window blur", () => {
    const onDown = vi.fn();
    const onUp = vi.fn();
    render(<PttButton active={false} disabled={false} onDown={onDown} onUp={onUp} />);

    fireEvent.keyDown(window, { code: "Space" });
    expect(onDown).toHaveBeenCalledTimes(1);

    fireEvent.blur(window);
    expect(onUp).toHaveBeenCalledTimes(1);
  });

  it("ignores presses while disabled", () => {
    const onDown = vi.fn();
    render(<PttButton active={false} disabled onDown={onDown} onUp={vi.fn()} />);

    fireEvent.keyDown(window, { code: "Space" });

    expect(onDown).not.toHaveBeenCalled();
  });

  it("shows Listening… while active", () => {
    render(<PttButton active onDown={vi.fn()} onUp={vi.fn()} disabled={false} />);

    expect(screen.getByRole("button", { name: "Listening…" })).toBeInTheDocument();
  });
});
