import * as React from 'react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface TabsContextValue {
  value: string;
  onChange: (v: string) => void;
  /** Stable base id used to derive tab / panel ids */
  baseId: string;
}

const TabsContext = React.createContext<TabsContextValue>({
  value: '',
  onChange: () => {},
  baseId: 'tabs',
});

// ---------------------------------------------------------------------------
// Tabs (root)
// ---------------------------------------------------------------------------

const Tabs = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { defaultValue?: string; value?: string; onValueChange?: (v: string) => void }
>(({ className, defaultValue, value, onValueChange, children, ...props }, ref) => {
  const [innerValue, setInnerValue] = React.useState(defaultValue || '');
  const activeValue = value !== undefined ? value : innerValue;

  const reactId = React.useId();

  const ctx = React.useMemo<TabsContextValue>(
    () => ({
      value: activeValue,
      onChange: onValueChange || setInnerValue,
      baseId: reactId,
    }),
    [activeValue, onValueChange, reactId],
  );

  return (
    <TabsContext.Provider value={ctx}>
      <div ref={ref} className={cn('w-full', className)} {...props}>
        {children}
      </div>
    </TabsContext.Provider>
  );
});
Tabs.displayName = 'Tabs';

// ---------------------------------------------------------------------------
// TabsList
// ---------------------------------------------------------------------------

const TabsList = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, onKeyDown, ...props }, ref) => {
  const handleKeyDown = React.useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      const list = event.currentTarget;
      const tabs = Array.from(
        list.querySelectorAll<HTMLButtonElement>('[role="tab"]:not([disabled])'),
      );
      if (tabs.length === 0) return;

      const current = document.activeElement as HTMLElement;
      const currentIndex = tabs.indexOf(current as HTMLButtonElement);

      let nextIndex: number | null = null;

      switch (event.key) {
        case 'ArrowRight':
          nextIndex = currentIndex < tabs.length - 1 ? currentIndex + 1 : 0;
          break;
        case 'ArrowLeft':
          nextIndex = currentIndex > 0 ? currentIndex - 1 : tabs.length - 1;
          break;
        case 'Home':
          nextIndex = 0;
          break;
        case 'End':
          nextIndex = tabs.length - 1;
          break;
        default:
          break;
      }

      if (nextIndex !== null) {
        event.preventDefault();
        tabs[nextIndex].focus();
      }

      onKeyDown?.(event);
    },
    [onKeyDown],
  );

  return (
    <div
      ref={ref}
      role="tablist"
      onKeyDown={handleKeyDown}
      className={cn(
        'inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground',
        className,
      )}
      {...props}
    />
  );
});
TabsList.displayName = 'TabsList';

// ---------------------------------------------------------------------------
// TabsTrigger
// ---------------------------------------------------------------------------

const TabsTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string }
>(({ className, value, ...props }, ref) => {
  const ctx = React.useContext(TabsContext);
  const active = ctx.value === value;
  const tabId = `${ctx.baseId}-tab-${value}`;
  const panelId = `${ctx.baseId}-panel-${value}`;

  return (
    <button
      ref={ref}
      id={tabId}
      role="tab"
      type="button"
      aria-selected={active}
      aria-controls={panelId}
      tabIndex={active ? 0 : -1}
      onClick={() => ctx.onChange(value)}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
        active ? 'bg-background text-foreground shadow' : 'hover:bg-background/50 hover:text-foreground',
        className,
      )}
      {...props}
    />
  );
});
TabsTrigger.displayName = 'TabsTrigger';

// ---------------------------------------------------------------------------
// TabsContent
// ---------------------------------------------------------------------------

const TabsContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { value: string }
>(({ className, value, ...props }, ref) => {
  const ctx = React.useContext(TabsContext);
  const tabId = `${ctx.baseId}-tab-${value}`;
  const panelId = `${ctx.baseId}-panel-${value}`;

  if (ctx.value !== value) return null;

  return (
    <div
      ref={ref}
      id={panelId}
      role="tabpanel"
      aria-labelledby={tabId}
      tabIndex={0}
      className={cn(
        'mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        className,
      )}
      {...props}
    />
  );
});
TabsContent.displayName = 'TabsContent';

export { Tabs, TabsList, TabsTrigger, TabsContent };
