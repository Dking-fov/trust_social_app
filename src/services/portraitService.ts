/**
 * Service layer handling search, tag filtering, sorting, and paginated loading of portraits.
 */

import { MOCK_PORTRAITS, generateRandomPortraits } from '../data/mockPortraits';
import { FilterCriteria, PortraitItem, SortOption } from '../types/portrait';
import { getLikedPostIds } from './storageService';

const PAGE_SIZE = 8;
const MAX_SYNTHETIC_ITEMS = 64;

export interface PortraitBatchResult {
  items: PortraitItem[];
  hasMore: boolean;
  total: number;
}

/**
 * Filter, search, and sort portrait items according to criteria.
 */
export function getFilteredPortraits(
  items: PortraitItem[],
  query?: string,
  category?: string,
  sortBy: SortOption = 'hot'
): PortraitItem[] {
  let filtered = [...items];

  // 1. Tag / Category filter
  if (category && category !== 'all') {
    filtered = filtered.filter(
      (item) => item.category === category || item.tags.some((tag) => tag.includes(category))
    );
  }

  // 2. Search query filter (matches title, creator name, bio, tags, location)
  if (query && query.trim()) {
    const q = query.trim().toLowerCase();
    filtered = filtered.filter((item) => {
      const matchTitle = item.title.toLowerCase().includes(q);
      const matchCreator = item.creator.name.toLowerCase().includes(q);
      const matchTags = item.tags.some((tag) => tag.toLowerCase().includes(q));
      const matchDesc = item.description.toLowerCase().includes(q);
      const matchLocation = item.location ? item.location.toLowerCase().includes(q) : false;
      return matchTitle || matchCreator || matchTags || matchDesc || matchLocation;
    });
  }

  // 3. Sorting mechanism
  filtered.sort((a, b) => {
    if (sortBy === 'latest') {
      const timeA = new Date(a.publishTime.replace(/-/g, '/')).getTime();
      const timeB = new Date(b.publishTime.replace(/-/g, '/')).getTime();
      return timeB - timeA;
    }
    if (sortBy === 'likes') {
      return b.likesCount - a.likesCount;
    }
    // 'hot' sorting: weighted score based on likes and favorites
    const scoreA = a.likesCount * 1.0 + a.favoritesCount * 2.0;
    const scoreB = b.likesCount * 1.0 + b.favoritesCount * 2.0;
    return scoreB - scoreA;
  });

  // Apply user like status from storage
  const likedSet = getLikedPostIds();
  return filtered.map((item) => ({
    ...item,
    isLiked: likedSet.has(item.id),
  }));
}

/**
 * Fetch a specific portrait by its ID.
 */
export function getPortraitById(id: string): PortraitItem | undefined {
  const foundInMock = MOCK_PORTRAITS.find((p) => p.id === id);
  if (foundInMock) {
    const likedSet = getLikedPostIds();
    return {
      ...foundInMock,
      isLiked: likedSet.has(foundInMock.id),
    };
  }

  // Check generated portraits if dynamically loaded
  const dynamicItems: PortraitItem[] = generateRandomPortraits(MAX_SYNTHETIC_ITEMS, 0);
  const foundDynamic = dynamicItems.find((p: PortraitItem) => p.id === id);
  if (foundDynamic) {
    const likedSet = getLikedPostIds();
    return {
      ...foundDynamic,
      isLiked: likedSet.has(foundDynamic.id),
    };
  }

  return undefined;
}

/**
 * Simulate paginated async API fetch with realistic network latency.
 */
export async function fetchPortraitBatch(
  criteria: FilterCriteria = {},
  networkLatencyMs: number = 300
): Promise<PortraitBatchResult> {
  const {
    query = '',
    category = 'all',
    sortBy = 'hot',
    page = 1,
    pageSize = PAGE_SIZE,
  } = criteria;

  if (networkLatencyMs > 0) {
    await new Promise((resolve) => setTimeout(resolve, networkLatencyMs));
  }

  // Build combined pool of portraits (static + synthetic) to allow deep infinite scrolling
  const fullPool = [...MOCK_PORTRAITS, ...generateRandomPortraits(MAX_SYNTHETIC_ITEMS, MOCK_PORTRAITS.length)];
  const filtered = getFilteredPortraits(fullPool, query, category, sortBy);

  const total = filtered.length;
  const startIndex = (page - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const items = filtered.slice(startIndex, endIndex);
  const hasMore = endIndex < total;

  return {
    items,
    hasMore,
    total,
  };
}
