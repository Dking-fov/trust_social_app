import React, { useState } from 'react';
import { ImageOff } from 'lucide-react';

export interface ImageWithFallbackProps {
  src: string;
  alt: string;
  aspectRatio?: number; // width / height
  className?: string;
  imgClassName?: string;
  loading?: 'lazy' | 'eager';
  onClick?: () => void;
}

/**
 * Image component with skeleton shimmer placeholder, lazy loading, and error fallback.
 * Prevents Cumulative Layout Shift (CLS) by preserving the calculated aspect ratio box.
 */
export const ImageWithFallback: React.FC<ImageWithFallbackProps> = ({
  src,
  alt,
  aspectRatio,
  className = '',
  imgClassName = '',
  loading = 'lazy',
  onClick,
}) => {
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [hasError, setHasError] = useState<boolean>(false);

  // Compute CSS padding-top or aspect-ratio style
  const ratioStyle = aspectRatio
    ? { aspectRatio: `${aspectRatio}` }
    : undefined;

  return (
    <div
      className={`relative w-full overflow-hidden bg-slate-100 ${className}`}
      style={ratioStyle}
      onClick={onClick}
    >
      {/* Skeleton Shimmer Overlay */}
      {isLoading && !hasError && (
        <div
          data-testid="image-skeleton"
          className="absolute inset-0 bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 bg-[length:200%_100%] animate-shimmer"
        />
      )}

      {/* Fallback View on Load Error */}
      {hasError ? (
        <div
          data-testid="image-fallback"
          className="absolute inset-0 flex flex-col items-center justify-center bg-gray-100 text-gray-400 p-4 text-center select-none"
        >
          <div className="w-12 h-12 rounded-full bg-gray-200 flex items-center justify-center mb-2 text-gray-400">
            <ImageOff className="w-6 h-6" />
          </div>
          <span className="text-xs text-gray-500 font-medium">图片加载失败</span>
          <span className="text-[11px] text-gray-400 mt-0.5">点击重试或查看其他作品</span>
        </div>
      ) : (
        <img
          src={src}
          alt={alt}
          loading={loading}
          onLoad={() => setIsLoading(false)}
          onError={() => {
            setIsLoading(false);
            setHasError(true);
          }}
          className={`w-full h-full object-cover transition-opacity duration-300 ${
            isLoading ? 'opacity-0' : 'opacity-100'
          } ${imgClassName}`}
        />
      )}
    </div>
  );
};
