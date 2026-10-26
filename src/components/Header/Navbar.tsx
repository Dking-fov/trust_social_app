import React, { useState, useEffect } from 'react';
import { Search, X, SlidersHorizontal, Sparkles } from 'lucide-react';
import { SortOption } from '../../types/portrait';
import { SORT_OPTIONS } from '../../constants/tags';

export interface NavbarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  sortBy: SortOption;
  onSortChange: (sort: SortOption) => void;
  totalCount?: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  searchQuery,
  onSearchChange,
  sortBy,
  onSortChange,
  totalCount,
}) => {
  const [localInput, setLocalInput] = useState(searchQuery);

  useEffect(() => {
    setLocalInput(searchQuery);
  }, [searchQuery]);

  const handleClear = () => {
    setLocalInput('');
    onSearchChange('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      onSearchChange(localInput);
    }
  };

  return (
    <header className="sticky top-0 z-30 w-full bg-white/95 backdrop-blur-md border-b border-gray-100 shadow-[0_1px_3px_rgba(0,0,0,0.03)]">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 h-16 flex items-center justify-between gap-3">
        {/* Brand / Logo */}
        <div className="flex items-center gap-2 flex-shrink-0 cursor-pointer select-none">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-[#ff1744] to-[#ff4081] flex items-center justify-center text-white font-black text-sm tracking-tighter shadow-sm hover:scale-105 transition-transform">
            RED
          </div>
          <div className="hidden sm:flex flex-col">
            <span className="font-bold text-gray-900 text-base leading-tight tracking-tight flex items-center gap-1">
              人像精选
              <Sparkles className="w-3.5 h-3.5 text-red-brand" />
            </span>
            <span className="text-[10px] text-gray-400 font-medium tracking-wide">
              TRENDING PORTRAITS
            </span>
          </div>
        </div>

        {/* Search Bar */}
        <div className="flex-1 max-w-xl mx-2 sm:mx-6">
          <div className="relative flex items-center w-full">
            <div className="absolute left-3 text-gray-400 pointer-events-none">
              <Search className="w-4 h-4" />
            </div>
            <input
              type="text"
              value={localInput}
              onChange={(e) => {
                setLocalInput(e.target.value);
                onSearchChange(e.target.value);
              }}
              onKeyDown={handleKeyDown}
              placeholder="搜索热门人像、摄影师、风格标签..."
              className="w-full h-10 pl-9 pr-8 bg-gray-100 hover:bg-gray-150/80 focus:bg-white text-sm text-gray-800 placeholder-gray-400 rounded-full border border-transparent focus:border-red-brand/40 focus:ring-2 focus:ring-red-light outline-none transition-all"
            />
            {localInput && (
              <button
                type="button"
                onClick={handleClear}
                className="absolute right-3 text-gray-400 hover:text-gray-600 p-0.5 rounded-full hover:bg-gray-200"
                aria-label="清空搜索"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Sort Selector */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="relative inline-flex items-center">
            <SlidersHorizontal className="w-4 h-4 text-gray-400 mr-1.5 hidden md:inline" />
            <select
              value={sortBy}
              onChange={(e) => onSortChange(e.target.value as SortOption)}
              className="text-xs sm:text-sm font-medium text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-full py-1.5 px-3 focus:outline-none focus:border-red-brand cursor-pointer transition-colors"
              aria-label="排序方式"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {typeof totalCount === 'number' && (
            <span className="hidden lg:inline-block text-xs text-gray-400 ml-1">
              共 {totalCount} 篇
            </span>
          )}
        </div>
      </div>
    </header>
  );
};
