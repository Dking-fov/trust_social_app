import React from 'react';
import { Camera, RefreshCw } from 'lucide-react';

export interface EmptyStateProps {
  title?: string;
  description?: string;
  onReset?: () => void;
  resetText?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = '未找到相关人像笔记',
  description = '换个搜索关键词，或者切换到“全部”标签看看大家都在拍什么吧',
  onReset,
  resetText = '重置筛选条件',
}) => {
  return (
    <div
      data-testid="empty-state"
      className="flex flex-col items-center justify-center py-20 px-4 text-center max-w-md mx-auto animate-fadeIn"
    >
      <div className="w-20 h-20 rounded-full bg-red-light flex items-center justify-center text-red-brand mb-4 shadow-sm">
        <Camera className="w-10 h-10 stroke-[1.5]" />
      </div>

      <h3 className="text-lg font-bold text-gray-800 mb-1.5">{title}</h3>
      <p className="text-sm text-gray-500 mb-6 leading-relaxed">{description}</p>

      {onReset && (
        <button
          type="button"
          onClick={onReset}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-red-brand text-white text-sm font-medium hover:bg-red-hover active:scale-95 transition-all shadow-sm"
        >
          <RefreshCw className="w-4 h-4" />
          <span>{resetText}</span>
        </button>
      )}
    </div>
  );
};
