/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./src/api/state/**/templates/**/*.html",
        "./src/static/js/**/*.js"
    ],
    theme: {
        extend: {
            colors: {
                primary: '#4F46E5',
                secondary: '#7C3AED',
            }
        }
    },
    plugins: [],
} 