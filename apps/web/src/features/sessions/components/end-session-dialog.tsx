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

export function EndSessionDialog({
  userTurns,
  onConfirm,
  disabled,
}: {
  userTurns: number;
  onConfirm: () => void;
  disabled: boolean;
}) {
  const short = userTurns < 2;
  return (
    <Dialog>
      <DialogTrigger render={<Button type="button" variant="outline" disabled={disabled} />}>
        End session
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>End this practice session?</DialogTitle>
          <DialogDescription>
            {short
              ? "No feedback report will be created for very short sessions. End anyway?"
              : "You can review the conversation afterwards from your history."}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose render={<Button type="button" variant="outline" />}>Cancel</DialogClose>
          <DialogClose render={<Button type="button" onClick={onConfirm} />}>
            End session
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
