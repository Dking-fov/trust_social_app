import { useState, useEffect, useMemo } from 'react';
import { PortraitItem } from '../types/portrait';

export interface UseMasonryColumnsOptions {
  breakpoints?: {
    mobileMax?: number; // default: 768 -> 2 cols
    tabletMax?: number; // default: 1100 -> 3 cols
    desktopMax?: number; // default: 1440 -> 4 cols
  };
}

/**
 * Calculates responsive column count based on viewport width.
 */
export function getColumnCount(width: number): number {
  if (width < 768) {
    return 2; // Mobile double-column waterfall
  }
  if (width < 1100) {
    return 3; // Tablet 3 columns
  }
  if (width < 1440) {
    return 4; // Standard desktop 4 columns
  }
  return 5; // Ultra-wide desktop 5 columns
}

/**
 * Balances an array of items across multiple columns using estimated heights.
 */
export function balanceColumns(items: PortraitItem[], columnCount: number): PortraitItem[][] {
  if (columnCount <= 1) {
    return [items];
  }

  const columns: PortraitItem[][] = Array.from({ length: columnCount }, () => []);
  const columnHeights: number[] = Array.from({ length: columnCount }, () => 0);

  items.forEach((item) => {
    // Find the column with the current minimum height
    let shortestIndex = 0;
    let minHeight = columnHeights[0];

    for (let i = 1; i < columnCount; i++) {
      if (columnHeights[i] < minHeight) {
        minHeight = columnHeights[i];
        shortestIndex = i;
      }
    }

    // Estimate card height: image height ratio (height / width) + fixed header/footer allowance (~75px)
    const ratio = item.aspectRatio > 0 ? 1 / item.aspectRatio : 1.33;
    const estimatedHeight = ratio * 300 + 75;

    columns[shortestIndex].push(item);
    columnHeights[shortestIndex] += estimatedHeight;
  });

  return columns;
}

/**
 * Hook to manage responsive waterfall columns and height-balanced distribution.
 */
export function useMasonryColumns(items: PortraitItem[]) {
  const [columnCount, setColumnCount] = useState<number>(() => {
    if (typeof window !== 'undefined') {
      return getColumnCount(window.innerWidth);
    }
    return 2;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;

    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const handleResize = () => {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        setColumnCount(getColumnCount(window.innerWidth));
      }, 100);
    };

    window.addEventListener('resize', handleResize);
    // Initial sync
    setColumnCount(getColumnCount(window.innerWidth));

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  const columns = useMemo(() => {
    return balanceColumns(items, columnCount);
  }, [items, columnCount]);

  return {
    columnCount,
    columns,
  };
}
