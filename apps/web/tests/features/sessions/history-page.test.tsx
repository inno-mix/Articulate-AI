import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import HistoryPage from "@/app/sessions/page";
import type { SessionSummary } from "@/features/sessions/api";

import { API, server } from "../../msw";
import { renderWithProviders } from "../../render";

function summary(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    id: crypto.randomUUID(),
    scenario: { slug: "explain-tech-debt-to-pm", title: "Explain tech debt to your PM" },
    mode: "text",
    status: "ended",
    started_at: "2026-09-17T10:00:00Z",
    ended_at: "2026-09-17T10:10:00Z",
    user_turns: 4,
    ...overrides,
  };
}

describe("HistoryPage", () => {
  it("loads the next page and appends its rows", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${API}/sessions`, ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        if (!cursor) {
          return HttpResponse.json({
            items: [summary({ id: "s1", scenario: { slug: "a", title: "First session" } })],
            next_cursor: "page-2",
          });
        }
        return HttpResponse.json({
          items: [summary({ id: "s2", scenario: { slug: "b", title: "Second session" } })],
          next_cursor: null,
        });
      }),
    );

    renderWithProviders(<HistoryPage />);
    expect(await screen.findByText("First session")).toBeInTheDocument();
    expect(screen.queryByText("Second session")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Load more" }));

    expect(await screen.findByText("Second session")).toBeInTheDocument();
    expect(screen.getByText("First session")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("asks for confirmation before deleting, then removes the row", async () => {
    const user = userEvent.setup();
    let deleted = false;
    server.use(
      http.get(`${API}/sessions`, () =>
        HttpResponse.json({
          items: deleted
            ? []
            : [summary({ id: "s1", scenario: { slug: "a", title: "Delete me" } })],
          next_cursor: null,
        }),
      ),
      http.delete(`${API}/sessions/:id`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(<HistoryPage />);
    await screen.findByText("Delete me");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(
      "The conversation, its report and its scores will be removed.",
    );

    const confirmButtons = await screen.findAllByRole("button", { name: "Delete" });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(screen.queryByText("Delete me")).not.toBeInTheDocument());
  });
});
