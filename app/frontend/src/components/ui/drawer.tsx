"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

// Lightweight, dependency-free Drawer mimicking the shadcn/vaul API surface
// so consumers can swap to `vaul` later by changing only this file.
// Renders as a slide-up bottom sheet with overlay + focus trap-lite.

interface DrawerContextValue {
  open: boolean;
  setOpen: (v: boolean) => void;
  titleId: string;
  descriptionId: string;
}

const DrawerContext = React.createContext<DrawerContextValue | null>(null);

function useDrawer(component: string): DrawerContextValue {
  const ctx = React.useContext(DrawerContext);
  if (!ctx)
    throw new Error(`${component} must be used inside <Drawer>.`);
  return ctx;
}

interface DrawerProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

function Drawer({
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  children,
}: DrawerProps) {
  const reactId = React.useId();
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? (controlledOpen as boolean) : internalOpen;

  const setOpen = React.useCallback(
    (next: boolean) => {
      if (!isControlled) setInternalOpen(next);
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange]
  );

  return (
    <DrawerContext.Provider
      value={{
        open,
        setOpen,
        titleId: `${reactId}-title`,
        descriptionId: `${reactId}-description`,
      }}
    >
      {children}
    </DrawerContext.Provider>
  );
}

interface DrawerTriggerProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean;
}

const DrawerTrigger = React.forwardRef<HTMLButtonElement, DrawerTriggerProps>(
  ({ asChild, onClick, children, ...props }, ref) => {
    const { setOpen } = useDrawer("DrawerTrigger");

    if (asChild && React.isValidElement(children)) {
      const child = children as React.ReactElement<
        React.ButtonHTMLAttributes<HTMLButtonElement>
      >;
      return React.cloneElement(child, {
        ...child.props,
        onClick: (e: React.MouseEvent<HTMLButtonElement>) => {
          child.props.onClick?.(e);
          setOpen(true);
        },
      });
    }

    return (
      <button
        ref={ref}
        type="button"
        onClick={(e) => {
          onClick?.(e);
          setOpen(true);
        }}
        {...props}
      >
        {children}
      </button>
    );
  }
);
DrawerTrigger.displayName = "DrawerTrigger";

const DrawerContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const { open, setOpen, titleId, descriptionId } = useDrawer("DrawerContent");

  // Close on Escape
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  // Lock body scroll while open
  React.useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center"
      role="presentation"
    >
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setOpen(false)}
        aria-hidden="true"
      />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className={cn(
          "relative z-10 mt-24 w-full max-w-3xl rounded-t-[10px] border bg-background shadow-lg animate-in slide-in-from-bottom",
          className
        )}
        {...props}
      >
        <div className="mx-auto mt-2 h-1.5 w-12 rounded-full bg-muted" />
        {children}
      </div>
    </div>
  );
});
DrawerContent.displayName = "DrawerContent";

const DrawerHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn("grid gap-1.5 p-4 text-center sm:text-left", className)}
    {...props}
  />
);
DrawerHeader.displayName = "DrawerHeader";

const DrawerFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn("mt-auto flex flex-col gap-2 p-4", className)}
    {...props}
  />
);
DrawerFooter.displayName = "DrawerFooter";

const DrawerTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, id, ...props }, ref) => {
  const { titleId } = useDrawer("DrawerTitle");
  return (
    <h2
      ref={ref}
      id={id ?? titleId}
      className={cn(
        "text-lg font-semibold leading-none tracking-tight",
        className
      )}
      {...props}
    />
  );
});
DrawerTitle.displayName = "DrawerTitle";

const DrawerDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, id, ...props }, ref) => {
  const { descriptionId } = useDrawer("DrawerDescription");
  return (
    <p
      ref={ref}
      id={id ?? descriptionId}
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
});
DrawerDescription.displayName = "DrawerDescription";

const DrawerClose = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement>
>(({ onClick, ...props }, ref) => {
  const { setOpen } = useDrawer("DrawerClose");
  return (
    <button
      ref={ref}
      type="button"
      onClick={(e) => {
        onClick?.(e);
        setOpen(false);
      }}
      {...props}
    />
  );
});
DrawerClose.displayName = "DrawerClose";

export {
  Drawer,
  DrawerTrigger,
  DrawerContent,
  DrawerHeader,
  DrawerFooter,
  DrawerTitle,
  DrawerDescription,
  DrawerClose,
};
