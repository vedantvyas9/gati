/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f0f4ff',
          100: '#e0e9fe',
          200: '#c7d5fd',
          300: '#a4bbfc',
          400: '#7c9ef8',
          500: '#1e3a8a',
          600: '#1e40af',
          700: '#1e3a8a',
          800: '#1e2d5c',
          900: '#0f172a',
        }
      },
      fontFamily: {
        serif: ['Garamond', 'Georgia', 'serif'],
      }
    },
  },
  plugins: [],
}
