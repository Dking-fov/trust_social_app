import React, { useRef } from 'react';
import { DEFAULT_CATEGORIES } from '../../constants/tags';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export interface TagFilterBarProps {
  activeCategory: string;
  onSelectCategory: (categoryId: string) => void;
}

export const TagFilterBar: React.FC<TagFilterBarProps> = ({
  activeCategory,
  onSelectCategory,
}) => {
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  const scroll = (direction: 'left' | 'right') => {
    if (scrollContainerRef.current) {
      const offset = direction === 'left' ? -200 : 200;
      scrollContainerRef.current.scrollBy({ left: offset, behavior: 'smooth' });
    }
  };

  return (
    <div className="relative w-full max-w-7xl mx-auto px-3 sm:px-6 py-3 select-none">
      <div className="flex items-center gap-1 group">
        {/* Left Scroll Arrow for Desktop */}
        <button
          type="button"
          onClick={() => scroll('left')}
          className="hidden md:flex items-center justify-center w-7 h-7 rounded-full bg-white shadow-sm border border-gray-100 text-gray-500 hover:text-gray-900 hover:bg-gray-50 transition-all z-10 flex-shrink-0"
          aria-label="向左滚动标签"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {/* Scrollable Container */}
        <div
          ref={scrollContainerRef}
          className="flex items-center gap-2 overflow-x-auto no-scrollbar scroll-smooth py-1 px-1 flex-1"
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {DEFAULT_CATEGORIES.map((cat) => {
            const isActive = activeCategory === cat.id;

            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => onSelectCategory(cat.id)}
                className={`flex-shrink-0 px-4 py-1.5 rounded-full text-xs sm:text-sm font-medium transition-all duration-200 cursor-pointer ${
                  isActive
                    ? 'bg-red-brand text-white shadow-[0_2px_8px_rgba(255,36,66,0.3)] scale-[1.03]'
                    : 'bg-white hover:bg-gray-100/90 text-gray-600 hover:text-gray-900 border border-gray-200/80'
                }`}
              >
                {cat.name}
              </button>
            );
          })}
        </div>

        {/* Right Scroll Arrow for Desktop */}
        <button
          type="button"
          onClick={() => scroll('right')}
          className="hidden md:flex items-center justify-center w-7 h-7 rounded-full bg-white shadow-sm border border-gray-100 text-gray-500 hover:text-gray-900 hover:bg-gray-50 transition-all z-10 flex-shrink-0"
          aria-label="向右滚动标签"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
