import React from 'react';
import { Heart } from 'lucide-react';
import { PortraitItem } from '../../types/portrait';
import { ImageWithFallback } from '../Common/ImageWithFallback';

export interface PortraitCardProps {
  portrait: PortraitItem;
  isLiked: boolean;
  likesCount: number;
  isBouncing?: boolean;
  onLikeToggle: (e: React.MouseEvent) => void;
  onClick: () => void;
}

export function formatCount(count: number): string {
  if (count >= 10000) {
    const val = (count / 10000).toFixed(1);
    return `${val.replace(/\.0$/, '')}万`;
  }
  if (count >= 1000) {
    const val = (count / 1000).toFixed(1);
    return `${val.replace(/\.0$/, '')}k`;
  }
  return `${count}`;
}

export const PortraitCard: React.FC<PortraitCardProps> = ({
  portrait,
  isLiked,
  likesCount,
  isBouncing = false,
  onLikeToggle,
  onClick,
}) => {
  return (
    <article
      data-testid={`portrait-card-${portrait.id}`}
      onClick={onClick}
      className="group relative flex flex-col bg-white rounded-2xl overflow-hidden shadow-[0_1px_4px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_20px_rgba(0,0,0,0.08)] border border-gray-150/60 transition-all duration-300 cursor-pointer transform hover:-translate-y-0.5"
    >
      {/* Portrait Image Cover */}
      <div className="w-full relative overflow-hidden bg-gray-50">
        <ImageWithFallback
          src={portrait.imageUrl}
          alt={portrait.title}
          aspectRatio={portrait.aspectRatio}
          imgClassName="group-hover:scale-[1.02] transition-transform duration-500 ease-out"
        />

        {/* Category Tag pill on image top-left */}
        {portrait.tags[0] && (
          <span className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-full bg-black/40 backdrop-blur-sm text-[11px] text-white font-medium tracking-tight">
            #{portrait.tags[0]}
          </span>
        )}
      </div>

      {/* Card Content Footer */}
      <div className="p-3 flex flex-col gap-2">
        {/* Title */}
        <h2 className="text-xs sm:text-sm font-semibold text-gray-800 line-clamp-2 leading-snug group-hover:text-red-brand transition-colors">
          {portrait.title}
        </h2>

        {/* Author Info & Like Button */}
        <div className="flex items-center justify-between text-xs text-gray-500 pt-1">
          {/* Creator Profile */}
          <div className="flex items-center gap-1.5 min-w-0 flex-1 mr-2">
            <img
              src={portrait.creator.avatar}
              alt={portrait.creator.name}
              loading="lazy"
              className="w-5 h-5 rounded-full object-cover flex-shrink-0 border border-gray-100"
              onError={(e) => {
                // Fallback avatar
                (e.target as HTMLImageElement).src =
                  'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=100&q=80';
              }}
            />
            <span className="truncate font-medium text-gray-600 text-[11px] sm:text-xs">
              {portrait.creator.name}
            </span>
          </div>

          {/* Like Interaction Button */}
          <button
            type="button"
            data-testid={`like-btn-${portrait.id}`}
            onClick={(e) => {
              e.stopPropagation();
              onLikeToggle(e);
            }}
            className="flex items-center gap-1 text-gray-500 hover:text-red-brand p-1 -mr-1 rounded-md active:scale-90 transition-all select-none"
            aria-label={isLiked ? '取消点赞' : '点赞'}
          >
            <Heart
              className={`w-4 h-4 transition-transform duration-200 ${
                isLiked
                  ? 'fill-red-brand text-red-brand'
                  : 'text-gray-400 hover:text-red-brand'
              } ${isBouncing ? 'animate-likeBounce' : ''}`}
            />
            <span
              className={`text-xs font-medium tabular-nums ${
                isLiked ? 'text-red-brand font-semibold' : 'text-gray-500'
              }`}
            >
              {formatCount(likesCount)}
            </span>
          </button>
        </div>
      </div>
    </article>
  );
};
