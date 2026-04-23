#!/usr/bin/env bash
# Release helper: bumps VERSION, moves the Unreleased section of
# CHANGELOG.md into a dated release entry, updates README image tag
# examples, commits, tags and pushes.
#
# Usage:
#   scripts/release.sh <version>     # e.g. scripts/release.sh 1.1.0
#   scripts/release.sh patch         # 1.0.0 -> 1.0.1
#   scripts/release.sh minor         # 1.0.0 -> 1.1.0
#   scripts/release.sh major         # 1.0.0 -> 2.0.0

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <version|major|minor|patch>" >&2
  exit 1
fi

arg="$1"
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

git add VERSION CHANGELOG.md README.md
git commit -m "Release v${new}"
git tag -a "v${new}" -m "Solar-Tracker v${new}"

echo
echo "Local release prepared. Pushing to origin…"
git push origin main "v${new}"

echo
echo "Done. GitHub Actions will build and push ghcr.io/xenofex7/solar-tracker:${new}"
