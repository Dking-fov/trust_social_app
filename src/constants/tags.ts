import { CategoryTag, SortOption } from '../types/portrait';

export const DEFAULT_CATEGORIES: CategoryTag[] = [
  { id: 'all', name: '全部' },
  { id: 'street', name: '街拍穿搭' },
  { id: 'vintage', name: '复古写真' },
  { id: 'mood', name: '情绪人像' },
  { id: 'celebrity', name: '艺人神颜' },
  { id: 'film', name: '日系胶片' },
  { id: 'cyberpunk', name: '赛博夜景' },
  { id: 'fresh', name: '清新人像' },
  { id: 'light-shadow', name: '光影人像' },
];

export const CATEGORY_TAG_MAP: Record<string, string[]> = {
  all: [],
  street: ['街拍穿搭', 'OOTD', '秋季穿搭', '日常出街', '高级感'],
  vintage: ['复古写真', '港风', '90年代', '法式复古', '复古妆容'],
  mood: ['情绪人像', '黑白人像', '眼神光', '微表情', '故事感'],
  celebrity: ['艺人神颜', '红毯造型', '高清生图', '封面大片', '视觉盛宴'],
  film: ['日系胶片', '胶片感', '富士色彩', '宝丽来', '颗粒感'],
  cyberpunk: ['赛博夜景', '霓虹光影', '未来主义', '夜幕人像', '冷暖撞色'],
  fresh: ['清新人像', '氧气少女', '户外草坪', '自然光', '元气微笑'],
  'light-shadow': ['光影人像', '丁达尔光', '逆光美学', '阴影构图', '室内窗边'],
};

export interface SortOptionItem {
  id: SortOption;
  label: string;
}

export const SORT_OPTIONS: SortOptionItem[] = [
  { id: 'hot', label: '最热推荐' },
  { id: 'latest', label: '最新发布' },
  { id: 'likes', label: '点赞最多' },
];
