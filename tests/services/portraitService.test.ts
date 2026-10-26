import { describe, it, expect, beforeEach } from 'vitest';
import {
  getFilteredPortraits,
  getPortraitById,
  fetchPortraitBatch,
} from '../../src/services/portraitService';
import { MOCK_PORTRAITS } from '../../src/data/mockPortraits';

describe('portraitService', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('getFilteredPortraits', () => {
    it('returns all portraits when category is "all" and no search query', () => {
      const result = getFilteredPortraits(MOCK_PORTRAITS, '', 'all');
      expect(result.length).toBe(MOCK_PORTRAITS.length);
    });

    it('filters portraits by category correctly', () => {
      const vintageResult = getFilteredPortraits(MOCK_PORTRAITS, '', 'vintage');
      expect(vintageResult.length).toBeGreaterThan(0);
      vintageResult.forEach((item) => {
        const matchesCategory = item.category === 'vintage';
        const matchesTags = item.tags.some((t) => t.includes('vintage') || t.includes('复古'));
        expect(matchesCategory || matchesTags).toBe(true);
      });
    });

    it('filters portraits by title keyword', () => {
      const result = getFilteredPortraits(MOCK_PORTRAITS, '梧桐');
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].title).toContain('梧桐');
    });

    it('filters portraits by creator name keyword', () => {
      const result = getFilteredPortraits(MOCK_PORTRAITS, '九月阿肆');
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].creator.name).toBe('九月阿肆');
    });

    it('filters portraits by tags', () => {
      const result = getFilteredPortraits(MOCK_PORTRAITS, 'OOTD');
      expect(result.length).toBeGreaterThan(0);
      expect(result.some((item) => item.tags.includes('OOTD'))).toBe(true);
    });

    it('sorts portraits by "likes" descending', () => {
      const result = getFilteredPortraits(MOCK_PORTRAITS, '', 'all', 'likes');
      for (let i = 0; i < result.length - 1; i++) {
        expect(result[i].likesCount).toBeGreaterThanOrEqual(result[i + 1].likesCount);
      }
    });

    it('sorts portraits by "latest" publish time descending', () => {
      const result = getFilteredPortraits(MOCK_PORTRAITS, '', 'all', 'latest');
      for (let i = 0; i < result.length - 1; i++) {
        const timeA = new Date(result[i].publishTime.replace(/-/g, '/')).getTime();
        const timeB = new Date(result[i + 1].publishTime.replace(/-/g, '/')).getTime();
        expect(timeA).toBeGreaterThanOrEqual(timeB);
      }
    });
  });

  describe('getPortraitById', () => {
    it('returns the portrait if it exists in MOCK_PORTRAITS', () => {
      const target = MOCK_PORTRAITS[0];
      const found = getPortraitById(target.id);
      expect(found).toBeDefined();
      expect(found?.id).toBe(target.id);
      expect(found?.title).toBe(target.title);
    });

    it('returns undefined if portrait does not exist', () => {
      const notFound = getPortraitById('non-existent-id-xyz');
      expect(notFound).toBeUndefined();
    });
  });

  describe('fetchPortraitBatch', () => {
    it('returns paginated batch results with hasMore and total', async () => {
      const result = await fetchPortraitBatch(
        { category: 'all', page: 1, pageSize: 4 },
        0
      );
      expect(result.items.length).toBe(4);
      expect(result.hasMore).toBe(true);
      expect(result.total).toBeGreaterThan(4);
    });

    it('handles out-of-range pages gracefully', async () => {
      const result = await fetchPortraitBatch(
        { category: 'all', page: 999, pageSize: 20 },
        0
      );
      expect(result.items.length).toBe(0);
      expect(result.hasMore).toBe(false);
    });
  });
});
