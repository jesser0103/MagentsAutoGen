'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  BUILT_IN_TEMPLATES,
  deleteTemplate,
  listTemplates,
  saveTemplate,
  type MissionTemplate,
} from '@/lib/templates';
import {
  BookOpen,
  ChevronRight,
  Cloud,
  HardDrive,
  Network,
  Plus,
  Shield,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';

const CATEGORY_META: Record<
  MissionTemplate['category'],
  { label: string; icon: React.ElementType; color: string }
> = {
  compute:    { label: 'Compute',    icon: Cloud,      color: 'text-cyan-300 border-cyan-300/20 bg-cyan-300/[0.06]' },
  networking: { label: 'Networking', icon: Network,    color: 'text-violet-300 border-violet-300/20 bg-violet-300/[0.06]' },
  storage:    { label: 'Storage',    icon: HardDrive,  color: 'text-emerald-300 border-emerald-300/20 bg-emerald-300/[0.06]' },
  security:   { label: 'Security',   icon: Shield,     color: 'text-amber-300 border-amber-300/20 bg-amber-300/[0.06]' },
  custom:     { label: 'Custom',     icon: Sparkles,   color: 'text-slate-300 border-slate-300/20 bg-slate-300/[0.06]' },
};

interface TemplatePanelProps {
  onSelect: (request: string) => void;
  onClose: () => void;
  currentRequest?: string;
}

export function TemplatePanel({ onSelect, onClose, currentRequest }: TemplatePanelProps) {
  const [templates, setTemplates] = useState<MissionTemplate[]>(listTemplates);
  const [filter, setFilter] = useState<MissionTemplate['category'] | 'all'>('all');
  const [savingName, setSavingName] = useState('');
  const [showSaveForm, setShowSaveForm] = useState(false);

  const visible = filter === 'all' ? templates : templates.filter((t) => t.category === filter);
  const categories: readonly (MissionTemplate['category'] | 'all')[] = [
    'all',
    ...(Object.keys(CATEGORY_META) as MissionTemplate['category'][]),
  ];

  const handleSave = () => {
    if (!currentRequest?.trim() || !savingName.trim()) return;
    saveTemplate({
      name: savingName.trim(),
      description: 'Custom template',
      request: currentRequest,
      category: 'custom',
    });
    setTemplates(listTemplates());
    setSavingName('');
    setShowSaveForm(false);
  };

  const handleDelete = (id: string) => {
    deleteTemplate(id);
    setTemplates(listTemplates());
  };

  return (
    <div className="animate-fade-in flex h-full flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-[#07091a]/95 shadow-[0_0_80px_rgba(0,0,0,0.6)] backdrop-blur-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
        <div className="flex items-center gap-2.5">
          <BookOpen className="h-4 w-4 text-cyan-300" />
          <h2 className="text-sm font-semibold text-white">Mission Templates</h2>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-400">
            {templates.length}
          </span>
        </div>
        <button
          onClick={onClose}
          className="grid h-7 w-7 place-items-center rounded-lg border border-white/10 text-slate-500 hover:border-white/20 hover:text-slate-300 transition-all"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Category filter pills */}
      <div className="flex gap-1.5 overflow-x-auto border-b border-white/[0.06] px-5 py-3 scrollbar-hide">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilter(cat)}
            className={cn(
              'shrink-0 rounded-full border px-3 py-1 text-[10px] font-semibold uppercase tracking-widest transition-all',
              filter === cat
                ? 'border-cyan-300/30 bg-cyan-300/10 text-cyan-200'
                : 'border-white/[0.07] bg-white/[0.02] text-slate-500 hover:border-white/[0.13] hover:text-slate-300',
            )}
          >
            {cat === 'all' ? 'All' : CATEGORY_META[cat as MissionTemplate['category']].label}
          </button>
        ))}
      </div>

      {/* Template list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {visible.length === 0 && (
          <p className="py-8 text-center text-xs text-slate-600">No templates in this category.</p>
        )}
        {visible.map((tpl) => {
          const meta = CATEGORY_META[tpl.category];
          const Icon = meta.icon;
          return (
            <div
              key={tpl.id}
              className="group relative flex items-start gap-3 rounded-xl border border-white/[0.06] bg-white/[0.025] p-4 hover:border-white/[0.12] hover:bg-white/[0.04] transition-all cursor-pointer"
              onClick={() => { onSelect(tpl.request); onClose(); }}
            >
              <div className={cn('mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border', meta.color)}>
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-white">{tpl.name}</p>
                  {tpl.builtIn && (
                    <span className="rounded-full border border-white/10 bg-white/[0.04] px-1.5 py-px text-[9px] uppercase tracking-widest text-slate-500">
                      Built-in
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-slate-500 leading-4">{tpl.description}</p>
                <p className="mt-2 line-clamp-2 text-[11px] text-slate-600 leading-4">{tpl.request}</p>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {!tpl.builtIn && (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(tpl.id); }}
                    className="grid h-7 w-7 place-items-center rounded-lg border border-red-400/20 bg-red-950/20 text-red-400 hover:bg-red-950/40 transition-all"
                    title="Delete template"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                )}
                <div className="grid h-7 w-7 place-items-center rounded-lg border border-cyan-400/20 bg-cyan-950/20 text-cyan-400">
                  <ChevronRight className="h-3.5 w-3.5" />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Save current request as template */}
      <div className="border-t border-white/[0.06] p-4">
        {showSaveForm ? (
          <div className="flex items-center gap-2">
            <input
              autoFocus
              type="text"
              value={savingName}
              onChange={(e) => setSavingName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') setShowSaveForm(false); }}
              placeholder="Template name…"
              className="flex-1 rounded-xl border border-white/[0.08] bg-black/20 px-3 py-2 text-xs text-white placeholder:text-slate-700 focus:border-cyan-400/40 focus:outline-none focus:ring-1 focus:ring-cyan-400/20"
            />
            <button
              onClick={handleSave}
              disabled={!savingName.trim() || !currentRequest?.trim()}
              className="rounded-xl border border-emerald-400/20 bg-emerald-950/20 px-3 py-2 text-xs text-emerald-300 hover:bg-emerald-950/40 disabled:opacity-40 transition-all"
            >
              Save
            </button>
            <button onClick={() => setShowSaveForm(false)} className="rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-400 hover:text-slate-200 transition-all">
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setShowSaveForm(true)}
            disabled={!currentRequest?.trim()}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/[0.07] bg-white/[0.02] py-2.5 text-xs text-slate-400 hover:border-white/[0.12] hover:text-slate-200 disabled:opacity-40 transition-all"
          >
            <Plus className="h-3.5 w-3.5" />
            Save current request as template
          </button>
        )}
      </div>
    </div>
  );
}
