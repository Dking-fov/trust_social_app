import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLikes } from '../../src/hooks/useLikes';

describe('useLikes hook', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('starts with no liked items', () => {
    const { result } = renderHook(() => useLikes());
    expect(result.current.isLiked('post-test')).toBe(false);
    expect(result.current.getAdjustedLikesCount('post-test', 100)).toBe(100);
  });

  it('toggles like and updates counts optimistically', () => {
    const { result } = renderHook(() => useLikes());

    act(() => {
      result.current.toggleLike('post-test');
    });

    expect(result.current.isLiked('post-test')).toBe(true);
    expect(result.current.getAdjustedLikesCount('post-test', 100)).toBe(101);
    expect(result.current.bouncingId).toBe('post-test');

    // Toggle again to unlike
    act(() => {
      result.current.toggleLike('post-test');
    });

    expect(result.current.isLiked('post-test')).toBe(false);
    expect(result.current.getAdjustedLikesCount('post-test', 100)).toBe(100);
  });

  it('responds to external custom like events', () => {
    const { result } = renderHook(() => useLikes());

    act(() => {
      window.dispatchEvent(
        new CustomEvent('red:like-changed', {
          detail: { postId: 'post-external', isLiked: true },
        })
      );
    });

    expect(result.current.isLiked('post-external')).toBe(true);
    expect(result.current.getAdjustedLikesCount('post-external', 50)).toBe(51);
  });
});
