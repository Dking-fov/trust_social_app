import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Header/Navbar';
import { TagFilterBar } from './components/Filter/TagFilterBar';
import { WaterfallGrid } from './components/Waterfall/WaterfallGrid';
import { PortraitDetailModal } from './components/Modal/PortraitDetailModal';
import { InfiniteScrollTrigger } from './components/Common/InfiniteScrollTrigger';
import { usePortraits } from './hooks/usePortraits';
import { useLikes } from './hooks/useLikes';
import { PortraitItem } from './types/portrait';
import { ArrowUp } from 'lucide-react';

export const App: React.FC = () => {
  const {
    portraits,
    category,
    sortBy,
    searchQuery,
    isLoading,
    isLoadingMore,
    hasMore,
    totalCount,
    setCategory,
    setSortBy,
    setSearchQuery,
    loadMore,
    resetFilters,
  } = usePortraits({
    initialCategory: 'all',
    initialSort: 'hot',
    pageSize: 8,
  });

  const {
    likedSet,
    toggleLike,
    isLiked,
    getAdjustedLikesCount,
    bouncingId,
  } = useLikes();

  const [selectedPortrait, setSelectedPortrait] = useState<PortraitItem | null>(null);
  const [showScrollTop, setShowScrollTop] = useState<boolean>(false);

  // Monitor scroll for back-to-top button
  useEffect(() => {
    const handleScroll = () => {
      setShowScrollTop(window.scrollY > 400);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCardClick = (item: PortraitItem) => {
    setSelectedPortrait(item);
  };

  const handleCloseModal = () => {
    setSelectedPortrait(null);
  };

  return (
    <div className="min-h-screen bg-surface flex flex-col antialiased text-text-primary">
      {/* Top Navbar */}
      <Navbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        sortBy={sortBy}
        onSortChange={setSortBy}
        totalCount={totalCount}
      />

      {/* Categories & Filter Bar */}
      <TagFilterBar
        activeCategory={category}
        onSelectCategory={setCategory}
      />

      {/* Main Content: Waterfall Feed */}
      <main className="flex-1 w-full max-w-7xl mx-auto">
        <WaterfallGrid
          items={portraits}
          isLoading={isLoading}
          likedSet={likedSet}
          getAdjustedLikesCount={getAdjustedLikesCount}
          bouncingId={bouncingId}
          onLikeToggle={toggleLike}
          onCardClick={handleCardClick}
          onResetFilters={resetFilters}
        />

        {/* Infinite Scroll Trigger Sentinel */}
        {portraits.length > 0 && (
          <InfiniteScrollTrigger
            hasMore={hasMore}
            isLoadingMore={isLoadingMore}
            onLoadMore={loadMore}
          />
        )}
      </main>

      {/* Interactive Detail Modal / Lightbox */}
      <PortraitDetailModal
        portrait={selectedPortrait}
        isOpen={!!selectedPortrait}
        onClose={handleCloseModal}
        isLiked={selectedPortrait ? isLiked(selectedPortrait.id) : false}
        likesCount={
          selectedPortrait
            ? getAdjustedLikesCount(selectedPortrait.id, selectedPortrait.likesCount)
            : 0
        }
        isBouncing={selectedPortrait ? bouncingId === selectedPortrait.id : false}
        onLikeToggle={() => {
          if (selectedPortrait) {
            toggleLike(selectedPortrait.id);
          }
        }}
      />

      {/* Back to Top Floating Button */}
      {showScrollTop && (
        <button
          type="button"
          onClick={scrollToTop}
          className="fixed bottom-6 right-6 z-40 w-11 h-11 rounded-full bg-white text-gray-700 shadow-lg border border-gray-100 flex items-center justify-center hover:bg-gray-50 hover:text-red-brand active:scale-95 transition-all"
          aria-label="返回顶部"
        >
          <ArrowUp className="w-5 h-5" />
        </button>
      )}
    </div>
  );
};

export default App;
