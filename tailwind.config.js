/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        red: {
          brand: '#ff2442',
          hover: '#e01a36',
          light: '#fff0f2',
          subtle: '#ffe5e8',
        },
        surface: {
          DEFAULT: '#f7f8fa',
          card: '#ffffff',
          hover: '#f2f3f5',
        },
        text: {
          primary: '#333333',
          secondary: '#666666',
          muted: '#999999',
        }
      },
      borderRadius: {
        'xl': '12px',
        '2xl': '16px',
        '3xl': '24px',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        likeBounce: {
          '0%': { transform: 'scale(1)' },
          '30%': { transform: 'scale(1.35)' },
          '60%': { transform: 'scale(0.85)' },
          '100%': { transform: 'scale(1)' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.8s infinite linear',
        likeBounce: 'likeBounce 0.45s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
        fadeIn: 'fadeIn 0.25s ease-out forwards',
      },
    },
  },
  plugins: [],
}
