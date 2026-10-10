'use client';

import dynamic from 'next/dynamic';
import { useState, useEffect, useMemo } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScanDashboard } from '@/components/ScanDashboard';
import { WorkflowRun, WorkflowEvent, FinOpsSummary } from '@/lib/types';
import { mergeWorkflowEvents } from '@/lib/events';
import { AlertTriangle, CheckCircle2, XCircle, Info, BookOpen, Shield, FileText, DollarSign, Activity, Swords } from 'lucide-react';

const CodeViewer = dynamic(
  () => import('@/components/CodeViewer').then((module) => module.CodeViewer),
  { ssr: false, loading: () => <p className="py-12 text-center text-sm text-muted-foreground">Loading code viewer…</p> },
);
const FinOpsCharts = dynamic(
  () => import('@/components/FinOpsCharts').then((module) => module.FinOpsCharts),
  { ssr: false, loading: () => <p className="py-12 text-center text-sm text-muted-foreground">Loading FinOps charts…</p> },
);
const RedTeamPanel = dynamic(
  () => import('@/components/RedTeamPanel').then((module) => module.RedTeamPanel),
  { ssr: false, loading: () => <p className="py-12 text-center text-sm text-muted-foreground">Loading Red Team analysis…</p> },
);

interface TabbedDashboardProps {
  run: WorkflowRun;
  events: WorkflowEvent[];
  finops?: FinOpsSummary | null;
  finopsLoading?: boolean;
  finopsError?: string | null;
}

export function TabbedDashboard({
  run,
  events,
  finops = null,
  finopsLoading = false,
  finopsError = null,
}: TabbedDashboardProps) {
  const [activeTab, setActiveTab] = useState('artifact');

  const artifact = run.artifacts[run.artifacts.length - 1];
  const previousArtifact = run.artifacts.length > 1 ? run.artifacts[run.artifacts.length - 2] : null;
  const review = run.reviews[run.reviews.length - 1];
  const sandbox = run.sandbox_results[run.sandbox_results.length - 1];
  const displayEvents = useMemo(
    () => mergeWorkflowEvents(run.events, events),
    [events, run.events],
  );



  const eventIcon = (type: string) => {
    const map: Record<string, React.ReactNode> = {
      input_screened: <Shield className="w-3.5 h-3.5 text-blue-400" />,
      context_bounded: <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />,
      rules_retrieved: <BookOpen className="w-3.5 h-3.5 text-purple-400" />,
      artifact_generated: <FileText className="w-3.5 h-3.5 text-emerald-400" />,
      scan_completed: <Shield className="w-3.5 h-3.5 text-cyan-400" />,
      review_completed: <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />,
      sandbox_completed: <CheckCircle2 className="w-3.5 h-3.5 text-teal-400" />,
      blocked: <XCircle className="w-3.5 h-3.5 text-red-400" />,
      completed: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />,
    };
    return map[type] || <Info className="w-3.5 h-3.5 text-slate-400" />;
  };

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="glass-card overflow-hidden p-2">
      <TabsList className="terminal-scroll flex h-auto w-full justify-start gap-1 overflow-x-auto rounded-xl border border-white/[0.05] bg-black/10 p-1.5">
        <TabsTrigger value="artifact" className="h-9 rounded-lg px-3 text-[10px] uppercase tracking-wider"><FileText className="mr-1.5 h-3.5 w-3.5" /> Artifact</TabsTrigger>
        <TabsTrigger value="scans" className="h-9 rounded-lg px-3 text-[10px] uppercase tracking-wider"><Shield className="mr-1.5 h-3.5 w-3.5" /> Scans</TabsTrigger>
        <TabsTrigger value="redteam" className="h-9 rounded-lg px-3 text-[10px] uppercase tracking-wider text-red-400 font-semibold"><Swords className="mr-1.5 h-3.5 w-3.5 text-red-400" /> Red Team</TabsTrigger>
        <TabsTrigger value="review" className="h-9 rounded-lg px-3 text-[10px] uppercase tracking-wider"><CheckCircle2 className="mr-1.5 h-3.5 w-3.5" /> Review</TabsTrigger>
        <TabsTrigger value="finops" className="h-9 rounded-lg px-3 text-[10px] uppercase tracking-wider"><DollarSign className="mr-1.5 h-3.5 w-3.5" /> FinOps</TabsTrigger>
        <TabsTrigger value="rag" className="h-9 rounded-lg px-3 text-[10px] uppercase tracking-wider"><BookOpen className="mr-1.5 h-3.5 w-3.5" /> RAG</TabsTrigger>
        <TabsTrigger value="events" className="h-9 rounded-lg px-3 text-[10px] uppercase tracking-wider"><Activity className="mr-1.5 h-3.5 w-3.5" /> Events</TabsTrigger>
      </TabsList>

      {/* Tab 1: Generated Artifact */}
      <TabsContent value="artifact" className="mt-2 p-3 sm:p-4">
        {activeTab === 'artifact' && artifact ? (
          <CodeViewer
            artifact={artifact}
            previousArtifact={previousArtifact}
            sandboxSuccess={sandbox?.succeeded ?? null}
          />
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <FileText className="w-8 h-8 text-muted-foreground mb-3 opacity-40" />
            <p className="text-sm text-muted-foreground">No artifact generated yet.</p>
            <p className="text-xs text-muted-foreground/60 mt-1">
              An artifact will appear once the Coder agent generates code.
            </p>
          </div>
        )}
      </TabsContent>

      {/* Tab 2: Security Scans */}
      <TabsContent value="scans" className="mt-2 p-3 sm:p-4">
        <ScanDashboard scans={run.scans} />
      </TabsContent>

      {/* Tab 3: Security Red Team Analysis */}
      <TabsContent value="redteam" className="mt-2 p-3 sm:p-4">
        {activeTab === 'redteam' && <RedTeamPanel reports={run.red_team_reports} />}
      </TabsContent>

      {/* Tab 3: Reviewer Assessment */}
      <TabsContent value="review" className="mt-2 p-3 sm:p-4">
        {review ? (
          <Card className="border-border/50 bg-card/60">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold">Reviewer Assessment</CardTitle>
                <Badge variant={review.verdict === 'approve' ? 'completed' : 'awaiting'}>
                  {review.verdict}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-foreground">{review.assessment}</p>
              {review.findings.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">Findings:</p>
                  {review.findings.map((f, i) => (
                    <div key={i} className="text-xs flex items-start gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
                      <span><strong>{f.severity.toUpperCase()}</strong> {f.rule_id}: {f.message}</span>
                    </div>
                  ))}
                </div>
              )}
              {review.required_changes.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">Required Changes:</p>
                  <ul className="list-disc list-inside text-xs text-foreground space-y-1">
                    {review.required_changes.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        ) : (
          <p className="text-sm text-muted-foreground">No review completed yet.</p>
        )}
      </TabsContent>

      {/* Tab 4: FinOps Cost Breakdown */}
      <TabsContent value="finops" className="mt-2 p-3 sm:p-4">
        {activeTab === 'finops' && (
          <FinOpsCharts
            finops={finops}
            finopsReports={run.finops_reports}
            loading={finopsLoading}
            error={finopsError}
          />
        )}
      </TabsContent>

      {/* Tab 5: RAG Policy Memory */}
      <TabsContent value="rag" className="mt-2 p-3 sm:p-4">
        {run.retrieval_evidence.length === 0 ? (
          <p className="text-sm text-muted-foreground">No policy rules retrieved yet.</p>
        ) : (
          <div className="space-y-3">
            {run.retrieval_evidence.map((ev, idx) => (
              <Card key={idx} className="border-border/50 bg-card/60">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-xs font-mono">{ev.rule_id}</CardTitle>
                    <Badge variant="outline" className="text-[10px]">Score: {ev.score.toFixed(2)}</Badge>
                  </div>
                  <CardDescription className="text-[10px]">
                    Source: {ev.source} | Hash: {ev.source_hash.slice(0, 12)}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-foreground whitespace-pre-wrap">
                    {run.retrieved_rules[idx] || '—'}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </TabsContent>

      {/* Tab 6: Event Audit Log */}
      <TabsContent value="events" className="mt-2 p-3 sm:p-4">
        <Card className="border-border/50 bg-card/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold">Workflow Event History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2">
              {displayEvents.length === 0 ? (
                <p className="text-xs text-muted-foreground">No events yet.</p>
              ) : (
                displayEvents.map((evt, i) => (
                    <div key={i} className="flex items-start gap-2.5 text-xs py-1.5 border-b border-border/20 last:border-0">
                      <span className="mt-0.5 shrink-0">{eventIcon(evt.event_type)}</span>
                      <div className="flex-1 min-w-0">
                        <span className="font-mono text-muted-foreground mr-2">
                          {new Date(evt.created_at).toLocaleTimeString()}
                        </span>
                        <span className="font-semibold text-foreground">{evt.agent}</span>
                        <span className="text-muted-foreground mx-1">—</span>
                        <span className="text-foreground/80">{evt.message}</span>
                      </div>
                    </div>
                  ))
              )}
            </div>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
}
