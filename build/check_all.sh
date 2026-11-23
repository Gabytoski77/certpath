#!/usr/bin/env bash
# Run the same checks as GitHub CI on your own machine (WSL/Linux) before pushing.
# First time:  cd tests && npm ci && cd .. && pip install -r tests/requirements.txt && python3 -m playwright install --with-deps chromium
# Semgrep is required (pip install semgrep, same version as CI; its rules download themselves on first run).
# Optional tools: gitleaks, actionlint on your PATH (skipped with a note if missing).
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
# Semgrep: same version and rules commit as CI (read from ci.yml), so a push can't fail on something this run skipped.
if [ "${SKIP_SEMGREP:-}" = 1 ]; then echo "skip semgrep (SKIP_SEMGREP=1)"; else
  step "Semgrep"
  SG_VER=$(grep -o 'semgrep==[0-9.]*' .github/workflows/ci.yml | head -1 | cut -d= -f3)
  SG_SHA=$(grep -o 'checkout --quiet [0-9a-f]\{40\}' .github/workflows/ci.yml | head -1 | awk '{print $3}')
  if ! command -v semgrep >/dev/null; then
    echo "FAIL: Semgrep isn't installed, and CI runs it on every PR."
    echo "      Install it once in your venv:  pip install semgrep==$SG_VER   (or run with SKIP_SEMGREP=1)"
    exit 1
  fi
  [ "$(semgrep --version 2>/dev/null)" = "$SG_VER" ] || echo "note: semgrep $(semgrep --version 2>/dev/null) here, CI uses $SG_VER"
  R="${SEMGREP_RULES:-$HOME/.cache/mynextcert/semgrep-rules}"
  if [ -z "${SEMGREP_RULES:-}" ]; then   # our own cached copy of the rules, pinned to CI's commit
    [ -d "$R/.git" ] || { echo "downloading Semgrep rules (first run only)..."; git clone --quiet --filter=blob:none https://github.com/semgrep/semgrep-rules "$R"; }
    if [ "$(git -C "$R" rev-parse HEAD)" != "$SG_SHA" ]; then
      git -C "$R" cat-file -e "$SG_SHA^{commit}" 2>/dev/null || git -C "$R" fetch --quiet origin
      git -C "$R" checkout --quiet "$SG_SHA"
    fi
  fi
  J="${TMPDIR:-/tmp}/mnc-js"; rm -rf "$J"; python3 build/extract_scripts.py "$J" >/dev/null
  semgrep scan --metrics=off --disable-version-check --max-target-bytes 5000000 --timeout 300 \
    --config "$R/javascript/browser" --config "$R/javascript/lang/security" \
    --config "$R/javascript/lang/correctness" --config "$R/html/security" \
    --json -q -o "${TMPDIR:-/tmp}/semgrep.json" "$J" 404.html sw.js
  python3 build/semgrep_gate.py "${TMPDIR:-/tmp}/semgrep.json"
fi
step "Browser tests";         python3 -m pytest tests -q -p no:cacheprovider
# On WSL, chrome-launcher (inside lhci) builds a Windows-style temp path (C:\Users\...\AppData\Local\lighthouse.XXXX)
# that Linux treats as a folder NAME, so it lands in the repo root. TMPDIR doesn't change that, so sweep them after.
sweep_lighthouse() { find . -maxdepth 1 -name 'C:\\*lighthouse.*' -exec rm -rf {} + 2>/dev/null || true; }
trap sweep_lighthouse EXIT
# Also on WSL, Lighthouse finds the Windows Chrome, whose debug port WSL can't reach ("Unable to connect to Chrome").
# Use the Linux Chromium that Playwright installed, unless CHROME_PATH is already set.
if [ -z "${CHROME_PATH:-}" ]; then
  PW_CHROME=$(ls -d "$HOME"/.cache/ms-playwright/chromium-*/chrome-linux*/chrome 2>/dev/null | sort -V | tail -1 || true)
  [ -n "$PW_CHROME" ] && export CHROME_PATH="$PW_CHROME"
fi
step "Lighthouse";            tests/node_modules/.bin/lhci autorun --config=tests/lighthouserc.json
sweep_lighthouse
printf '\nAll local checks passed.\n'
