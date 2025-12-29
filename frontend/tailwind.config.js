/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        profit: {
          high: '#10b981',
          medium: '#f59e0b',
          low: '#6b7280',
        }
      },
      animation: {
        'pulse-fast': 'pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'flash': 'flash 0.5s ease-in-out',
      },
      keyframes: {
        flash: {
          '0%, 100%': { backgroundColor: 'transparent' },
          '50%': { backgroundColor: 'rgba(16, 185, 129, 0.2)' },
        }
      }
    },
  },
  plugins: [],
}
