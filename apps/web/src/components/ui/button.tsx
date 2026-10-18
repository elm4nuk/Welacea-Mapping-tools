import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva } from 'class-variance-authority';
import type { VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';
// Adapted from shadcn/ui Button (MIT); see apps/web/THIRD_PARTY.md.
const buttonVariants = cva('inline-flex min-h-11 items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-50', {
  variants: { variant: { default: 'bg-[#164b38] text-white hover:bg-[#236348]',
    outline: 'border border-[#9bab9b] bg-white text-[#213d30] hover:bg-[#edf5e6]' } },
  defaultVariants: { variant: 'default' },
});
export function Button({ className, variant, asChild = false, ...props }:
  React.ComponentProps<'button'> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'button';
  return <Comp data-slot="button" className={cn(buttonVariants({ variant, className }))} {...props} />;
}
