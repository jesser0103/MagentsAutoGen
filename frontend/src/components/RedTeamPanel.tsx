'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { RedTeamReport, AttackFinding } from '@/lib/types';
import { AlertTriangle, ShieldAlert, Swords, Terminal, CheckCircle2, ShieldCheck, Flame, Zap } from 'lucide-react';

interface RedTeamPanelProps {
  reports?: RedTeamReport[];
}

export function RedTeamPanel({ reports = [] }: RedTeamPanelProps) {
  const latestReport = reports.length > 0 ? reports[reports.length - 1] : null;

  if (!latestReport) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Swords className="w-10 h-10 text-muted-foreground/40 mb-3" />
        <h3 className="text-sm font-semibold text-foreground">No Red Team Assessment Available</h3>
        <p className="text-xs text-muted-foreground mt-1 max-w-md">
          The Security Red Team Agent runs after code generation to proactively simulate adversarial attack scenarios.
        </p>
      </div>
    );
  }

  const getRiskBadgeColor = (score: number) => {
    if (score >= 8.0) return 'bg-red-500/20 text-red-400 border-red-500/40';
    if (score >= 5.0) return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
    if (score >= 2.0) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40';
    return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
  };

  const getSeverityBadge = (sev: string) => {
    const s = sev.toLowerCase();
    if (s === 'critical') return <Badge className="bg-red-950/80 text-red-400 border-red-500/50 uppercase text-[10px]">CRITICAL</Badge>;
    if (s === 'high') return <Badge className="bg-orange-950/80 text-orange-400 border-orange-500/50 uppercase text-[10px]">HIGH</Badge>;
    if (s === 'medium') return <Badge className="bg-amber-950/80 text-amber-400 border-amber-500/50 uppercase text-[10px]">MEDIUM</Badge>;
    return <Badge className="bg-blue-950/80 text-blue-400 border-blue-500/50 uppercase text-[10px]">LOW</Badge>;
  };

  const getVectorLabel = (vector: string) => {
    return vector.replace(/_/g, ' ').toUpperCase();
  };

  return (
    <div className="space-y-4">
      {/* ── 1. Adversarial Risk Banner ── */}
      <Card className="border-red-500/30 bg-red-950/10">
        <CardContent className="p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-500/20 text-red-400">
                <Swords className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                  Security Red Team Adversarial Analysis
                </h3>
                <p className="text-xs text-muted-foreground">
                  Proactive offensive attack surface simulation & exploit verification
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Adversarial Risk Score:</span>
              <div className={`px-3 py-1 rounded-lg border font-mono text-sm font-bold ${getRiskBadgeColor(latestReport.risk_score)}`}>
                {latestReport.risk_score.toFixed(1)} / 10.0
              </div>
            </div>
          </div>

          {latestReport.assessment && (
            <p className="text-xs text-foreground/90 bg-black/40 p-3 rounded-lg border border-white/[0.05] leading-relaxed">
              {latestReport.assessment}
            </p>
          )}
        </CardContent>
      </Card>

      {/* ── 2. Identified Attack Findings Grid ── */}
      {latestReport.attack_findings.length > 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Flame className="h-3.5 w-3.5 text-red-400" />
              Identified Exploit Vectors ({latestReport.attack_findings.length})
            </h4>
          </div>

          <div className="space-y-3">
            {latestReport.attack_findings.map((finding: AttackFinding, idx: number) => (
              <Card key={idx} className="border-border/50 bg-card/60 overflow-hidden">
                <CardHeader className="pb-2 pt-3 px-4 bg-white/[0.01]">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getSeverityBadge(finding.severity)}
                      <Badge variant="outline" className="text-[10px] font-mono border-red-500/30 text-red-300">
                        {finding.rule_id}
                      </Badge>
                      <Badge variant="secondary" className="text-[10px] uppercase font-mono">
                        {getVectorLabel(finding.vector)}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-4 space-y-3">
                  <p className="text-xs font-medium text-foreground">
                    {finding.message}
                  </p>

                  {/* Step-by-step Exploit Scenario */}
                  {finding.exploit_scenario && (
                    <div className="space-y-1.5 rounded-lg border border-red-900/40 bg-black/60 p-3 font-mono text-xs">
                      <div className="flex items-center gap-1.5 text-red-400 text-[11px] font-bold">
                        <Terminal className="h-3.5 w-3.5" />
                        <span>Adversarial Exploit Scenario:</span>
                      </div>
                      <p className="text-red-200/90 leading-relaxed text-[11px]">
                        {finding.exploit_scenario}
                      </p>
                    </div>
                  )}

                  {/* Remediation */}
                  <div className="flex items-start gap-2 rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-2.5 text-xs text-emerald-300/90">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <div>
                      <strong className="text-emerald-200">Recommended Fix: </strong>
                      {finding.remediation}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ) : (
        <Card className="border-emerald-500/30 bg-emerald-950/10">
          <CardContent className="p-4 flex items-center gap-3">
            <ShieldCheck className="h-5 w-5 text-emerald-400 shrink-0" />
            <div className="text-xs text-emerald-200">
              <strong className="font-semibold text-foreground">Zero Exploitable Attack Vectors Identified!</strong>
              <p className="text-muted-foreground mt-0.5">
                The Security Red Team Agent simulated adversarial attacks (privilege escalation, exfiltration, perimeter leaks) and found no vulnerabilities.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
