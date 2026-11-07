/** Mirrors the palette the original app declared inline against the Tailwind CDN. */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        sand: {
          50: '#FDFCF9',
          100: '#F5F2EB',
          200: '#E8E3DA',
          300: '#CFC7B8',
          400: '#9A927F',
          500: '#6B6560',
          600: '#2C2825',
        },
        neutral: {
          750: '#2C2C2C',
          850: '#1A1A1A',
          925: '#0F0F0F',
        },
      },
      keyframes: {
        'fade-in-slide': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in-slide': 'fade-in-slide 0.45s cubic-bezier(0.16, 1, 0.3, 1) forwards',
      },
    },
  },
  plugins: [],
};
