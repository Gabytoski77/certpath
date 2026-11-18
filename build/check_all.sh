#!/usr/bin/env bash
# Run the same checks as GitHub CI on your own machine (WSL/Linux) before pushing.
# First time:  cd tests && npm ci && cd .. && pip install -r tests/requirements.txt && python3 -m playwright install --with-deps chromium
# Optional tools: semgrep, gitleaks, actionlint on your PATH (skipped with a note if missing).
set -euo pipefail
cd "$(dirname "$0")/.."
step() { printf '\n== %s\n' "$1"; }

step "Build matches source";  python3 build/build_site.py --check; python3 build/make_404.py --check
step "Public files";          python3 build/stage_site.py "${TMPDIR:-/tmp}/_site"
step "Site checks";           BASE_SHA="${BASE_SHA:-$(git merge-base HEAD origin/main 2>/dev/null || true)}" python3 .github/scripts/check_site.py
step "HTML + JS lint"
(cd tests && npx html-validate -c .htmlvalidate.json ../index.html ../404.html)
python3 build/extract_scripts.py tests/js-scan >/dev/null && cp sw.js tests/js-scan/
(cd tests && npx eslint --no-config-lookup -c eslint.config.mjs js-scan)
if command -v actionlint >/dev/null; then step "actionlint"; actionlint; else echo "skip actionlint (not installed)"; fi
if command -v gitleaks >/dev/null; then step "Secret scan"; gitleaks git --redact --no-banner .; else echo "skip gitleaks (not installed)"; fi
if command -v semgrep >/dev/null && [ -d "${SEMGREP_RULES:-}" ]; then
  step "Semgrep"; J="${TMPDIR:-/tmp}/mnc-js"; python3 build/extract_scripts.py "$J" >/dev/null
  semgrep scan --metrics=off --disable-version-check --max-target-bytes 5000000 --timeout 300 \
    --config "$SEMGREP_RULES/javascript/browser" --config "$SEMGREP_RULES/javascript/lang/security" \
    --config "$SEMGREP_RULES/javascript/lang/correctness" --config "$SEMGREP_RULES/html/security" \
    --json -q -o "${TMPDIR:-/tmp}/semgrep.json" "$J" 404.html sw.js
  python3 build/semgrep_gate.py "${TMPDIR:-/tmp}/semgrep.json"
else echo "skip semgrep (needs semgrep installed and SEMGREP_RULES=path to a semgrep-rules clone)"; fi
step "Browser tests";         python3 -m pytest tests -q -p no:cacheprovider
step "Lighthouse";            tests/node_modules/.bin/lhci autorun --config=tests/lighthouserc.json
printf '\nAll local checks passed.\n'
