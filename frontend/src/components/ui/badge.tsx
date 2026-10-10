import * as React from 'react';
import { cn } from '@/lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'awaiting' | 'active' | 'completed' | 'blocked';
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
        {
          'border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80': variant === 'default',
          'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80': variant === 'secondary',
          'border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80': variant === 'destructive',
          'text-foreground': variant === 'outline',
          'border-orange-400/50 bg-orange-950/60 text-orange-100': variant === 'awaiting',
          'border-blue-400/50 bg-blue-950/60 text-blue-100 animate-pulse-glow': variant === 'active',
          'border-emerald-400/50 bg-emerald-950/60 text-emerald-100': variant === 'completed',
          'border-red-400/50 bg-red-950/60 text-red-100': variant === 'blocked',
        },
        className
      )}
      {...props}
    />
  );
}

export { Badge };
