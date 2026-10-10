'use client';

import { useEffect, useState, useCallback } from 'react';
import { highlightCode, languages } from '@/lib/shiki';
import { diffLines } from 'diff';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Copy, Download, FileCode, Eye, GitCompare, FileArchive, Check } from 'lucide-react';
import { toast } from 'sonner';
import JSZip from 'jszip';
import { saveAs } from 'file-saver';
import { cn } from '@/lib/utils';
import type { Artifact } from '@/lib/types';

interface CodeViewerProps {
  artifact: Artifact;
  previousArtifact?: Artifact | null;
  sandboxSuccess?: boolean | null;
}

type ViewMode = 'highlighted' | 'raw' | 'diff';

function detectLanguage(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    py: 'python',
    tf: 'hcl',
    yml: 'yaml',
    yaml: 'yaml',
    json: 'json',
    js: 'javascript',
    ts: 'typescript',
    tsx: 'tsx',
    jsx: 'jsx',
    md: 'markdown',
    sh: 'bash',
    dockerfile: 'dockerfile',
    hcl: 'hcl',
    go: 'go',
    rs: 'rust',
  };
  return map[ext || ''] || 'text';
}

export function CodeViewer({ artifact, previousArtifact, sandboxSuccess }: CodeViewerProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('highlighted');
  const [highlightedHtml, setHighlightedHtml] = useState<string>('');
  const [diffHtml, setDiffHtml] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const language = detectLanguage(artifact.filename);

  useEffect(() => {
    if (viewMode === 'highlighted') {
      setLoading(true);
      highlightCode(artifact.content, language)
        .then((html) => {
          setHighlightedHtml(html);
          setLoading(false);
        })
        .catch(() => setLoading(false));
    }
  }, [artifact.content, language, viewMode]);

  useEffect(() => {
    if (viewMode === 'diff' && previousArtifact) {
      const changes = diffLines(previousArtifact.content, artifact.content);
      const html = changes
        .map((part) => {
          const cls = part.added ? 'diff-add' : part.removed ? 'diff-del' : 'diff-neutral';
          const prefix = part.added ? '+' : part.removed ? '-' : ' ';
          const lines = part.value.split('\n');
          // Remove trailing empty line artifact from split
          if (lines[lines.length - 1] === '') lines.pop();
          return lines
            .map((line) => `<span class="${cls}">${prefix}${escapeHtml(line)}</span>`)
            .join('\n');
        })
        .join('\n');
      setDiffHtml(html);
    }
  }, [viewMode, artifact.content, previousArtifact]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(artifact.content);
      setCopied(true);
      toast.success('Copied to clipboard', { description: artifact.filename });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Failed to copy');
    }
  }, [artifact]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([artifact.content], { type: 'text/plain' });
    saveAs(blob, artifact.filename);
    toast.success('Download started', { description: artifact.filename });
  }, [artifact]);

  const handleDownloadZip = useCallback(async () => {
    const zip = new JSZip();
    zip.file(artifact.filename, artifact.content);
    const blob = await zip.generateAsync({ type: 'blob' });
    saveAs(blob, `${artifact.filename.replace(/\.[^/.]+$/, '')}.zip`);
    toast.success('ZIP archive downloaded');
  }, [artifact]);

  const canDiff = !!previousArtifact;

  return (
    <Card className="border-border/50 bg-card/60 overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between pb-2 gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-muted-foreground" />
          <CardTitle className="text-sm font-semibold">{artifact.filename}</CardTitle>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono uppercase">
            {language}
          </span>
          {sandboxSuccess != null && (
            <span
              className={cn(
                'text-[10px] px-1.5 py-0.5 rounded-full border font-medium',
                sandboxSuccess
                  ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/30'
                  : 'bg-red-950/40 text-red-300 border-red-500/30'
              )}
            >
              {sandboxSuccess ? 'Docker Pass' : 'Docker Fail'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <div className="flex bg-muted/60 rounded-md p-0.5 mr-2">
            <Button
              size="sm"
              variant={viewMode === 'highlighted' ? 'secondary' : 'ghost'}
              onClick={() => setViewMode('highlighted')}
              className="h-7 text-xs px-2"
            >
              <FileCode className="w-3 h-3 mr-1" /> Highlighted
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'raw' ? 'secondary' : 'ghost'}
              onClick={() => setViewMode('raw')}
              className="h-7 text-xs px-2"
            >
              <Eye className="w-3 h-3 mr-1" /> Raw
            </Button>
            {canDiff && (
              <Button
                size="sm"
                variant={viewMode === 'diff' ? 'secondary' : 'ghost'}
                onClick={() => setViewMode('diff')}
                className="h-7 text-xs px-2"
              >
                <GitCompare className="w-3 h-3 mr-1" /> Diff
              </Button>
            )}
          </div>
          <Button size="sm" variant="outline" onClick={handleCopy} className="h-7 text-xs px-2">
            {copied ? <Check className="w-3 h-3 mr-1" /> : <Copy className="w-3 h-3 mr-1" />}
            {copied ? 'Copied' : 'Copy'}
          </Button>
          <Button size="sm" variant="outline" onClick={handleDownload} className="h-7 text-xs px-2">
            <Download className="w-3 h-3 mr-1" /> Download
          </Button>
          <Button size="sm" variant="outline" onClick={handleDownloadZip} className="h-7 text-xs px-2">
            <FileArchive className="w-3 h-3 mr-1" /> ZIP
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {viewMode === 'highlighted' && (
          <div className="relative">
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
                <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
            )}
            <div
              className="overflow-x-auto p-4 text-[13px] leading-relaxed"
              style={{
                background: '#0d1117',
                borderTop: '1px solid rgba(255,255,255,0.06)',
              }}
              dangerouslySetInnerHTML={{ __html: highlightedHtml }}
            />
          </div>
        )}
        {viewMode === 'raw' && (
          <pre
            className="p-4 text-xs font-mono text-slate-200 leading-relaxed overflow-x-auto"
            style={{ background: '#0d1117', borderTop: '1px solid rgba(255,255,255,0.06)' }}
          >
            {artifact.content}
          </pre>
        )}
        {viewMode === 'diff' && (
          <pre
            className="p-4 text-xs font-mono leading-relaxed overflow-x-auto diff-viewer"
            style={{ background: '#0d1117', borderTop: '1px solid rgba(255,255,255,0.06)' }}
            dangerouslySetInnerHTML={{ __html: diffHtml }}
          />
        )}
      </CardContent>
    </Card>
  );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
