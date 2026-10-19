/** @type {import('tailwindcss').Config} */
// ONE place for the dark theme. Pages keep using the familiar class names (bg-slate-100, text-red-700,
// bg-blue-600 ...) but those names now point at dark-friendly values defined here, so changing the
// look of the whole app means editing this file only. Semantic tokens: canvas, surface, elevated, line, accent.
const scale = (o) => o

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#0b0f1a',     // page background
        surface: '#121826',    // cards, panels
        elevated: '#1a2234',   // inputs, hovered rows, inner tiles
        line: '#26314a',       // borders
        accent: { DEFAULT: '#7c83ff', soft: '#9aa0ff' },
        cyan2: '#22d3ee',
        // Neutral scale, inverted for dark: low numbers = dark backgrounds, high numbers = light text.
        slate: scale({
          50: '#1a2234', 100: '#1f2940', 200: '#26314a', 300: '#34415f', 400: '#8a94ad',
          500: '#9aa4bd', 600: '#aab3c8', 700: '#c4cbdc', 800: '#e6e9f2', 900: '#f3f5fa',
        }),
        // Accent family. 600 is the button color (white text on it), 400/900 are readable text on dark.
        blue: scale({
          50: '#1a2047', 100: '#232b5c', 200: '#343e80', 300: '#6d74f5', 400: '#9aa0ff',
          500: '#7c83ff', 600: '#6a71f0', 700: '#5a61e0', 900: '#c7caff',
        }),
        indigo: scale({ 50: '#1d2145', 200: '#3b4290', 600: '#a5abff' }),
        purple: scale({ 50: '#231a3f', 200: '#4a3a85', 600: '#c4b5fd' }),
        red: scale({
          50: '#2a1519', 100: '#3a1a20', 200: '#5c242c', 500: '#f87171', 600: '#f87171', 700: '#fca5a5',
        }),
        amber: scale({
          50: '#2b2210', 100: '#3a2c10', 200: '#5c4515', 300: '#7a5a1a', 500: '#fbbf24',
          700: '#fcd34d', 800: '#fde68a', 900: '#fef3c7',
        }),
        green: scale({
          50: '#0f2a22', 100: '#12382c', 200: '#1b5543', 300: '#237a5e', 500: '#34d399',
          600: '#34d399', 700: '#6ee7b7', 800: '#a7f3d0',
        }),
        orange: scale({ 500: '#fb923c' }),
      },
      boxShadow: { glow: '0 0 0 1px #26314a, 0 8px 30px rgba(0,0,0,.45)' },
    },
  },
  plugins: [],
}
