import js from '@eslint/js'
import eslintConfigPrettier from 'eslint-config-prettier'
import globals from 'globals'

export default [
  { ignores: ['**/node_modules/**', '**/dist/**'] },
  js.configs.recommended,
  eslintConfigPrettier,
  {
    files: ['src/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      'max-len': ['error', { code: 80 }],
      'no-unused-vars': 'warn',
      'no-var': 'error',
      'no-duplicate-imports': 'error',
      'no-unreachable': 'error',
      'no-case-declarations': 'off',
      'no-useless-catch': 'off',
    },
  },
]
