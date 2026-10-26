/**
 * LocalStorage persistence service for tracking liked posts and custom user engagements.
 */

const LIKED_POSTS_STORAGE_KEY = 'red_portrait_liked_posts_v1';
const LIKES_DELTA_STORAGE_KEY = 'red_portrait_likes_deltas_v1';

/**
 * Safely access localStorage with fallback to in-memory set when storage is blocked.
 */
class MemoryStorageFallback {
  private store = new Map<string, string>();

  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }
}

const memoryStorage = new MemoryStorageFallback();

function getStorage(): Storage | MemoryStorageFallback {
  if (typeof window === 'undefined') {
    return memoryStorage;
  }
  try {
    const testKey = '__storage_test__';
    window.localStorage.setItem(testKey, testKey);
    window.localStorage.removeItem(testKey);
    return window.localStorage;
  } catch {
    return memoryStorage;
  }
}

/**
 * Retrieve the set of liked post IDs from storage.
 */
export function getLikedPostIds(): Set<string> {
  const storage = getStorage();
  try {
    const raw = storage.getItem(LIKED_POSTS_STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return new Set(parsed);
    }
    return new Set();
  } catch (error) {
    console.warn('[storageService] Failed to read liked posts:', error);
    return new Set();
  }
}

/**
 * Check whether a specific post is liked by the user.
 */
export function isPostLiked(postId: string): boolean {
  return getLikedPostIds().has(postId);
}

/**
 * Toggle the like status of a post.
 * Returns the new liked state (true if now liked, false if unliked).
 */
export function togglePostLike(postId: string): boolean {
  const storage = getStorage();
  const likedSet = getLikedPostIds();
  const willBeLiked = !likedSet.has(postId);

  if (willBeLiked) {
    likedSet.add(postId);
  } else {
    likedSet.delete(postId);
  }

  try {
    storage.setItem(LIKED_POSTS_STORAGE_KEY, JSON.stringify(Array.from(likedSet)));
    
    // Dispatch a custom storage event so other components or tabs update in real time
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('red:like-changed', {
          detail: { postId, isLiked: willBeLiked },
        })
      );
    }
  } catch (error) {
    console.warn('[storageService] Failed to persist like status:', error);
  }

  return willBeLiked;
}

/**
 * Get the delta count (e.g. +1 or -1 or 0) for likes performed by the current session.
 */
export function getLikesDeltaMap(): Record<string, number> {
  const storage = getStorage();
  try {
    const raw = storage.getItem(LIKES_DELTA_STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

/**
 * Save updated delta map for like counts.
 */
export function saveLikesDeltaMap(map: Record<string, number>): void {
  const storage = getStorage();
  try {
    storage.setItem(LIKES_DELTA_STORAGE_KEY, JSON.stringify(map));
  } catch (error) {
    console.warn('[storageService] Failed to save likes delta map:', error);
  }
}
