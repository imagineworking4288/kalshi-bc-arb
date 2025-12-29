import { clsx } from 'clsx';
import type { ReactNode } from 'react';

interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  size?: 'sm' | 'md';
  children: ReactNode;
  className?: string;
}

export function Badge({
  variant = 'default',
  size = 'md',
  children,
  className,
}: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center font-medium rounded-full',
        {
          // Variants
          'bg-gray-700 text-gray-300': variant === 'default',
          'bg-emerald-900/50 text-emerald-400 border border-emerald-700':
            variant === 'success',
          'bg-yellow-900/50 text-yellow-400 border border-yellow-700':
            variant === 'warning',
          'bg-red-900/50 text-red-400 border border-red-700':
            variant === 'danger',
          'bg-blue-900/50 text-blue-400 border border-blue-700':
            variant === 'info',

          // Sizes
          'px-2 py-0.5 text-xs': size === 'sm',
          'px-2.5 py-1 text-sm': size === 'md',
        },
        className
      )}
    >
      {children}
    </span>
  );
}
