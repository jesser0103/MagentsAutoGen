import { createHighlighter } from 'shiki';
import type { Highlighter } from 'shiki';

let highlighterPromise: Promise<Highlighter> | null = null;

const SUPPORTED_LANGS = [
  'python',
  'hcl',
  'yaml',
  'json',
  'javascript',
  'typescript',
  'tsx',
  'bash',
  'dockerfile',
  'markdown',
  'go',
  'rust',
] as const;

async function getHighlighter(): Promise<Highlighter> {
  if (highlighterPromise) return highlighterPromise;
  highlighterPromise = createHighlighter({
    themes: ['dark-plus'],
    langs: [...SUPPORTED_LANGS],
  });
  return highlighterPromise;
}

export async function highlightCode(code: string, lang: string): Promise<string> {
  try {
    const highlighter = await getHighlighter();
    const validLang = SUPPORTED_LANGS.includes(lang as any) ? lang : 'text';
    return highlighter.codeToHtml(code, {
      lang: validLang,
      theme: 'dark-plus',
    });
  } catch {
    // Fallback to escaped plain text in a pre block
    return `<pre style="color:#e6edf3;background:#0d1117;padding:16px;overflow:auto"><code>${escapeHtml(code)}</code></pre>`;
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export const languages = [...SUPPORTED_LANGS, 'text'];
