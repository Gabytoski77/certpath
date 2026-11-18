// ESLint for the app's JavaScript (inline scripts copied out by build/extract_scripts.py, plus sw.js).
// Only rules that catch real bugs; style is not checked.
import globals from "globals";

export default [
  {
    files: ["**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: { ...globals.browser, ...globals.serviceworker, THREE: "readonly", Lenis: "readonly", echarts: "readonly" },
    },
    linterOptions: { reportUnusedDisableDirectives: "off" },
    rules: {
      "no-undef": "error",              // a typo'd variable name = a crash on some screen
      "no-dupe-keys": "error",
      "no-duplicate-case": "error",
      "no-unreachable": "error",
      "no-func-assign": "error",
      "no-import-assign": "error",
      "no-self-assign": "error",
      "no-unsafe-negation": "error",
      "no-unsafe-finally": "error",
      "use-isnan": "error",
      "valid-typeof": "error",
      "no-cond-assign": ["error", "except-parens"],
      "no-dupe-else-if": "error",
      "no-constant-binary-expression": "error",
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-script-url": "error",
    },
  },
];
