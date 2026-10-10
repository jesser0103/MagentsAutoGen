'use client';

import { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScanReport, SecurityFinding } from '@/lib/types';
import { cn } from '@/lib/utils';
import {
  Shield,
  Filter,
  AlertTriangle,
  XCircle,
  Info,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface ScanDashboardProps {
  scans: ScanReport[];
}

type SeverityFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';

const SEVERITY_ORDER: SeverityFilter[] = ['critical', 'high', 'medium', 'low'];
const SEVERITY_META: Record<string, { color: string; icon: React.ReactNode; bg: string; border: string }> = {
  critical: {
    color: 'text-red-300',
    icon: <XCircle className="w-3.5 h-3.5 text-red-400" />,
    bg: 'bg-red-950/30',
    border: 'border-red-500/40',
  },
  high: {
    color: 'text-amber-300',
    icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />,
    bg: 'bg-amber-950/30',
    border: 'border-amber-500/40',
  },
  medium: {
    color: 'text-blue-300',
    icon: <Info className="w-3.5 h-3.5 text-blue-400" />,
    bg: 'bg-blue-950/30',
    border: 'border-blue-500/40',
  },
  low: {
    color: 'text-slate-300',
    icon: <Info className="w-3.5 h-3.5 text-slate-400" />,
    bg: 'bg-slate-900/30',
    border: 'border-slate-500/30',
  },
};

function FindingCard({ finding }: { finding: SecurityFinding }) {
  const [expanded, setExpanded] = useState(false);
  const meta = SEVERITY_META[finding.severity] || SEVERITY_META.low;

  return (
    <div
      className={cn(
        'rounded-lg border p-3 transition-all duration-200',
        meta.bg,
        meta.border
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge
            variant="outline"
            className={cn(
              'text-[10px] uppercase font-bold border-none',
              finding.severity === 'critical'
                ? 'bg-red-500/20 text-red-300'
                : finding.severity === 'high'
                ? 'bg-amber-500/20 text-amber-300'
                : finding.severity === 'medium'
                ? 'bg-blue-500/20 text-blue-300'
                : 'bg-slate-500/20 text-slate-300'
            )}
          >
            {meta.icon}
            <span className="ml-1">{finding.severity}</span>
          </Badge>
          <span className="text-[10px] font-mono text-muted-foreground">
            {finding.tool}/{finding.rule_id}
          </span>
        </div>
        <Button
          size="icon"
          variant="ghost"
          className="h-5 w-5 shrink-0"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? (
            <ChevronUp className="w-3 h-3 text-slate-400" />
          ) : (
            <ChevronDown className="w-3 h-3 text-slate-400" />
          )}
        </Button>
      </div>

      <p className="text-xs text-foreground mt-2">{finding.message}</p>

      {finding.evidence && (
        <pre className="mt-2 text-[10px] font-mono bg-[#0a0c14] p-2 rounded text-slate-300 overflow-x-auto border border-white/5">
          {finding.evidence}
        </pre>
      )}

      {expanded && (
        <div className="mt-3 pt-3 border-t border-white/10 animate-fade-in">
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1 font-medium">
            Remediation
          </p>
          <p className="text-xs text-slate-200 leading-relaxed">{finding.remediation}</p>
          {finding.location && (
            <p className="text-[10px] text-muted-foreground mt-2 font-mono">
              Location: {finding.location}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function ScanDashboard({ scans }: ScanDashboardProps) {
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [toolFilter, setToolFilter] = useState<string>('all');

  const allFindings = useMemo(() => {
    const findings: (SecurityFinding & { tool: string })[] = [];
    scans.forEach((scan) => {
      scan.findings.forEach((f) => findings.push({ ...f, tool: scan.tool }));
    });
    return findings;
  }, [scans]);

  const tools = useMemo(() => {
    const set = new Set(scans.map((s) => s.tool));
    return Array.from(set);
  }, [scans]);

  const filteredFindings = useMemo(() => {
    let result = allFindings;
    if (severityFilter !== 'all') {
      result = result.filter((f) => f.severity === severityFilter);
    }
    if (toolFilter !== 'all') {
      result = result.filter((f) => f.tool === toolFilter);
    }
    return result;
  }, [allFindings, severityFilter, toolFilter]);

  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
    allFindings.forEach((f) => {
      counts[f.severity] = (counts[f.severity] || 0) + 1;
    });
    return counts;
  }, [allFindings]);

  if (scans.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Shield className="w-8 h-8 text-muted-foreground mb-3 opacity-40" />
        <p className="text-sm text-muted-foreground">No scans completed yet.</p>
        <p className="text-xs text-muted-foreground/60 mt-1">
          Scans will appear once the Coder and Reviewer agents finish their work.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Severity summary chips */}
      <div className="flex flex-wrap items-center gap-2">
        {SEVERITY_ORDER.map((sev) => (
          <button
            key={sev}
            onClick={() => setSeverityFilter((prev) => (prev === sev ? 'all' : sev))}
            className={cn(
              'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[10px] uppercase tracking-wider font-medium border transition-all',
              severityFilter === sev
                ? SEVERITY_META[sev].bg + ' ' + SEVERITY_META[sev].border + ' ' + SEVERITY_META[sev].color
                : 'bg-transparent border-border/30 text-muted-foreground hover:bg-white/5'
            )}
          >
            {SEVERITY_META[sev].icon}
            {sev} ({severityCounts[sev] || 0})
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1.5">
          <Filter className="w-3 h-3 text-muted-foreground" />
          <select
            value={toolFilter}
            onChange={(e) => setToolFilter(e.target.value)}
            className="bg-background/50 border border-border/40 rounded-md text-[10px] px-2 py-1 text-muted-foreground outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="all">All Tools</option>
            {tools.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Scan tool cards */}
      {scans.map((scan, idx) => {
        const scanFindings = filteredFindings.filter((f) => f.tool === scan.tool);
        const hasMatch = scanFindings.length > 0 || (severityFilter === 'all' && toolFilter === 'all');
        if (!hasMatch && toolFilter !== 'all' && toolFilter !== scan.tool) return null;

        return (
          <Card key={`${scan.tool}-${idx}`} className="border-border/50 bg-card/60">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-muted-foreground" />
                  <CardTitle className="text-sm font-semibold">{scan.tool}</CardTitle>
                </div>
                <Badge
                  variant={scan.succeeded ? 'completed' : 'blocked'}
                  className="text-[10px]"
                >
                  {scan.succeeded ? 'Passed' : 'Blocked'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {scan.error && <p className="text-xs text-red-300 mb-2">{scan.error}</p>}
              {scan.findings.length === 0 ? (
                <p className="text-xs text-emerald-300">No findings reported by this scanner.</p>
              ) : severityFilter !== 'all' || toolFilter !== 'all' ? (
                scanFindings.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No findings match the current filters.
                  </p>
                ) : (
                  scanFindings.map((f, i) => <FindingCard key={i} finding={f} />)
                )
              ) : (
                scan.findings.map((f, i) => <FindingCard key={i} finding={f} />)
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
