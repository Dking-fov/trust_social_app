import React from 'react';
import { PortraitItem } from '../../types/portrait';
import { PortraitCard } from './PortraitCard';
import { CardSkeleton } from './CardSkeleton';
import { useMasonryColumns } from '../../hooks/useMasonryColumns';
import { EmptyState } from '../Common/EmptyState';

export interface WaterfallGridProps {
  items: PortraitItem[];
  isLoading: boolean;
  likedSet: Set<string>;
  getAdjustedLikesCount: (postId: string, baseLikes: number) => number;
  bouncingId?: string | null;
  onLikeToggle: (postId: string) => void;
  onCardClick: (item: PortraitItem) => void;
  onResetFilters?: () => void;
}

export const WaterfallGrid: React.FC<WaterfallGridProps> = ({
  items,
  isLoading,
  likedSet,
  getAdjustedLikesCount,
  bouncingId,
  onLikeToggle,
  onCardClick,
  onResetFilters,
}) => {
  const { columns, columnCount } = useMasonryColumns(items);

  // If initial load is in progress and we have zero items yet, display skeleton columns
  if (isLoading && items.length === 0) {
    const dummySkeletons = [0.75, 0.67, 0.8, 0.7, 0.75, 0.67, 0.82, 0.72];
    return (
      <div
        data-testid="waterfall-loading-skeleton"
        className="max-w-7xl mx-auto px-2 sm:px-6 py-4 grid gap-3 sm:gap-4"
        style={{
          gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))`,
        }}
      >
        {Array.from({ length: columnCount }).map((_, colIdx) => (
          <div key={`skel-col-${colIdx}`} className="flex flex-col gap-3 sm:gap-4">
            {dummySkeletons
              .filter((_, idx) => idx % columnCount === colIdx)
              .map((ratio, sIdx) => (
                <CardSkeleton key={`skel-${colIdx}-${sIdx}`} aspectRatio={ratio} />
              ))}
          </div>
        ))}
      </div>
    );
  }

  // If no items match search or category filters
  if (!isLoading && items.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <EmptyState onReset={onResetFilters} />
      </div>
    );
  }

  return (
    <div
      data-testid="waterfall-grid"
      className="max-w-7xl mx-auto px-2 sm:px-6 py-4 grid gap-3 sm:gap-4 items-start"
      style={{
        gridTemplateColumns: `repeat(${columnCount}, minmax(0, 1fr))`,
      }}
    >
      {columns.map((columnItems, columnIndex) => (
        <div
          key={`col-${columnIndex}`}
          data-testid={`waterfall-col-${columnIndex}`}
          className="flex flex-col gap-3 sm:gap-4"
        >
          {columnItems.map((portrait) => {
            const isLiked = likedSet.has(portrait.id);
            const currentLikes = getAdjustedLikesCount(portrait.id, portrait.likesCount);

            return (
              <PortraitCard
                key={portrait.id}
                portrait={portrait}
                isLiked={isLiked}
                likesCount={currentLikes}
                isBouncing={bouncingId === portrait.id}
                onLikeToggle={() => onLikeToggle(portrait.id)}
                onClick={() => onCardClick(portrait)}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
};
