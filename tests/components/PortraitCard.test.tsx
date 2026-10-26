import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PortraitCard, formatCount } from '../../src/components/Waterfall/PortraitCard';
import { MOCK_PORTRAITS } from '../../src/data/mockPortraits';

describe('PortraitCard component', () => {
  const mockPortrait = MOCK_PORTRAITS[0];

  it('formats counts properly', () => {
    expect(formatCount(950)).toBe('950');
    expect(formatCount(1200)).toBe('1.2k');
    expect(formatCount(25000)).toBe('2.5万');
  });

  it('renders portrait card with title, creator info, and like count', () => {
    const handleLike = vi.fn();
    const handleCardClick = vi.fn();

    render(
      <PortraitCard
        portrait={mockPortrait}
        isLiked={false}
        likesCount={12450}
        onLikeToggle={handleLike}
        onClick={handleCardClick}
      />
    );

    expect(screen.getByText(mockPortrait.title)).toBeInTheDocument();
    expect(screen.getByText(mockPortrait.creator.name)).toBeInTheDocument();
    expect(screen.getByText('1.2万')).toBeInTheDocument();
  });

  it('triggers onLikeToggle when like button is clicked', () => {
    const handleLike = vi.fn();
    const handleCardClick = vi.fn();

    render(
      <PortraitCard
        portrait={mockPortrait}
        isLiked={false}
        likesCount={100}
        onLikeToggle={handleLike}
        onClick={handleCardClick}
      />
    );

    const likeBtn = screen.getByTestId(`like-btn-${mockPortrait.id}`);
    fireEvent.click(likeBtn);

    expect(handleLike).toHaveBeenCalledTimes(1);
    expect(handleCardClick).not.toHaveBeenCalled();
  });

  it('triggers onClick when article card is clicked', () => {
    const handleLike = vi.fn();
    const handleCardClick = vi.fn();

    render(
      <PortraitCard
        portrait={mockPortrait}
        isLiked={false}
        likesCount={100}
        onLikeToggle={handleLike}
        onClick={handleCardClick}
      />
    );

    const card = screen.getByTestId(`portrait-card-${mockPortrait.id}`);
    fireEvent.click(card);

    expect(handleCardClick).toHaveBeenCalledTimes(1);
  });
});
