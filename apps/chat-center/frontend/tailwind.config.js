/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // AgentIQ Theme Colors (from memory)
        'bg-primary': '#0a1018',
        'bg-secondary': '#141e2b',
        'accent': '#e8a838',
        'error': '#e85454',
        'success': '#4ecb71',
        'info': '#7db8e8',
      },
      fontFamily: {
        sans: ['Montserrat', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
