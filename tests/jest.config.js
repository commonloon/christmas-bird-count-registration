// Jest configuration for CBC Registration tests
// Updated by Claude AI on 2025-10-10

module.exports = {
  testEnvironment: 'node',

  // Use v8 coverage provider which tracks all executed code
  coverageProvider: 'v8',

  // Collect coverage from symlinked validation.js
  collectCoverageFrom: [
    'validation.js'
  ],

  coverageDirectory: './coverage',

  coverageReporters: [
    'html',
    'text',
    'text-summary',
    'lcov'
  ],

  verbose: true,

  testMatch: ['**/email_validation.test.js']
};
