import { defineConfig } from 'vitest/config'

// The tests load index.html into their own JSDOM (tests/load-app.js), so the runner stays in the node environment.
export default defineConfig({
  test: {
    include: ['tests/**/*.test.js'],
  },
})
