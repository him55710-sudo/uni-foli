import React from 'react';
import { cn } from '../../lib/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'tertiary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

interface ButtonStyleOptions {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    'border-transparent bg-[#3182f6] text-white shadow-md shadow-blue-200/50 hover:bg-[#1b64da] active:scale-[0.96]',
  secondary:
    'border-transparent bg-[#f2f4f6] text-[#333d4b] hover:bg-[#e5e8eb] active:scale-[0.96]',
  tertiary: 'border-transparent bg-blue-50 text-[#3182f6] hover:bg-blue-100 active:scale-[0.96]',
  ghost: 'border-transparent bg-transparent text-[#6b7684] hover:bg-[#f2f4f6] hover:text-[#3182f6]',
  danger: 'border-transparent bg-[#f04452] text-white shadow-md shadow-red-100 hover:bg-[#d73441] active:scale-[0.96]',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-10 rounded-[0.9rem] px-3.5 text-sm font-bold',
  md: 'h-12 rounded-[1.1rem] px-5 text-sm font-bold',
  lg: 'h-14 rounded-[1.2rem] px-6 text-base font-black',
  icon: 'h-12 w-12 rounded-[1.1rem] p-0',
};

export function buttonClassName(options: ButtonStyleOptions = {}) {
  const { variant = 'secondary', size = 'md', fullWidth = false } = options;

  return cn(
    'inline-flex items-center justify-center gap-2 border transition-all duration-200 ease-out disabled:cursor-not-allowed disabled:opacity-50',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600/30 focus-visible:ring-offset-2',
    variantClasses[variant],
    sizeClasses[size],
    fullWidth && 'w-full',
  );
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, ButtonStyleOptions {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', fullWidth = false, className, type = 'button', ...props },
  ref,
) {
  return <button ref={ref} type={type} className={cn(buttonClassName({ variant, size, fullWidth }), className)} {...props} />;
});
