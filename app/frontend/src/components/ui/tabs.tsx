"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

// Minimal, dependency-free Tabs primitive modeled after the shadcn API
// (Radix-compatible surface) so other agents can drop in @radix-ui/react-tabs
// later with no consumer changes.

interface TabsContextValue {
  value: string;
  setValue: (v: string) => void;
  baseId: string;
}

const TabsContext = React.createContext<TabsContextValue | null>(null);

function useTabsContext(component: string): TabsContextValue {
  const ctx = React.useContext(TabsContext);
  if (!ctx) {
    throw new Error(`${component} must be rendered inside <Tabs>.`);
  }
  return ctx;
}

interface TabsProps extends React.HTMLAttributes<HTMLDivElement> {
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
}

const Tabs = React.forwardRef<HTMLDivElement, TabsProps>(
  (
    {
      className,
      defaultValue = "",
      value: controlledValue,
      onValueChange,
      children,
      ...props
    },
    ref
  ) => {
    const reactId = React.useId();
    const [internal, setInternal] = React.useState(defaultValue);
    const isControlled = controlledValue !== undefined;
    const value = isControlled ? (controlledValue as string) : internal;

    const setValue = React.useCallback(
      (next: string) => {
        if (!isControlled) setInternal(next);
        onValueChange?.(next);
      },
      [isControlled, onValueChange]
    );

    return (
      <TabsContext.Provider value={{ value, setValue, baseId: reactId }}>
        <div ref={ref} className={cn(className)} {...props}>
          {children}
        </div>
      </TabsContext.Provider>
    );
  }
);
Tabs.displayName = "Tabs";

const TabsList = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    role="tablist"
    className={cn(
      "inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground",
      className
    )}
    {...props}
  />
));
TabsList.displayName = "TabsList";

interface TabsTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

const TabsTrigger = React.forwardRef<HTMLButtonElement, TabsTriggerProps>(
  ({ className, value, onClick, ...props }, ref) => {
    const ctx = useTabsContext("TabsTrigger");
    const active = ctx.value === value;
    return (
      <button
        ref={ref}
        role="tab"
        type="button"
        aria-selected={active}
        aria-controls={`${ctx.baseId}-content-${value}`}
        id={`${ctx.baseId}-trigger-${value}`}
        data-state={active ? "active" : "inactive"}
        tabIndex={active ? 0 : -1}
        onClick={(e) => {
          ctx.setValue(value);
          onClick?.(e);
        }}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
          active
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground",
          className
        )}
        {...props}
      />
    );
  }
);
TabsTrigger.displayName = "TabsTrigger";

interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
  forceMount?: boolean;
}

const TabsContent = React.forwardRef<HTMLDivElement, TabsContentProps>(
  ({ className, value, forceMount, ...props }, ref) => {
    const ctx = useTabsContext("TabsContent");
    const active = ctx.value === value;
    if (!active && !forceMount) return null;
    return (
      <div
        ref={ref}
        role="tabpanel"
        id={`${ctx.baseId}-content-${value}`}
        aria-labelledby={`${ctx.baseId}-trigger-${value}`}
        hidden={!active}
        data-state={active ? "active" : "inactive"}
        className={cn(
          "mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          className
        )}
        {...props}
      />
    );
  }
);
TabsContent.displayName = "TabsContent";

export { Tabs, TabsList, TabsTrigger, TabsContent };
