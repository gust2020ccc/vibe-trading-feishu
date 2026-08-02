/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0a0e1a',
        surface: '#111827',
        surface2: '#1a2234',
        surface3: '#242e44',
        border: '#2a3548',
        accent: { DEFAULT: '#6366f1', light: '#818cf8' },
      },
      fontFamily: {
        sans: ['-apple-system', 'SF Pro Display', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease',
        'slide-in': 'slideIn 0.3s ease',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideIn: { '0%': { transform: 'translateX(100%)', opacity: '0' }, '100%': { transform: 'translateX(0)', opacity: '1' } },
      },
    },
  },
  plugins: [],
}
