/**
 * Types and interfaces for the Xiaohongshu Portrait Feed application.
 */

export interface Creator {
  id: string;
  name: string;
  avatar: string;
  bio?: string;
  isFollowed?: boolean;
}

export interface CategoryTag {
  id: string;
  name: string;
  description?: string;
  icon?: string;
}

export type SortOption = 'hot' | 'latest' | 'likes';

export interface PortraitItem {
  id: string;
  title: string;
  description: string;
  imageUrl: string;
  thumbnailUrl?: string;
  width: number;
  height: number;
  aspectRatio: number; // width / height, e.g. 0.75 for 3:4 portrait
  creator: Creator;
  likesCount: number;
  favoritesCount: number;
  isLiked?: boolean;
  isFavorited?: boolean;
  tags: string[];
  category: string;
  publishTime: string;
  location?: string;
}

export interface FilterCriteria {
  query?: string;
  category?: string;
  sortBy?: SortOption;
  page?: number;
  pageSize?: number;
}

export interface UserLikeRecord {
  postId: string;
  likedAt: number;
}
