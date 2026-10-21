import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva } from 'class-variance-authority';
import type { VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';
// Adapted from shadcn/ui Button (MIT); see apps/web/THIRD_PARTY.md.
export const buttonVariants = cva('ui-button', {
  variants: {
    variant: {
      default: 'ui-button--default', secondary: 'ui-button--secondary', outline: 'ui-button--outline',
      ghost: 'ui-button--ghost', destructive: 'ui-button--destructive',
    },
    size: { default: 'ui-button--md', sm: 'ui-button--sm', icon: 'ui-button--icon' },
  },
  defaultVariants: { variant: 'default', size: 'default' },
});
export function Button({ className, variant, size, asChild = false, ...props }:
  React.ComponentProps<'button'> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'button';
  return <Comp data-slot="button" className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}
