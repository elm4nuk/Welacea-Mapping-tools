import * as DropdownPrimitive from '@radix-ui/react-dropdown-menu';
import type * as React from 'react';
import { cn } from '../../lib/utils';

export const DropdownMenu = DropdownPrimitive.Root;
export const DropdownMenuTrigger = DropdownPrimitive.Trigger;
export function DropdownMenuContent({ className, sideOffset = 6, ...props }: React.ComponentProps<typeof DropdownPrimitive.Content>) {
  return <DropdownPrimitive.Portal><DropdownPrimitive.Content sideOffset={sideOffset} className={cn('ui-menu', className)} {...props} /></DropdownPrimitive.Portal>;
}
export function DropdownMenuItem({ className, destructive, ...props }:
  React.ComponentProps<typeof DropdownPrimitive.Item> & { destructive?: boolean }) {
  return <DropdownPrimitive.Item className={cn('ui-menu__item', destructive && 'ui-menu__item--destructive', className)} {...props} />;
}
export const DropdownMenuSeparator = DropdownPrimitive.Separator;
