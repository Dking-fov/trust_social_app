import { useState, useEffect, useCallback, useRef } from 'react';
import { PortraitItem, SortOption } from '../types/portrait';
import { fetchPortraitBatch } from '../services/portraitService';

export interface UsePortraitsOptions {
  initialCategory?: string;
  initialSort?: SortOption;
  initialQuery?: string;
  pageSize?: number;
}

export function usePortraits(options: UsePortraitsOptions = {}) {
  const {
    initialCategory = 'all',
    initialSort = 'hot',
    initialQuery = '',
    pageSize = 8,
  } = options;

  const [category, setCategory] = useState<string>(initialCategory);
  const [sortBy, setSortBy] = useState<SortOption>(initialSort);
  const [searchQuery, setSearchQuery] = useState<string>(initialQuery);

  const [portraits, setPortraits] = useState<PortraitItem[]>([]);
  const [page, setPage] = useState<number>(1);
  const [hasMore, setHasMore] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);

  const inFlightRef = useRef<boolean>(false);

  // Load first page whenever category, sortBy, or searchQuery changes
  const loadInitialBatch = useCallback(
    async (cat: string, sort: SortOption, query: string) => {
      setIsLoading(true);
      setError(null);
      setPage(1);

      try {
        const result = await fetchPortraitBatch(
          {
            category: cat,
            sortBy: sort,
            query,
            page: 1,
            pageSize,
          },
          250
        );

        setPortraits(result.items);
        setHasMore(result.hasMore);
        setTotalCount(result.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载人像失败');
      } finally {
        setIsLoading(false);
      }
    },
    [pageSize]
  );

  useEffect(() => {
    loadInitialBatch(category, sortBy, searchQuery);
  }, [category, sortBy, searchQuery, loadInitialBatch]);

  // Load next batch for infinite scroll
  const loadMore = useCallback(async () => {
    if (inFlightRef.current || !hasMore || isLoading || isLoadingMore) {
      return;
    }

    inFlightRef.current = true;
    setIsLoadingMore(true);

    const nextPage = page + 1;
    try {
      const result = await fetchPortraitBatch(
        {
          category,
          sortBy,
          query: searchQuery,
          page: nextPage,
          pageSize,
        },
        300
      );

      setPortraits((prev) => [...prev, ...result.items]);
      setHasMore(result.hasMore);
      setPage(nextPage);
      setTotalCount(result.total);
    } catch (err) {
      console.error('[usePortraits] Load more error:', err);
    } finally {
      setIsLoadingMore(false);
      inFlightRef.current = false;
    }
  }, [hasMore, isLoading, isLoadingMore, page, category, sortBy, searchQuery, pageSize]);

  const selectCategory = useCallback((catId: string) => {
    setCategory((curr) => (curr === catId ? 'all' : catId));
  }, []);

  const resetFilters = useCallback(() => {
    setCategory('all');
    setSearchQuery('');
    setSortBy('hot');
  }, []);

  return {
    portraits,
    category,
    sortBy,
    searchQuery,
    isLoading,
    isLoadingMore,
    hasMore,
    totalCount,
    error,
    setCategory: selectCategory,
    setSortBy,
    setSearchQuery,
    loadMore,
    refresh: () => loadInitialBatch(category, sortBy, searchQuery),
    resetFilters,
  };
}
