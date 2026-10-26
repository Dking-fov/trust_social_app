import React from 'react';

export interface CardSkeletonProps {
  aspectRatio?: number;
}

export const CardSkeleton: React.FC<CardSkeletonProps> = ({
  aspectRatio = 0.75, // default 3:4 ratio
}) => {
  return (
    <div
      data-testid="card-skeleton"
      className="bg-white rounded-2xl overflow-hidden border border-gray-100 shadow-sm animate-pulse flex flex-col"
    >
      {/* Image Skeleton */}
      <div
        className="w-full bg-gray-200"
        style={{ aspectRatio: `${aspectRatio}` }}
      />

      {/* Content Skeleton */}
      <div className="p-3 space-y-2.5">
        {/* Title Lines */}
        <div className="h-3.5 bg-gray-200 rounded-md w-11/12" />
        <div className="h-3 bg-gray-200 rounded-md w-3/4" />

        {/* Creator & Like Skeleton */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-full bg-gray-200" />
            <div className="w-16 h-3 bg-gray-200 rounded" />
          </div>
          <div className="w-8 h-3 bg-gray-200 rounded" />
        </div>
      </div>
    </div>
  );
};
