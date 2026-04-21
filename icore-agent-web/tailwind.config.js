/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        cream: '#f0ede8',
      },
      fontFamily: {
        sans: ['"Inter"', '"PingFang SC"', '"Helvetica Neue"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
