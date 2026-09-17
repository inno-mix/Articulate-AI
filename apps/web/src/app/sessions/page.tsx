"use client";

import { HistoryIcon } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { HistoryRow } from "@/features/sessions/components/history-row";
import { useSessionsHistory } from "@/features/sessions/hooks/use-sessions-history";

export default function HistoryPage() {
  const { data, isPending, isError, refetch, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useSessionsHistory();

  const sessions = data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="max-w-2xl">
      <header className="mb-8">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">History</h1>
        <p className="mt-2 text-muted-foreground">Every practice session you&apos;ve started.</p>
      </header>

      {isPending && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-16 rounded-xl" />
          ))}
        </div>
      )}

      {isError && <ErrorState message="Couldn't load your history." onRetry={() => refetch()} />}

      {!isPending && !isError && sessions.length === 0 && (
        <EmptyState
          icon={HistoryIcon}
          title="No sessions yet"
          description="Start a scenario from Practice to see it here."
          action={
            <Button nativeButton={false} render={<Link href="/practice" />} className="mt-1">
              Go to Practice
            </Button>
          }
        />
      )}

      {!isPending && !isError && sessions.length > 0 && (
        <>
          <ul className="space-y-2.5">
            {sessions.map((session) => (
              <HistoryRow key={session.id} session={session} />
            ))}
          </ul>
          {hasNextPage && (
            <div className="mt-4 flex justify-center">
              <Button
                type="button"
                variant="outline"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                Load more
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
