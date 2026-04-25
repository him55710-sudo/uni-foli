import React from 'react';
import { cn } from '../../lib/cn';
import { Card, type CardProps } from '../ui';

interface SurfaceCardProps extends CardProps {
  elevated?: boolean;
}

export function SurfaceCard({ elevated = false, className, children, ...props }: SurfaceCardProps) {
  return (
    <Card
      {...props}
      className={cn(
        'rounded-3xl border-transparent bg-white',
        elevated ? 'shadow-lg' : 'shadow-sm',
        className,
      )}
    >
      {children}
    </Card>
  );
}
