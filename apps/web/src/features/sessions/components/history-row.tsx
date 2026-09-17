"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

import type { SessionSummary } from "../api";
import { useDeleteSession } from "../hooks/use-delete-session";

const STATUS_LABEL = { active: "Active", ended: "Ended", abandoned: "Abandoned" } as const;
const MODE_LABEL = { text: "Text", voice: "Voice" } as const;

const DATE_FORMAT = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

export function HistoryRow({ session }: { session: SessionSummary }) {
  const deleteSession = useDeleteSession();

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-card px-4 py-3 ring-1 ring-foreground/10">
      <Link href={`/sessions/${session.id}`} className="min-w-0 flex-1">
        <p className="truncate font-medium">{session.scenario.title}</p>
        <p className="mt-0.5 text-sm text-muted-foreground">
          {MODE_LABEL[session.mode]} · {DATE_FORMAT.format(new Date(session.started_at))} ·{" "}
          {session.user_turns} {session.user_turns === 1 ? "turn" : "turns"}
        </p>
      </Link>
      <div className="flex items-center gap-3">
        <Badge variant={session.status === "active" ? "default" : "secondary"}>
          {STATUS_LABEL[session.status]}
        </Badge>
        <Dialog>
          <DialogTrigger render={<Button type="button" variant="ghost" size="sm" />}>
            Delete
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete this practice session?</DialogTitle>
              <DialogDescription>
                The conversation, its report and its scores will be removed.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <DialogClose render={<Button type="button" variant="outline" />}>Cancel</DialogClose>
              <DialogClose
                render={
                  <Button
                    type="button"
                    variant="destructive"
                    onClick={() => deleteSession.mutate(session.id)}
                  />
                }
              >
                Delete
              </DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </li>
  );
}
