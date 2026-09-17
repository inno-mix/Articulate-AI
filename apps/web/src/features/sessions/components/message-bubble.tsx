import type { MessageOut } from "@/lib/api/events";
import { cn } from "@/lib/utils";

export function MessageBubble({ message }: { message: MessageOut }) {
  const isUser = message.role === "user";
  const isSafety = message.source === "system";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[34rem] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground"
            : isSafety
              ? "bg-accent text-accent-foreground"
              : "bg-card ring-1 ring-foreground/10",
        )}
      >
        {message.content}
      </div>
    </div>
  );
}
