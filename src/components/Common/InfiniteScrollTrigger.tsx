import React, { useEffect, useRef } from 'react';
import { Loader2 } from 'lucide-react';

export interface InfiniteScrollTriggerProps {
  hasMore: boolean;
  isLoadingMore: boolean;
  onLoadMore: () => void;
  rootMargin?: string;
  endMessage?: string;
}

export const InfiniteScrollTrigger: React.FC<InfiniteScrollTriggerProps> = ({
  hasMore,
  isLoadingMore,
  onLoadMore,
  rootMargin = '300px',
  endMessage = '已加载全部精彩内容',
}) => {
  const triggerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!hasMore || isLoadingMore) return;

    const currentTrigger = triggerRef.current;
    if (!currentTrigger) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const firstEntry = entries[0];
        if (firstEntry && firstEntry.isIntersecting) {
          onLoadMore();
        }
      },
      {
        root: null,
        rootMargin,
        threshold: 0.1,
      }
    );

    observer.observe(currentTrigger);

    return () => {
      observer.disconnect();
    };
  }, [hasMore, isLoadingMore, onLoadMore, rootMargin]);

  return (
    <div
      ref={triggerRef}
      data-testid="infinite-scroll-trigger"
      className="w-full py-8 flex items-center justify-center text-sm text-gray-400 select-none"
    >
      {isLoadingMore ? (
        <div className="flex items-center gap-2 text-red-brand">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-xs font-medium text-gray-500">正在探索更多精彩人像...</span>
        </div>
      ) : !hasMore ? (
        <div className="flex items-center gap-3">
          <div className="h-[1px] w-12 bg-gray-200" />
          <span className="text-xs text-gray-400">{endMessage}</span>
          <div className="h-[1px] w-12 bg-gray-200" />
        </div>
      ) : (
        <div className="h-6" />
      )}
    </div>
  );
};
