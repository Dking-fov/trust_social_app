# xiaohongshu-portrait-feed - 系统架构设计规格书

## 技术栈选型
- **build_tool**: Vite 5
- **framework**: React 18 / TypeScript
- **icons**: Lucide React
- **language**: TypeScript 5
- **state_and_storage**: React Hooks + Browser LocalStorage
- **styling**: Tailwind CSS 3
- **testing**: Vitest + React Testing Library + jsdom

## 第三方依赖清单
- react@^18.3.1
- react-dom@^18.3.1
- lucide-react@^0.453.0
- clsx@^2.1.1
- tailwind-merge@^2.5.4
- vite@^5.4.9
- typescript@^5.6.3
- @types/react@^18.3.11
- @types/react-dom@^18.3.1
- tailwindcss@^3.4.14
- postcss@^8.4.47
- autoprefixer@^10.4.20
- vitest@^2.1.3
- @testing-library/react@^16.0.1
- @testing-library/jest-dom@^6.6.2
- jsdom@^25.0.1

## 规划文件树结构 ({len(state.architecture.file_tree)} 个模块)
- `package.json`: Project manifest declaring dependencies, scripts (dev, build, test), and project metadata (Symbols: package.json)
- `tsconfig.json`: TypeScript compiler configuration with strict typing, JSX settings, and path aliases (Symbols: tsconfig.json)
- `vite.config.ts`: Vite build configuration including React plugin and test runner setup (Symbols: vite.config.ts)
- `tailwind.config.js`: Tailwind CSS design token configuration (Xiaohongshu red colors, border radiuses, animations) (Symbols: tailwind.config.js)
- `postcss.config.js`: PostCSS configuration for Tailwind and Autoprefixer (Symbols: postcss.config.js)
- `index.html`: HTML entry point with viewport meta, font links, and root mount node (Symbols: index.html)
- `src/types/portrait.ts`: TypeScript interface and type definitions for portraits, authors, categories, tags, and states (Symbols: PortraitItem, Creator, CategoryTag, SortOption, FilterCriteria, UserLikeRecord)
- `src/constants/tags.ts`: Constant definitions for photography category tabs, tags, and sort dropdown options (Symbols: DEFAULT_CATEGORIES, CATEGORY_TAG_MAP, SORT_OPTIONS)
- `src/data/mockPortraits.ts`: Curated high-resolution trending portrait mock dataset with diverse aspect ratios, creators, and tags (Symbols: MOCK_PORTRAITS, generateRandomPortraits)
- `src/services/portraitService.ts`: Service layer handling search, tag filtering, sorting, and paginated loading of portraits (Symbols: getFilteredPortraits, getPortraitById, fetchPortraitBatch)
- `src/services/storageService.ts`: LocalStorage persistence service for tracking liked posts and custom favorites (Symbols: getLikedPostIds, togglePostLike, isPostLiked)
- `src/hooks/usePortraits.ts`: Custom hook managing feed state, search queries, active tags, sorting, and infinite scroll batching (Symbols: usePortraits)
- `src/hooks/useLikes.ts`: Custom hook for optimistic like toggle, animated bounce state, and storage synchronization (Symbols: useLikes)
- `src/hooks/useMasonryColumns.ts`: Custom hook calculating responsive column counts and balancing items across columns by height (Symbols: useMasonryColumns)
- `src/components/Common/ImageWithFallback.tsx`: Resilient image component with skeleton shimmer, lazy loading, aspect ratio box, and error fallback (Symbols: ImageWithFallback)
- `src/components/Common/EmptyState.tsx`: Friendly empty state view when search or filter returns no matching portrait notes (Symbols: EmptyState)
- `src/components/Common/InfiniteScrollTrigger.tsx`: Bottom sentinel component utilizing IntersectionObserver to trigger loading the next page of cards (Symbols: InfiniteScrollTrigger)
- `src/components/Header/Navbar.tsx`: Top header bar containing RED logo, search input bar, and hot/latest sort dropdown selector (Symbols: Navbar)
- `src/components/Filter/TagFilterBar.tsx`: Horizontally scrollable trending category filter bar with Xiaohongshu red pill active highlights (Symbols: TagFilterBar)
- `src/components/Waterfall/PortraitCard.tsx`: Masonry card component with portrait cover, aspect-ratio placeholder, title, author info, and like button (Symbols: PortraitCard)
- `src/components/Waterfall/CardSkeleton.tsx`: Shimmering placeholder card shown while portraits are loading (Symbols: CardSkeleton)
- `src/components/Waterfall/WaterfallGrid.tsx`: Responsive masonry grid container rendering multi-column unbalanced portrait flow (Symbols: WaterfallGrid)
- `src/components/Modal/PortraitDetailModal.tsx`: Full-screen/split lightbox modal showing high-res photo, author notes, tags, like action, and body scroll lock (Symbols: PortraitDetailModal)
- `src/App.tsx`: Root application component integrating Navbar, TagFilterBar, WaterfallGrid, DetailModal, and status toast (Symbols: App)
- `src/main.tsx`: React application entrypoint rendering App into the DOM root with global styles (Symbols: main)
- `tests/services/portraitService.test.ts`: Unit tests for portrait querying, searching, filtering, and sorting algorithms (Symbols: describe, test, expect)
- `tests/services/storageService.test.ts`: Unit tests for LocalStorage like persistence and fault tolerance (Symbols: describe, test, expect)
- `tests/hooks/useMasonryColumns.test.ts`: Unit tests for responsive column split and height balancing logic (Symbols: describe, test, expect)
- `tests/hooks/useLikes.test.ts`: Unit tests for like toggle, count increment/decrement, and optimistic updates (Symbols: describe, test, expect)
- `tests/components/PortraitCard.test.tsx`: Component tests for card rendering, like interaction, and image error fallback (Symbols: describe, test, expect)
- `tests/components/PortraitDetailModal.test.tsx`: Component tests for modal visibility, keyboard Esc dismiss, and scroll lock (Symbols: describe, test, expect)

## 设计原则
Architectural Design Principles, Modularity & Integration Strategy:

1. System Decomposition & Single Responsibility Principle (SRP):
   - The application is decoupled into clean, distinct layers:
     * Data & Domain Layer (`src/types`, `src/data`, `src/services`): Handles data structures, mock data feeds, filtering, sorting, pagination, and LocalStorage persistence.
     * State Management & Hook Layer (`src/hooks`): Provides isolated business logic hooks (`usePortraits`, `useLikes`, `useMasonryColumns`) that can be tested independently of UI rendering.
     * Presentation Component Layer (`src/components`): Organized into modular domains (`Header`, `Filter`, `Waterfall`, `Modal`, `Common`).

2. Responsive Masonry (Waterfall) Layout Engine:
   - Dynamic Multi-Column Distribution: Rather than relying solely on pure CSS columns (which render top-to-bottom and break ordering across columns), `useMasonryColumns` dynamically splits posts into 2 columns (<768px), 3 columns (768px-1200px), or 4-5 columns (>1200px).
   - CLS Prevention (CLS < 0.1): Card aspect ratios are tracked and predefined; `ImageWithFallback` reserves container height with aspect-ratio CSS and renders skeleton shimmer placeholders until image load finishes.

3. Performance & 60fps Scrolling:
   - Native `loading="lazy"` and `IntersectionObserver` sentinel triggers for infinite scroll batches.
   - Debounced search queries and throttled scroll triggers prevent excessive state re-computations.
   - Optimistic updates for engagement interactions (like/favorite) update the UI instantaneously, syncing to LocalStorage in the background.

4. Interactive Detail Lightbox & Modal Experience:
   - Full-bleed or split-pane modal view on desktop and drawer-style sheet on mobile.
   - Body scroll locking (`overflow: hidden`) during modal mount prevents background disorientations.
   - Accessible dismissal via Esc key, backdrop click, or dedicated close button.

5. Visual Aesthetics (Xiaohongshu RED Style):
   - Background: Soft warm grey/white (`#f7f8fa`).
   - Cards: `bg-white`, `rounded-2xl`, subtle shadow (`shadow-sm hover:shadow-md`).
   - Signature Red: Accent red `#ff2442` for active filter badges, like hearts, and primary CTAs.
   - Spring micro-animations: CSS scale/bounce keyframes for heart tap feedback.