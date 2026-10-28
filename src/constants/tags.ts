import { CategoryTag, SortOption } from '../types/portrait';

export const DEFAULT_CATEGORIES: CategoryTag[] = [
  { id: 'all', name: '全部动态' },
  { id: 'dating', name: '恋爱脱单' },
  { id: 'moments', name: '朋友圈日常' },
  { id: 'partner', name: '同城搭子' },
  { id: 'hobby', name: '兴趣圈子' },
  { id: 'outdoor', name: '运动户外' },
  { id: 'treehole', name: '深夜树洞' },
  { id: 'pet', name: '萌宠生活' },
];

export const CATEGORY_TAG_MAP: Record<string, string[]> = {
  all: [],
  dating: ['恋爱脱单', '实名认证', '心动卡片', '同频共振', '985名企交友'],
  moments: ['朋友圈日常', '生活碎碎念', '今日份美好', '美食探店', '周末小确幸'],
  partner: ['同城搭子', '羽毛球搭子', '咖啡探店', '看展搭子', '线下约会'],
  hobby: ['兴趣圈子', '摄影交流', '深度阅读', '独立音乐', '电影同好'],
  outdoor: ['运动户外', '周末徒步', '骑行漫游', '露营自驾', '飞盘俱乐部'],
  treehole: ['深夜树洞', '情绪共鸣', '治愈时刻', '告别焦虑', '真实自我'],
  pet: ['萌宠生活', '吸猫日常', '汪星人', '养宠经验', '治愈系毛孩子'],
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
