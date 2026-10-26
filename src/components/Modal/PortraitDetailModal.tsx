import React, { useEffect, useState } from 'react';
import {
  X,
  Heart,
  Bookmark,
  Share2,
  MapPin,
  Calendar,
  MessageCircle,
  UserPlus,
  Check,
} from 'lucide-react';
import { PortraitItem } from '../../types/portrait';
import { formatCount } from '../Waterfall/PortraitCard';

export interface PortraitDetailModalProps {
  portrait: PortraitItem | null;
  isOpen: boolean;
  onClose: () => void;
  isLiked: boolean;
  likesCount: number;
  isBouncing?: boolean;
  onLikeToggle: () => void;
}

export const PortraitDetailModal: React.FC<PortraitDetailModalProps> = ({
  portrait,
  isOpen,
  onClose,
  isLiked,
  likesCount,
  isBouncing = false,
  onLikeToggle,
}) => {
  const [isFavorited, setIsFavorited] = useState<boolean>(false);
  const [isFollowed, setIsFollowed] = useState<boolean>(false);
  const [favoritesDelta, setFavoritesDelta] = useState<number>(0);
  const [commentInput, setCommentInput] = useState<string>('');
  const [comments, setComments] = useState<
    Array<{ id: string; author: string; avatar: string; text: string; time: string }>
  >([
    {
      id: 'c-1',
      author: '胶片爱好者小陈',
      avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=100&q=80',
      text: '色调太赞了！请问用的什么机身和镜头？光圈开多大？',
      time: '2小时前',
    },
    {
      id: 'c-2',
      author: '爱喝拿铁的猫',
      avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=100&q=80',
      text: '构图很有故事感，模特情绪抓得特别自然绝了！已赞收藏！',
      time: '4小时前',
    },
  ]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // Handle Esc key to close
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  // Sync creator follow and favorites state when portrait changes
  useEffect(() => {
    if (portrait) {
      setIsFollowed(!!portrait.creator.isFollowed);
      setIsFavorited(false);
      setFavoritesDelta(0);
    }
  }, [portrait]);

  if (!isOpen || !portrait) {
    return null;
  }

  const handleFavoriteToggle = () => {
    setIsFavorited((prev) => {
      const next = !prev;
      setFavoritesDelta((delta) => (next ? delta + 1 : delta - 1));
      return next;
    });
  };

  const handleAddComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentInput.trim()) return;

    setComments((prev) => [
      ...prev,
      {
        id: `c-dyn-${Date.now()}`,
        author: '当前用户',
        avatar: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=100&q=80',
        text: commentInput.trim(),
        time: '刚刚',
      },
    ]);
    setCommentInput('');
  };

  const currentFavoritesCount = Math.max(0, portrait.favoritesCount + favoritesDelta);

  return (
    <div
      data-testid="portrait-detail-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-0 md:p-6 bg-black/75 backdrop-blur-sm animate-fadeIn"
      onClick={onClose}
    >
      {/* Modal Container */}
      <div
        className="relative w-full max-w-5xl h-full md:h-[90vh] bg-white rounded-none md:rounded-3xl shadow-2xl overflow-hidden flex flex-col md:flex-row"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button Top Right for Mobile and Desktop */}
        <button
          type="button"
          data-testid="modal-close-button"
          onClick={onClose}
          className="absolute top-4 right-4 z-20 w-9 h-9 rounded-full bg-black/40 hover:bg-black/60 md:bg-gray-100 md:hover:bg-gray-200 text-white md:text-gray-700 flex items-center justify-center backdrop-blur-sm transition-all"
          aria-label="关闭详情浮层"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Left Side: High-Res Photo View */}
        <div className="w-full md:w-3/5 h-1/2 md:h-full bg-black flex items-center justify-center relative select-none">
          <img
            src={portrait.imageUrl}
            alt={portrait.title}
            className="w-full h-full object-contain max-h-full"
          />
        </div>

        {/* Right Side: Creator Notes & Engagement Bar */}
        <div className="w-full md:w-2/5 h-1/2 md:h-full flex flex-col bg-white">
          {/* Header: Author Profile */}
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img
                src={portrait.creator.avatar}
                alt={portrait.creator.name}
                className="w-10 h-10 rounded-full object-cover border border-gray-200"
              />
              <div className="flex flex-col">
                <span className="font-semibold text-gray-900 text-sm">
                  {portrait.creator.name}
                </span>
                <span className="text-[11px] text-gray-400">
                  {portrait.creator.bio || '生活摄影家'}
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setIsFollowed(!isFollowed)}
              className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all flex items-center gap-1 ${
                isFollowed
                  ? 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  : 'bg-red-brand text-white hover:bg-red-hover shadow-sm'
              }`}
            >
              {isFollowed ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>已关注</span>
                </>
              ) : (
                <>
                  <UserPlus className="w-3.5 h-3.5" />
                  <span>关注</span>
                </>
              )}
            </button>
          </div>

          {/* Scrollable Center: Caption, Tags, Comments */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 text-sm text-gray-700">
            {/* Title & Description */}
            <div>
              <h1 className="text-base font-bold text-gray-900 mb-2 leading-snug">
                {portrait.title}
              </h1>
              <p className="text-gray-600 leading-relaxed whitespace-pre-line text-[13px]">
                {portrait.description}
              </p>
            </div>

            {/* Tags */}
            <div className="flex flex-wrap gap-1.5 pt-1">
              {portrait.tags.map((tag, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-full bg-red-light text-red-brand text-xs font-medium"
                >
                  #{tag}
                </span>
              ))}
            </div>

            {/* Meta: Location and Time */}
            <div className="flex items-center gap-4 text-xs text-gray-400 pt-2 border-t border-gray-50">
              {portrait.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-gray-400" />
                  {portrait.location}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-gray-400" />
                {portrait.publishTime}
              </span>
            </div>

            {/* Comments Section */}
            <div className="pt-4 border-t border-gray-100 space-y-3">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-gray-800">
                <MessageCircle className="w-4 h-4 text-gray-500" />
                <span>精选评论 ({comments.length})</span>
              </div>

              <div className="space-y-3">
                {comments.map((comment) => (
                  <div key={comment.id} className="flex gap-2.5 items-start text-xs">
                    <img
                      src={comment.avatar}
                      alt={comment.author}
                      className="w-6 h-6 rounded-full object-cover flex-shrink-0 mt-0.5"
                    />
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-700">{comment.author}</span>
                        <span className="text-[10px] text-gray-400">{comment.time}</span>
                      </div>
                      <p className="text-gray-600 mt-0.5 leading-normal">{comment.text}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom Action Footer */}
          <div className="p-3 border-t border-gray-100 bg-gray-50/50 flex flex-col gap-2">
            {/* Quick Comment Input */}
            <form onSubmit={handleAddComment} className="flex items-center gap-2">
              <input
                type="text"
                value={commentInput}
                onChange={(e) => setCommentInput(e.target.value)}
                placeholder="说点什么吧..."
                className="flex-1 bg-white border border-gray-200 rounded-full px-3.5 py-1.5 text-xs text-gray-800 focus:outline-none focus:border-red-brand"
              />
              <button
                type="submit"
                disabled={!commentInput.trim()}
                className="px-3 py-1.5 rounded-full bg-red-brand disabled:bg-gray-200 text-white text-xs font-medium transition-colors"
              >
                发送
              </button>
            </form>

            {/* Action Buttons: Like, Favorite, Share */}
            <div className="flex items-center justify-around pt-1">
              {/* Like Button */}
              <button
                type="button"
                data-testid="modal-like-button"
                onClick={onLikeToggle}
                className="flex items-center gap-1.5 text-gray-600 hover:text-red-brand px-2 py-1 rounded-md transition-all active:scale-95"
              >
                <Heart
                  className={`w-5 h-5 transition-transform ${
                    isLiked
                      ? 'fill-red-brand text-red-brand'
                      : 'text-gray-500'
                  } ${isBouncing ? 'animate-likeBounce' : ''}`}
                />
                <span
                  className={`text-xs font-medium ${
                    isLiked ? 'text-red-brand font-bold' : ''
                  }`}
                >
                  {formatCount(likesCount)}
                </span>
              </button>

              {/* Favorite Button */}
              <button
                type="button"
                onClick={handleFavoriteToggle}
                className="flex items-center gap-1.5 text-gray-600 hover:text-amber-500 px-2 py-1 rounded-md transition-all active:scale-95"
              >
                <Bookmark
                  className={`w-5 h-5 ${
                    isFavorited
                      ? 'fill-amber-400 text-amber-500'
                      : 'text-gray-500'
                  }`}
                />
                <span
                  className={`text-xs font-medium ${
                    isFavorited ? 'text-amber-500 font-bold' : ''
                  }`}
                >
                  {formatCount(currentFavoritesCount)}
                </span>
              </button>

              {/* Share Button */}
              <button
                type="button"
                onClick={() => {
                  if (navigator.clipboard) {
                    navigator.clipboard.writeText(window.location.href);
                    alert('作品链接已复制到剪贴板！');
                  }
                }}
                className="flex items-center gap-1.5 text-gray-600 hover:text-gray-900 px-2 py-1 rounded-md transition-all"
              >
                <Share2 className="w-5 h-5 text-gray-500" />
                <span className="text-xs font-medium">分享</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
