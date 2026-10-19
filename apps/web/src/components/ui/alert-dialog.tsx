import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog';
import type * as React from 'react';
import { cn } from '../../lib/utils';
import { Button } from './button';

export const AlertDialog = AlertDialogPrimitive.Root;
export const AlertDialogTrigger = AlertDialogPrimitive.Trigger;
export function AlertDialogContent({ className, ...props }: React.ComponentProps<typeof AlertDialogPrimitive.Content>) {
  return <AlertDialogPrimitive.Portal><AlertDialogPrimitive.Overlay className="ui-overlay" />
    <AlertDialogPrimitive.Content className={cn('ui-dialog', className)} {...props} /></AlertDialogPrimitive.Portal>;
}
export const AlertDialogTitle = AlertDialogPrimitive.Title;
export const AlertDialogDescription = AlertDialogPrimitive.Description;
export function AlertDialogFooter(props: React.ComponentProps<'div'>) { return <div className="ui-dialog__footer" {...props} />; }
export function AlertDialogCancel(props: React.ComponentProps<typeof AlertDialogPrimitive.Cancel>) {
  return <AlertDialogPrimitive.Cancel asChild><Button variant="outline" {...props} /></AlertDialogPrimitive.Cancel>;
}
export function AlertDialogAction(props: React.ComponentProps<typeof AlertDialogPrimitive.Action> & { destructive?: boolean }) {
  const { destructive, ...rest } = props;
  return <AlertDialogPrimitive.Action asChild><Button variant={destructive ? 'destructive' : 'default'} {...rest} /></AlertDialogPrimitive.Action>;
}
