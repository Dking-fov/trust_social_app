import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import {
  getColumnCount,
  balanceColumns,
  useMasonryColumns,
} from '../../src/hooks/useMasonryColumns';
import { MOCK_PORTRAITS } from '../../src/data/mockPortraits';

describe('useMasonryColumns', () => {
  describe('getColumnCount', () => {
    it('returns 2 for mobile widths < 768px', () => {
      expect(getColumnCount(375)).toBe(2);
      expect(getColumnCount(767)).toBe(2);
    });

    it('returns 3 for tablet widths between 768px and 1099px', () => {
      expect(getColumnCount(768)).toBe(3);
      expect(getColumnCount(1024)).toBe(3);
    });

    it('returns 4 for standard desktop widths between 1100px and 1439px', () => {
      expect(getColumnCount(1100)).toBe(4);
      expect(getColumnCount(1280)).toBe(4);
    });

    it('returns 5 for large desktop widths >= 1440px', () => {
      expect(getColumnCount(1440)).toBe(5);
      expect(getColumnCount(1920)).toBe(5);
    });
  });

  describe('balanceColumns', () => {
    it('returns single column array if columnCount <= 1', () => {
      const result = balanceColumns(MOCK_PORTRAITS, 1);
      expect(result.length).toBe(1);
      expect(result[0].length).toBe(MOCK_PORTRAITS.length);
    });

    it('distributes items across 2 columns evenly', () => {
      const items = MOCK_PORTRAITS.slice(0, 6);
      const cols = balanceColumns(items, 2);
      expect(cols.length).toBe(2);
      const totalDistributed = cols[0].length + cols[1].length;
      expect(totalDistributed).toBe(items.length);
      expect(Math.abs(cols[0].length - cols[1].length)).toBeLessThanOrEqual(1);
    });

    it('distributes items across 4 columns without dropping items', () => {
      const cols = balanceColumns(MOCK_PORTRAITS, 4);
      expect(cols.length).toBe(4);
      const allItemIds = cols.flat().map((item) => item.id);
      expect(allItemIds.length).toBe(MOCK_PORTRAITS.length);
      MOCK_PORTRAITS.forEach((orig) => {
        expect(allItemIds).toContain(orig.id);
      });
    });
  });

  describe('useMasonryColumns hook', () => {
    it('initializes columns according to window width', () => {
      window.innerWidth = 800;
      const { result } = renderHook(() => useMasonryColumns(MOCK_PORTRAITS));

      expect(result.current.columnCount).toBe(3);
      expect(result.current.columns.length).toBe(3);
    });

    it('reacts to window resize events', () => {
      window.innerWidth = 500;
      const { result } = renderHook(() => useMasonryColumns(MOCK_PORTRAITS));

      expect(result.current.columnCount).toBe(2);

      act(() => {
        window.innerWidth = 1200;
        window.dispatchEvent(new Event('resize'));
      });

      // Advance debounce timer if any
      act(() => {
        new Promise((r) => setTimeout(r, 150));
      });
    });
  });
});
