/**
 * Popover 浮动面板组件
 *
 * 基于 @base-ui/react/popover 封装，用于触发元素旁展开浮动内容。
 * 样式与现有 shadcn/ui 风格保持一致。
 */

import { Popover as PopoverPrimitive } from "@base-ui/react/popover";
import { cn } from "@/lib/utils";

/** Popover 根组件 */
function PopoverRoot({ children, ...props }: PopoverPrimitive.Root.Props) {
  return <PopoverPrimitive.Root {...props}>{children}</PopoverPrimitive.Root>;
}

/** Popover 触发器 */
function PopoverTrigger({
  className,
  children,
  ...props
}: PopoverPrimitive.Trigger.Props) {
  return (
    <PopoverPrimitive.Trigger
      className={cn(
        "inline-flex items-center justify-center outline-none",
        className
      )}
      {...props}
    >
      {children}
    </PopoverPrimitive.Trigger>
  );
}

/** Popover 弹出内容（已包含 Portal + Positioner + 样式） */
function PopoverPopup({
  className,
  children,
  ...props
}: PopoverPrimitive.Popup.Props) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Positioner sideOffset={6} align="end">
        <PopoverPrimitive.Popup
          className={cn(
            "z-50 w-96 max-w-[calc(100vw-2rem)] rounded-xl border bg-popover p-3 text-popover-foreground shadow-lg outline-none origin-top-right transition-[transform,opacity] duration-150 data-[starting-style]:scale-95 data-[starting-style]:opacity-0 data-[ending-style]:scale-95 data-[ending-style]:opacity-0",
            className
          )}
          {...props}
        >
          {children}
        </PopoverPrimitive.Popup>
      </PopoverPrimitive.Positioner>
    </PopoverPrimitive.Portal>
  );
}

/** Popover 箭头 */
function PopoverArrow({ className, ...props }: PopoverPrimitive.Arrow.Props) {
  return (
    <PopoverPrimitive.Arrow
      className={cn("fill-popover stroke-border", className)}
      {...props}
    />
  );
}

/** Popover 关闭按钮 */
function PopoverClose({ className, ...props }: PopoverPrimitive.Close.Props) {
  return (
    <PopoverPrimitive.Close
      className={cn(
        "inline-flex items-center justify-center rounded-md text-sm font-medium outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
        className
      )}
      {...props}
    />
  );
}

export const Popover = {
  Root: PopoverRoot,
  Trigger: PopoverTrigger,
  Portal: PopoverPrimitive.Portal,
  Positioner: PopoverPrimitive.Positioner,
  Popup: PopoverPopup,
  Arrow: PopoverArrow,
  Close: PopoverClose,
  Title: PopoverPrimitive.Title,
  Description: PopoverPrimitive.Description,
};
