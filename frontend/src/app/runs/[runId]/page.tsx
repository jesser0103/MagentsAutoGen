import { RunDashboard } from '@/components/RunDashboard';

interface RunPageProps {
  params: { runId: string };
}

export default function RunPage({ params }: RunPageProps) {
  return <RunDashboard runId={decodeURIComponent(params.runId)} />;
}
