'use client';

import { Badge, BadgeProps } from '@/components/ui/badge';

const statusVariantMap: Record<string, BadgeProps['variant']> = {
  awaiting_approval: 'awaiting',
  coding: 'active',
  auto_fixing: 'active',
  scanning: 'active',
  reviewing: 'active',
  approved: 'active',
  sandboxing: 'active',
  completed: 'completed',
  blocked: 'blocked',
  needs_manual_intervention: 'blocked',
  failed: 'blocked',
  submitted: 'outline',
  planning: 'outline',
  needs_clarification: 'awaiting',
};

interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const variant = statusVariantMap[status] || 'outline';
  return (
    <Badge variant={variant} className="text-xs uppercase tracking-wider">
      {status.replace(/_/g, ' ')}
    </Badge>
  );
}
