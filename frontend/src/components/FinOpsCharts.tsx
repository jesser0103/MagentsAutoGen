'use client';

import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { FinOpsReport, FinOpsSummary } from '@/lib/types';
import { cn } from '@/lib/utils';
import { AlertCircle, CheckCircle2, Cloud, DollarSign, Info, Loader2, Sparkles, TrendingDown, Cpu } from 'lucide-react';

interface FinOpsChartsProps {
  finops: FinOpsSummary | null;
  finopsReports?: FinOpsReport[];
  loading?: boolean;
  error?: string | null;
}

const COLORS = ['#3b82f6', '#8b5cf6', '#22c55e', '#f59e0b', '#ef4444', '#06b6d4'];

export function FinOpsCharts({
  finops,
  finopsReports = [],
  loading = false,
  error = null,
}: FinOpsChartsProps) {
  const latestReport = finopsReports.length > 0 ? finopsReports[finopsReports.length - 1] : null;

  const agentData = useMemo(() => {
    if (!finops) return [];
    return Object.entries(finops.per_agent).map(([name, cost]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      cost: Number(cost),
    }));
  }, [finops]);

  const stageData = useMemo(() => {
    if (!finops) return [];
    return Object.entries(finops.per_stage).map(([name, cost]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      cost: Number(cost),
    }));
  }, [finops]);

  const tokenData = useMemo(() => {
    if (!finops) return [];
    return [
      { name: 'Prompt', value: finops.total_prompt_tokens },
      { name: 'Completion', value: finops.total_completion_tokens },
    ];
  }, [finops]);

  const totalTokens = (finops?.total_prompt_tokens || 0) + (finops?.total_completion_tokens || 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading FinOps analytics…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-950/20 px-3 py-3 text-sm text-red-200">
        <AlertCircle className="h-4 w-4 shrink-0" /> {error}
      </div>
    );
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-[#0d1117] border border-border/50 rounded-md px-3 py-2 text-xs shadow-xl">
          <p className="font-medium text-foreground mb-1">{label}</p>
          <p className="text-muted-foreground">
            Cost: <span className="font-mono text-emerald-300">${payload[0].value.toFixed(5)}</span>
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* ── 1. Azure Cloud OpEx Projection (from FinOps Agent) ── */}
      {latestReport ? (
        <div className="space-y-4 rounded-xl border border-emerald-500/30 bg-emerald-950/10 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400">
                <Cloud className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground">
                  Azure Cloud Infrastructure OpEx Projection
                </h3>
                <p className="text-xs text-muted-foreground">
                  AI-estimated monthly runtime costs for generated cloud resources
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Estimated Monthly OpEx:</span>
              <Badge className="bg-emerald-600/30 text-emerald-300 hover:bg-emerald-600/40 text-sm font-mono px-3 py-1">
                ${latestReport.total_monthly_usd.toFixed(2)} {latestReport.currency} / mo
              </Badge>
            </div>
          </div>

          {latestReport.raw_assessment && (
            <p className="text-xs text-foreground/90 bg-black/20 p-2.5 rounded-lg border border-white/[0.05]">
              {latestReport.raw_assessment}
            </p>
          )}

          {latestReport.infracost_breakdown && (
            <div className="space-y-2 rounded-lg border border-sky-500/25 bg-sky-950/10 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-sky-200">
                    Infracost Terraform estimate
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Calculated from the generated Terraform after sandbox validation
                  </p>
                </div>
                <Badge className="bg-sky-600/25 font-mono text-sky-200 hover:bg-sky-600/35">
                  ${latestReport.infracost_breakdown.total_monthly_usd.toFixed(2)} {latestReport.infracost_breakdown.currency} / mo
                </Badge>
              </div>
              {latestReport.infracost_breakdown.error ? (
                <p className="text-xs text-amber-200">
                  {latestReport.infracost_breakdown.error}
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[480px] text-left text-xs">
                    <thead className="border-b border-sky-500/20 text-[10px] uppercase tracking-wide text-muted-foreground">
                      <tr>
                        <th className="px-2 py-2 font-medium">Resource</th>
                        <th className="px-2 py-2 font-medium">Type</th>
                        <th className="px-2 py-2 text-right font-medium">Monthly cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {latestReport.infracost_breakdown.resources.map((resource) => (
                        <tr key={`${resource.resource_type}-${resource.name}`} className="border-b border-border/20 last:border-0">
                          <td className="px-2 py-2 font-mono text-foreground">{resource.name}</td>
                          <td className="px-2 py-2 text-muted-foreground">{resource.resource_type}</td>
                          <td className="px-2 py-2 text-right font-mono text-emerald-300">
                            ${resource.monthly_cost_usd.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Cost drivers breakdown */}
          {latestReport.cost_drivers.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Resource Cost Breakdown ({latestReport.cost_drivers.length} detected)
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
                {latestReport.cost_drivers.map((driver, idx) => (
                  <Card key={idx} className="border-border/40 bg-card/70">
                    <CardContent className="p-3 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-foreground flex items-center gap-1.5">
                          <Cpu className="h-3.5 w-3.5 text-blue-400" />
                          {driver.resource_type}
                        </span>
                        <span className="font-mono text-xs font-bold text-emerald-400">
                          ${driver.estimated_monthly_usd.toFixed(2)}/mo
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                        <span>SKU: <strong className="text-foreground/80">{driver.sku}</strong></span>
                      </div>
                      {driver.notes && (
                        <p className="text-[10px] text-muted-foreground/80 italic border-t border-border/20 pt-1">
                          {driver.notes}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Right-sizing recommendations */}
          {latestReport.recommendations.length > 0 && (
            <div className="space-y-1.5 rounded-lg border border-amber-500/20 bg-amber-950/15 p-3">
              <div className="flex items-center gap-1.5 text-xs font-medium text-amber-300">
                <Sparkles className="h-3.5 w-3.5" />
                <span>FinOps Right-Sizing & Sizing Recommendations:</span>
              </div>
              <ul className="space-y-1 pl-4 text-xs text-amber-100/90 list-disc">
                {latestReport.recommendations.map((rec, i) => (
                  <li key={i}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <Card className="border-border/50 bg-card/60">
          <CardContent className="p-4 flex items-center gap-3">
            <Cloud className="h-5 w-5 text-muted-foreground/50 shrink-0" />
            <div className="text-xs text-muted-foreground">
              <strong className="text-foreground">Azure Cloud OpEx Projection:</strong> Run code generation to see the FinOps Agent project resource monthly costs and sizing recommendations.
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── 2. LLM Multi-Agent Invocation Cost & Token Metrics ── */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-blue-400" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            LLM Multi-Agent Invocation & Token Usage
          </h4>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[
            ['AI Pipeline Execution Cost', `$${(finops?.total_usd ?? 0).toFixed(6)}`],
            ['Prompt Tokens', (finops?.total_prompt_tokens ?? 0).toLocaleString()],
            ['Completion Tokens', (finops?.total_completion_tokens ?? 0).toLocaleString()],
            ['Total Tokens Consumed', totalTokens.toLocaleString()],
          ].map(([label, value]) => (
            <Card key={label} className="border-border/50 bg-card/60">
              <CardContent className="p-3">
                <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
                <p className="mt-1 font-mono text-sm font-semibold text-foreground">{value}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="border-border/50 bg-card/60">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Cost by Agent (USD)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-44">
                {agentData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={agentData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                      <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <YAxis
                        tick={{ fontSize: 10, fill: '#94a3b8' }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v: number) => `$${v.toFixed(3)}`}
                      />
                      <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                      <Bar dataKey="cost" radius={[4, 4, 0, 0]}>
                        {agentData.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                    No agent cost data yet
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/50 bg-card/60">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Cost by Stage (USD)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-44">
                {stageData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stageData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                      <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                      <YAxis
                        tick={{ fontSize: 10, fill: '#94a3b8' }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v: number) => `$${v.toFixed(3)}`}
                      />
                      <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                      <Bar dataKey="cost" radius={[4, 4, 0, 0]}>
                        {stageData.map((_, i) => (
                          <Cell key={i} fill={COLORS[(i + 2) % COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                    No stage data yet
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="border-border/50 bg-card/60">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Token Distribution
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-44">
                {totalTokens > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={tokenData}
                        cx="50%"
                        cy="50%"
                        innerRadius={45}
                        outerRadius={65}
                        paddingAngle={4}
                        dataKey="value"
                        stroke="none"
                      >
                        {tokenData.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Legend
                        verticalAlign="bottom"
                        height={24}
                        iconType="circle"
                        iconSize={6}
                        formatter={(value: string) => (
                          <span className="text-[10px] text-slate-300">{value}</span>
                        )}
                      />
                      <Tooltip
                        content={({ active, payload }: any) => {
                          if (active && payload && payload.length) {
                            return (
                              <div className="bg-[#0d1117] border border-border/50 rounded-md px-3 py-2 text-xs shadow-xl">
                                <p className="font-medium text-foreground">{payload[0].name}</p>
                                <p className="font-mono text-slate-300">
                                  {payload[0].value.toLocaleString()} tokens
                                </p>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                    No token data yet
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/50 bg-card/60">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Agent Operation Breakdown
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {finops && Object.keys(finops.per_operation || {}).length > 0 ? (
                  Object.entries(finops.per_operation).map(([op, cost]) => (
                    <div key={op} className="flex items-center justify-between text-xs py-1 border-b border-border/20 last:border-0">
                      <span className="text-muted-foreground capitalize">{op}</span>
                      <span className="font-mono text-emerald-300">${(cost as number).toFixed(5)}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground">No operation data recorded.</p>
                )}
                <div className="flex items-center justify-between text-xs pt-2 border-t border-border/30">
                  <span className="font-medium text-foreground">Total LLM Cost</span>
                  <span className="font-mono text-emerald-300 font-bold">
                    ${finops?.total_usd.toFixed(4) || '0.0000'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {finops?.disclaimer && (
        <div className="flex items-start gap-2 rounded-lg border border-blue-500/20 bg-blue-950/20 px-3 py-2 text-xs text-blue-100/80">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{finops.disclaimer}</span>
        </div>
      )}
    </div>
  );
}
