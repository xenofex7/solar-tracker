#!/usr/bin/env bash
# Release helper: bumps VERSION, moves the Unreleased section of
# CHANGELOG.md into a dated release entry, updates README image tag
# examples, commits, tags and pushes.
#
# Usage:
#   scripts/deploy.sh <version>      # e.g. scripts/deploy.sh 1.1.0
#   scripts/deploy.sh patch          # 1.0.0 -> 1.0.1
#   scripts/deploy.sh minor          # 1.0.0 -> 1.1.0
#   scripts/deploy.sh major          # 1.0.0 -> 2.0.0
#
# Flags:
#   -q, --quiet   After pushing, poll the triggered GitHub Actions runs
#                 without streaming them. On success print "[OK] CI passed";
#                 on failure write the failure log to .deploy-ci-<run-id>.log,
#                 print the path and the run URL, then exit 1.

set -euo pipefail

cd "$(dirname "$0")/.."

arg=""
quiet=false
for a in "$@"; do
  case "$a" in
    -q|--quiet) quiet=true ;;
    -*) echo "unknown flag: $a" >&2; exit 1 ;;
    *)
      if [[ -n "$arg" ]]; then
        echo "usage: $0 <version|major|minor|patch> [-q]" >&2
        exit 1
      fi
      arg="$a"
      ;;
  esac
done

if [[ -z "$arg" ]]; then
  echo "usage: $0 <version|major|minor|patch> [-q]" >&2
  exit 1
fi

current=$(cat VERSION)

bump_part() {
  local part=$1
  IFS=. read -r ma mi pa <<<"$current"
  case "$part" in
    major) echo "$((ma + 1)).0.0" ;;
    minor) echo "${ma}.$((mi + 1)).0" ;;
    patch) echo "${ma}.${mi}.$((pa + 1))" ;;
    *) echo "" ;;
  esac
}

case "$arg" in
  major|minor|patch) new=$(bump_part "$arg") ;;
  [0-9]*.[0-9]*.[0-9]*) new="$arg" ;;
  *)
    echo "invalid version: $arg" >&2
    exit 1
    ;;
esac

if [[ ! "$new" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "invalid version produced: $new" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "working tree is not clean - commit or stash first" >&2
  exit 1
fi

if git rev-parse "v${new}" >/dev/null 2>&1; then
  echo "tag v${new} already exists" >&2
  exit 1
fi

# Quality gate: run the same checks CI runs, before we bump/tag/push.
# Prefer .venv binaries so we match the project's pinned toolchain.
pick() {
  if [[ -x ".venv/bin/$1" ]]; then echo ".venv/bin/$1"; return; fi
  if command -v "$1" >/dev/null 2>&1; then command -v "$1"; return; fi
  echo ""
}
ruff_bin=$(pick ruff)
pytest_bin=$(pick pytest)
if [[ -z "$ruff_bin" || -z "$pytest_bin" ]]; then
  echo "ruff and/or pytest not found (.venv/bin or PATH) - install them or run from the project venv" >&2
  exit 1
fi

echo "Running ruff check…"
"$ruff_bin" check .
echo "Running pytest…"
"$pytest_bin" -q

today=$(date +%Y-%m-%d)

echo "Releasing v${current} -> v${new} (${today})"

# Check CHANGELOG has content under [Unreleased]
unreleased_lines=$(awk '
  /^## \[Unreleased\]/ {flag=1; next}
  /^## \[/ {flag=0}
  flag {print}
' CHANGELOG.md | grep -cE '^[^[:space:]]' || true)

if [[ "$unreleased_lines" -eq 0 ]]; then
  echo "CHANGELOG.md has no entries under [Unreleased] - add notes first" >&2
  exit 1
fi

# Sanity: every existing vX.Y.Z git tag should have a matching changelog header,
# otherwise an earlier edit silently dropped a section.
missing=""
while IFS= read -r tag; do
  ver="${tag#v}"
  if ! grep -qE "^## \[${ver}\]" CHANGELOG.md; then
    missing+=" ${tag}"
  fi
done < <(git tag --list 'v[0-9]*.[0-9]*.[0-9]*')
if [[ -n "$missing" ]]; then
  echo "CHANGELOG.md is missing headers for released tags:${missing}" >&2
  exit 1
fi

# VERSION
echo "$new" > VERSION

# CHANGELOG: rename [Unreleased] -> [new] - date, add fresh [Unreleased]
python3 - "$new" "$today" <<'PY'
import re, sys, pathlib
new, today = sys.argv[1], sys.argv[2]
path = pathlib.Path("CHANGELOG.md")
text = path.read_text()

# Insert new version header right after the Unreleased header line.
text = re.sub(
    r"^## \[Unreleased\]\s*\n",
    f"## [Unreleased]\n\n## [{new}] - {today}\n",
    text, count=1, flags=re.MULTILINE,
)

# Update comparison links at the bottom.
text = re.sub(
    r"^\[Unreleased\]: .*$",
    f"[Unreleased]: https://github.com/xenofex7/solar-tracker/compare/v{new}...HEAD",
    text, count=1, flags=re.MULTILINE,
)
if f"[{new}]:" not in text:
    text = text.rstrip() + f"\n[{new}]: https://github.com/xenofex7/solar-tracker/releases/tag/v{new}\n"

path.write_text(text)
PY

# README: update example version tags in docker pull lines
python3 - "$current" "$new" <<'PY'
import re, sys, pathlib
current, new = sys.argv[1], sys.argv[2]
path = pathlib.Path("README.md")
text = path.read_text()
text = re.sub(
    rf"(ghcr\.io/xenofex7/solar-tracker:){re.escape(current)}\b",
    rf"\g<1>{new}",
    text,
)
path.write_text(text)
PY

# docs/index.html: bump softwareVersion in the SoftwareApplication JSON-LD
python3 - "$new" <<'PY'
import re, sys, pathlib
new = sys.argv[1]
path = pathlib.Path("docs/index.html")
text = path.read_text()
new_text, count = re.subn(
    r'("softwareVersion"\s*:\s*")[^"]+(")',
    rf'\g<1>{new}\g<2>',
    text,
    count=1,
)
if count != 1:
    print("warning: softwareVersion not found in docs/index.html", file=sys.stderr)
path.write_text(new_text)
PY

# docs/sitemap.xml: refresh lastmod to today
python3 - "$today" <<'PY'
import re, sys, pathlib
today = sys.argv[1]
path = pathlib.Path("docs/sitemap.xml")
text = path.read_text()
new_text, count = re.subn(
    r"<lastmod>[^<]*</lastmod>",
    f"<lastmod>{today}</lastmod>",
    text,
    count=1,
)
if count != 1:
    print("warning: <lastmod> not found in docs/sitemap.xml", file=sys.stderr)
path.write_text(new_text)
PY

# mcp_server/pyproject.toml: bump version = "X.Y.Z"
python3 - "$new" <<'PY'
import re, sys, pathlib
new = sys.argv[1]
path = pathlib.Path("mcp_server/pyproject.toml")
text = path.read_text()
new_text, count = re.subn(
    r'(?m)^(version\s*=\s*")[^"]+(")',
    rf'\g<1>{new}\g<2>',
    text,
    count=1,
)
if count != 1:
    print("warning: version not found in mcp_server/pyproject.toml", file=sys.stderr)
path.write_text(new_text)
PY

# mcp_server/src/solar_tracker_mcp/__init__.py: bump __version__ = "X.Y.Z"
python3 - "$new" <<'PY'
import re, sys, pathlib
new = sys.argv[1]
path = pathlib.Path("mcp_server/src/solar_tracker_mcp/__init__.py")
text = path.read_text()
new_text, count = re.subn(
    r'(?m)^(__version__\s*=\s*")[^"]+(")',
    rf'\g<1>{new}\g<2>',
    text,
    count=1,
)
if count != 1:
    print("warning: __version__ not found in mcp_server/__init__.py", file=sys.stderr)
path.write_text(new_text)
PY

git add VERSION CHANGELOG.md README.md docs/index.html docs/sitemap.xml \
        mcp_server/pyproject.toml mcp_server/src/solar_tracker_mcp/__init__.py
git commit -m "Release v${new}"
git tag -a "v${new}" -m "Solar-Tracker v${new}"

echo
echo "Local release prepared. Pushing to origin…"
git push origin main "v${new}"

echo
echo "Done. GitHub Actions will build and push ghcr.io/xenofex7/solar-tracker:${new}"

# Watchtower nudge: ask the Synology host to pull the new image as soon as
# it appears on GHCR, instead of waiting for the next poll cycle. The helper
# lives in a sibling repo so the same wiring works for every project. The
# `|| true` keeps the release green if the Synology is offline or the helper
# isn't installed - the tag is already pushed, the image will follow.
if [[ -x "$HOME/Development/synology-server/update.sh" ]]; then
  echo
  echo "Nudging Watchtower on the Synology host…"
  "$HOME/Development/synology-server/update.sh" solar-tracker || true
fi

# Docs sanity reminder. The release script auto-updates docs/index.html
# (softwareVersion in the JSON-LD) and docs/sitemap.xml (lastmod), but the
# user-facing copy in docs/ - meta descriptions, OG/Twitter tags, JSON-LD
# description, hero tagline, install snippet, llms.txt - is hand-written
# and easy to forget. Print the new CHANGELOG entries side-by-side with
# every description-shaped spot in docs/ so drift jumps out.
echo
echo "===================================================================="
echo " Docs sanity check for v${new}"
echo "===================================================================="
echo
echo " Just released (from CHANGELOG.md):"
awk -v ver="${new}" '
  $0 ~ "^## \\["ver"\\]" {flag=1; next}
  /^## \[/ {flag=0}
  flag && /^[^[:space:]]/ {print "   " $0}
' CHANGELOG.md | head -40
echo
echo " Description-shaped spots in docs/index.html (meta/SEO):"
grep -nE 'meta name="description"|og:description|twitter:description|"description":|"softwareRequirements":' docs/index.html 2>/dev/null \
  | sed 's/^/   /' \
  | head -10
echo
echo " Visible copy in docs/index.html (manual review):"
grep -nE 'class="tagline"|class="lead"|<h3>' docs/index.html 2>/dev/null \
  | head -10 \
  | sed 's/^/   line /'
echo
echo " docs/llms.txt:"
grep -nE '^>|^- ' docs/llms.txt 2>/dev/null \
  | sed 's/^/   /' \
  | head -15
echo
echo " GitHub Pages will not auto-correct stale wording."
echo " If anything above looks outdated for v${new}, commit a follow-up:"
echo "   git commit -m \"Update docs site for v${new}\" && git push"
echo "===================================================================="

# Quiet CI watch (-q / --quiet): poll the runs this push triggered without
# streaming them. Compact result so the caller's context stays small. The
# release is already pushed at this point, so any early-out here exits 0 and
# leaves the tag in place - only a genuine CI failure exits non-zero.
if [[ "$quiet" == true ]]; then
  echo
  if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
    echo "[skip] gh not available/authenticated - not watching CI."
    echo "       Check https://github.com/xenofex7/solar-tracker/actions"
    exit 0
  fi

  sha=$(git rev-parse HEAD)
  echo "Watching GitHub Actions for ${sha:0:7} (quiet)…"

  # Runs may take a few seconds to register after the push.
  ids=""
  for _ in $(seq 1 12); do
    ids=$(gh run list --limit 30 --json databaseId,headSha \
            --jq ".[] | select(.headSha==\"$sha\") | .databaseId" 2>/dev/null || true)
    [[ -n "$ids" ]] && break
    sleep 5
  done
  if [[ -z "$ids" ]]; then
    echo "[skip] no workflow runs found for ${sha:0:7} after waiting."
    echo "       Check https://github.com/xenofex7/solar-tracker/actions"
    exit 0
  fi

  failed=0
  for id in $ids; do
    # Poll this run until it completes (max ~30 min, then give up gracefully).
    status="" conclusion=""
    for _ in $(seq 1 180); do
      read -r status conclusion < <(
        gh run view "$id" --json status,conclusion \
          --jq '"\(.status) \(.conclusion)"' 2>/dev/null || echo "unknown "
      )
      [[ "$status" == "completed" ]] && break
      sleep 10
    done

    name=$(gh run view "$id" --json name --jq '.name' 2>/dev/null || echo "run $id")
    url=$(gh run view "$id" --json url --jq '.url' 2>/dev/null || echo "")

    if [[ "$status" != "completed" ]]; then
      failed=1
      echo "[TIMEOUT] ${name} still running -> ${url}"
    elif [[ "$conclusion" == "success" ]]; then
      echo "[OK]   ${name}"
    else
      failed=1
      log=".deploy-ci-${id}.log"
      gh run view "$id" --log-failed > "$log" 2>/dev/null || true
      echo "[FAIL] ${name} (${conclusion}) -> ${log}"
      echo "       ${url}"
    fi
  done

  if [[ "$failed" -ne 0 ]]; then
    exit 1
  fi
  echo "[OK] CI passed"
fi
