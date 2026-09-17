import { SessionView } from "@/features/sessions/components/session-view";

export default async function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SessionView sessionId={id} />;
}
