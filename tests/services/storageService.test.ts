import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getLikedPostIds,
  isPostLiked,
  togglePostLike,
  getLikesDeltaMap,
  saveLikesDeltaMap,
} from '../../src/services/storageService';

describe('storageService', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('initially returns empty set when no likes stored', () => {
    const likes = getLikedPostIds();
    expect(likes.size).toBe(0);
    expect(isPostLiked('test-post-1')).toBe(false);
  });

  it('toggles post like status and persists to localStorage', () => {
    const isNowLiked = togglePostLike('post-100');
    expect(isNowLiked).toBe(true);
    expect(isPostLiked('post-100')).toBe(true);

    const storedIds = getLikedPostIds();
    expect(storedIds.has('post-100')).toBe(true);

    // Toggle again to unlike
    const isNowUnliked = togglePostLike('post-100');
    expect(isNowUnliked).toBe(false);
    expect(isPostLiked('post-100')).toBe(false);
  });

  it('dispatches custom event on like toggle', () => {
    const eventSpy = vi.fn();
    window.addEventListener('red:like-changed', eventSpy);

    togglePostLike('post-200');

    expect(eventSpy).toHaveBeenCalledTimes(1);
    const event = eventSpy.mock.calls[0][0] as CustomEvent;
    expect(event.detail).toEqual({ postId: 'post-200', isLiked: true });

    window.removeEventListener('red:like-changed', eventSpy);
  });

  it('handles corrupted localStorage JSON without crashing', () => {
    localStorage.setItem('red_portrait_liked_posts_v1', 'invalid-json{{{');
    const likes = getLikedPostIds();
    expect(likes.size).toBe(0);
  });

  it('manages likes delta map accurately', () => {
    expect(getLikesDeltaMap()).toEqual({});

    saveLikesDeltaMap({ 'post-1': 1, 'post-2': -1 });
    expect(getLikesDeltaMap()).toEqual({ 'post-1': 1, 'post-2': -1 });
  });
});
