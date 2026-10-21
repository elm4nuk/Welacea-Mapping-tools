import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import type * as React from 'react';

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;
export function TooltipContent(props: React.ComponentProps<typeof TooltipPrimitive.Content>) {
  return <TooltipPrimitive.Portal><TooltipPrimitive.Content sideOffset={6} className="ui-tooltip" {...props} /></TooltipPrimitive.Portal>;
}
