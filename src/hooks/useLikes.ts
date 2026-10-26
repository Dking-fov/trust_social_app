import { useState, useEffect, useCallback } from 'react';
import {
  getLikedPostIds,
  togglePostLike as persistToggleLike,
  getLikesDeltaMap,
  saveLikesDeltaMap,
} from '../services/storageService';

export function useLikes() {
  const [likedSet, setLikedSet] = useState<Set<string>>(() => getLikedPostIds());
  const [likesDeltaMap, setLikesDeltaMap] = useState<Record<string, number>>(() => getLikesDeltaMap());
  const [bouncingId, setBouncingId] = useState<string | null>(null);

  // Listen to changes across components or tabs
  useEffect(() => {
    const handleLikeEvent = (e: Event) => {
      const customEvent = e as CustomEvent<{ postId: string; isLiked: boolean }>;
      if (customEvent.detail) {
        const { postId, isLiked } = customEvent.detail;
        setLikedSet((prev) => {
          const next = new Set(prev);
          if (isLiked) {
            next.add(postId);
          } else {
            next.delete(postId);
          }
          return next;
        });

        setLikesDeltaMap((prev) => {
          const updated = {
            ...prev,
            [postId]: isLiked ? 1 : 0,
          };
          saveLikesDeltaMap(updated);
          return updated;
        });
      }
    };

    window.addEventListener('red:like-changed', handleLikeEvent);
    return () => {
      window.removeEventListener('red:like-changed', handleLikeEvent);
    };
  }, []);

  const toggleLike = useCallback((postId: string) => {
    // Trigger spring bounce animation
    setBouncingId(postId);
    setTimeout(() => {
      setBouncingId((curr) => (curr === postId ? null : curr));
    }, 500);

    const isNowLiked = persistToggleLike(postId);

    setLikedSet((prev) => {
      const next = new Set(prev);
      if (isNowLiked) {
        next.add(postId);
      } else {
        next.delete(postId);
      }
      return next;
    });

    setLikesDeltaMap((prev) => {
      const updated = {
        ...prev,
        [postId]: isNowLiked ? 1 : 0,
      };
      saveLikesDeltaMap(updated);
      return updated;
    });

    return isNowLiked;
  }, []);

  const isLiked = useCallback(
    (postId: string) => {
      return likedSet.has(postId);
    },
    [likedSet]
  );

  const getAdjustedLikesCount = useCallback(
    (postId: string, baseLikes: number) => {
      const delta = likesDeltaMap[postId] ?? (likedSet.has(postId) ? 1 : 0);
      return Math.max(0, baseLikes + delta);
    },
    [likesDeltaMap, likedSet]
  );

  return {
    likedSet,
    toggleLike,
    isLiked,
    getAdjustedLikesCount,
    bouncingId,
  };
}
