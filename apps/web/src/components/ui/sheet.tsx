import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type * as React from 'react';
import { cn } from '../../lib/utils';

export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;
export function SheetContent({ side = 'left', className, children, ...props }:
  React.ComponentProps<typeof DialogPrimitive.Content> & { side?: 'left' | 'right' | 'bottom' }) {
  return <DialogPrimitive.Portal><DialogPrimitive.Overlay className="ui-overlay" />
    <DialogPrimitive.Content className={cn('ui-sheet', `ui-sheet--${side}`, className)} {...props}>
      {children}<DialogPrimitive.Close className="ui-sheet__close" aria-label="Tutup panel"><X aria-hidden="true" /></DialogPrimitive.Close>
    </DialogPrimitive.Content></DialogPrimitive.Portal>;
}
export const SheetTitle = DialogPrimitive.Title;
export const SheetDescription = DialogPrimitive.Description;
