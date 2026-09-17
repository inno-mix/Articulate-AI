import { ScenarioDetailView } from "@/features/scenarios/components/scenario-detail-view";

export default async function ScenarioDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <ScenarioDetailView slug={slug} />;
}
