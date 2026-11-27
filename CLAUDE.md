# MyNextCert (mynextcert.com): rules for Claude

MyNextCert is Gabytoski's free site of IT cert paths, study guides, DoD 8140 work roles and CG COOL funding for
Coast Guard IT. One self-contained app page, hosted on GitHub Pages behind Cloudflare. Not an official U.S. Coast
Guard site. The owner is learning (Security+ / SOC analyst track): explain what you changed in plain words.

These rules are the same ones the claude.ai CERTPATH project chats follow (skills certpath-release,
certpath-quick-edit, certpath-guide). If another skill (Superpowers, UI UX Pro Max, Taste Skill...) says something
different, **this file wins**.

## Where things live

| Path | What it is |
|---|---|
| `src/app.html` | **The source of truth for the app.** Same file as the claude.ai preview artifact (slug `1811d6a9-4955-405c-b8c6-440326077839`); loads libraries/fonts from CDNs. |
| `src/site-head.html`, `src/site-tail.html` | The live site's own head (SEO/share tags, icons) and the service worker registration. |
| `build/build_site.py` | Builds `index.html` from `src/`: swaps CDNs for `vendor/` + `fonts/`, writes the CSP with a sha256 per inline script. |
| `build/make_404.py` | Writes `404.html`. |
| `index.html`, `404.html` | **Generated. Never edit by hand** (the CSP hashes break and CI fails). |
| `guides/*.json` | **Generated. Never edit by hand.** Each guide, split out of `src/app.html` by `build/split_guides.py` when you run `build_site.py`; fetched when a guide opens (`?h=` hash in the address). `index.html` keeps only a small index of each guide. Edit guides in `src/app.html` as before, rebuild, and commit the changed `guides/` files with `index.html`. |
| `sw.js` | Service worker. `VERSION = "certpath-vN"`. |
| `qbank/*.json` | Practice exam question banks. |
| `img/globe/` | Light mode's still globe: one picture per vendor (1000 and 1600 px) + `views.json` (badge tap targets). Made by `build/make_globe_stills.py`; rerun it (about 3 min) after changing how the globe or the vendors look, and commit the results. |
| `.github/scripts/check_site.py` | Site checks (CSP, no outside loads, 8140 data, share tags, banks, version bump). |
| `tests/` | Playwright browser tests, axe, Lighthouse, lint configs, Semgrep baseline. |
| `build/stage_site.py` | Lists which files are public. Only those are deployed. |
| `build/check_all.sh` | Runs every CI check locally. |

## How a change ships (never push to main)

1. `git switch main && git pull`, then `git switch -c <short-branch-name>`. One change per branch; finish it before starting another.
2. Edit `src/` (or `sw.js`, `qbank/`, `build/`...). Never `index.html` / `404.html` directly.
3. `python3 build/build_site.py` (and `python3 build/make_404.py` if the 404 page changed).
4. If `index.html` changed: bump the visible label `<span>v.2.X</span>` in `src/app.html` (rebuild again) **and** `VERSION` in `sw.js`, or installed phones keep the old copy. CI fails if you forget. Also add one line at the top of the `WHATS_NEW` array in `src/app.html` (version, ISO date, 1–2 plain lines for users; keep about 6).
5. Run the fast checks: `python3 build/build_site.py --check`, `python3 .github/scripts/check_site.py`, `python3 build/check_qbank.py qbank/<file>.json` for a bank you touched, and only the tests you added or changed: `python3 -m pytest tests/<file>.py -q -n 1`. All must pass. GitHub CI runs the full suite on every PR (the repo is public, so Actions minutes are free); the full local run (`bash build/check_all.sh`) is optional because it can freeze a laptop.
6. Commit as `Gabytoski77 <Gabytoski77@users.noreply.github.com>` (never a personal email). Message = what changed for users, in plain words.
7. `git push -u origin <branch>` and open a PR (`gh pr create`). CI runs every check. Merge only when it's green; the Deploy workflow re-runs every check and only then publishes.
8. After the merge, the Post-deploy workflow checks the live site. Tell the owner to close and reopen the app once to see the new label.
9. The claude.ai preview artifact syncs itself: the scheduled task "MyNextCert preview auto-sync" copies main to it every 3 hours. Nothing to do here.
10. Rollback: revert the commit on main through a PR (GitHub's "Revert" button on the merged PR). Deploy runs again.

Small edits (typo, link, one fact): batch several on one branch rather than one PR each. The owner prefers updates queued and shipped together when he says "ship it".

## Hard rules

- **Public information only.** No CUI, no internal CG documents, no personal info. No CG seal or logos, no vendor logos as images.
- Keep "Not an official U.S. Coast Guard site" in the footer and the © 2026 Gabriel Rodriguez line.
- **Nothing loads from outside servers.** No CDNs, Google Fonts, analytics, outside images or embeds on the live site. New library = local copy in `vendor/` with its license + a swap in `build_site.py` + add to `sw.js` SHELL if needed. The CSP and the tests block anything else.
- **Every string from data or the user goes through `gEsc()`** before it goes into `innerHTML`. Semgrep fails on any new `innerHTML`/`document.write` use: check it is escaped, then (and only then) accept it with `python3 build/semgrep_gate.py <semgrep.json> --update`.
- Quiz questions and PBQs are **original**, at or above real exam difficulty. Never copy CertMaster, vendor or practice-test questions.
- Facts (exam codes, dates, prices, question counts, DoD 8140 mapping) come from official sources; record the date checked. Third-party-only facts are flagged to the owner as "verify".
- Offensive-security content stresses written authorization and legal labs (TryHackMe, Hack The Box, own machines).
- Plain language for junior Coast Guard IT members: short sentences, define jargon once.
- Don't rename a guide's version keys after shipping (saved progress depends on them).
- A literal `</script>` inside a JS string ends the page script: write `<\/script>`.
- New public file at the repo root? Add it to `PUBLIC` in `build/stage_site.py`, or it won't be deployed (CI asks you to decide).

## Working on the big source file

`src/app.html` is ~1.7 MB. Never read it whole. Grep for a distinctive word, then Read only those lines (offset/limit), and change it with Edit using the exact text (watch for `·`, `–`, curly quotes).
Pipe grep output on src/app.html through cut -c1-300 (line 4 is a long base64 icon).
Guides are `GUIDES["Name"]={...}` objects just before the `G_SECS=` line (plain data only: no functions or regexes, because the build parses them as data); copy the closest existing guide as a template. Search aliases are in `ALIAS` (edit the existing entry; a duplicate key wins). Every guide has `checked:"YYYY-MM-DD"` (shown as "Facts last checked"): set it to the day you really re-verified its facts, never a guess. `check_site.py` fails on a missing, bad or future date and warns after 45 days.

## Helpers (save tokens; none are public files)

Use these instead of reading `src/app.html` or a `qbank/` file by hand. All are in `build/`.

| Command | Use it when |
|---|---|
| `python3 build/show_guide.py "Name"` | You need one guide. Add `--outline` to see just its top-level keys; `--names` lists every guide. It prints the line numbers, so you can `Read` with offset/limit or `Edit`. |
| `python3 build/list_guides.py` | You want every guide's "checked" date and days since, oldest first (monthly fact check, or before editing facts). |
| `python3 build/check_qbank.py qbank/<file>.json` | You edited a question bank. Same rules as `check_site.py`, in seconds, for one file. |

`.claude/settings.json` pre-approves only safe, read-only or test commands (pytest, these helpers, `build_site.py`, `check_site.py`, git status/diff/log/switch/pull, `gh pr view/checks`, `gh run view/list`). Pushing to main, force pushes and reading `.env` stay denied.

## Tests

- `pip install -r tests/requirements.txt semgrep==1.186.0 && python3 -m playwright install --with-deps chromium && (cd tests && npm ci)` once. `build/check_all.sh` fails if Semgrep is missing (CI runs it on every PR) and downloads CI's pinned Semgrep rules itself on the first run.
- Day to day, run only the test files you touched (`python3 -m pytest tests/<file>.py -q -n 1`); CI runs everything. The whole suite locally is `python3 -m pytest tests -q -n 2` (more than 2 workers overload the software WebGL on a laptop, and even 2 can freeze a slow one). Add a test for every bug fixed and every new feature.
- Known accessibility issues are listed in `tests/a11y-known.json`; when you fix one, delete its line.
- The site's code is inside an IIFE: tests drive the DOM (search open = `#srch.on`, sheet open = `#sh-grab[aria-expanded=true]`).

## How to work (Karpathy guidelines, adapted)

1. **Think before coding.** State assumptions. If something is unclear, or there are two reasonable readings, ask. If a simpler way exists, say so.
2. **Simplicity first.** The minimum change that solves the request. No extra features, no abstractions for one use, no "flexibility" nobody asked for.
3. **Surgical changes.** Touch only what the request needs. Match the existing style. Mention unrelated problems; don't fix them unasked.
4. **Goal-driven.** Turn the request into something checkable ("write a test that shows the bug, then make it pass") and loop until the checks pass. For multi-step work, write a short plan with a check per step.

## Question banks: writer + reviewer

New bank, new questions or bank fixes: (1) the `qbank-writer` subagent writes; (2) a fresh `qbank-reviewer` subagent grades it (it never saw the writing); (3) the writer fixes what the reviewer found; repeat until the reviewer says PASS. Paste the reviewer's final verdict in the PR description. Never let the writer grade itself.

## Automated helpers (claude.ai scheduled tasks)

Scheduled agents may open PRs on branches named `bot/...` (monthly fact check, weekly bank audit). They never merge: **only the owner merges**. If a `bot/` PR is open when you start work, finish or close it first, or expect a version-bump conflict.

## Models

Project default is `opusplan` (Opus plans, Sonnet builds). Use a stronger model only for hard problems.
