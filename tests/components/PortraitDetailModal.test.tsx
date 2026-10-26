import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PortraitDetailModal } from '../../src/components/Modal/PortraitDetailModal';
import { MOCK_PORTRAITS } from '../../src/data/mockPortraits';

describe('PortraitDetailModal component', () => {
  const mockPortrait = MOCK_PORTRAITS[0];

  it('does not render when isOpen is false', () => {
    const handleClose = vi.fn();
    const handleLike = vi.fn();

    render(
      <PortraitDetailModal
        portrait={mockPortrait}
        isOpen={false}
        onClose={handleClose}
        isLiked={false}
        likesCount={100}
        onLikeToggle={handleLike}
      />
    );

    expect(screen.queryByTestId('portrait-detail-modal')).not.toBeInTheDocument();
  });

  it('renders correctly with portrait content and locks body scroll', () => {
    const handleClose = vi.fn();
    const handleLike = vi.fn();

    render(
      <PortraitDetailModal
        portrait={mockPortrait}
        isOpen={true}
        onClose={handleClose}
        isLiked={true}
        likesCount={12450}
        onLikeToggle={handleLike}
      />
    );

    expect(screen.getByTestId('portrait-detail-modal')).toBeInTheDocument();
    expect(screen.getByText(mockPortrait.title)).toBeInTheDocument();
    expect(screen.getByText(mockPortrait.creator.name)).toBeInTheDocument();
    expect(document.body.style.overflow).toBe('hidden');
  });

  it('invokes onClose when clicking the close button', () => {
    const handleClose = vi.fn();
    const handleLike = vi.fn();

    render(
      <PortraitDetailModal
        portrait={mockPortrait}
        isOpen={true}
        onClose={handleClose}
        isLiked={false}
        likesCount={100}
        onLikeToggle={handleLike}
      />
    );

    const closeBtn = screen.getByTestId('modal-close-button');
    fireEvent.click(closeBtn);

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('invokes onClose when Esc key is pressed', () => {
    const handleClose = vi.fn();
    const handleLike = vi.fn();

    render(
      <PortraitDetailModal
        portrait={mockPortrait}
        isOpen={true}
        onClose={handleClose}
        isLiked={false}
        likesCount={100}
        onLikeToggle={handleLike}
      />
    );

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('triggers onLikeToggle inside the modal', () => {
    const handleClose = vi.fn();
    const handleLike = vi.fn();

    render(
      <PortraitDetailModal
        portrait={mockPortrait}
        isOpen={true}
        onClose={handleClose}
        isLiked={false}
        likesCount={100}
        onLikeToggle={handleLike}
      />
    );

    const likeBtn = screen.getByTestId('modal-like-button');
    fireEvent.click(likeBtn);

    expect(handleLike).toHaveBeenCalledTimes(1);
  });
});
