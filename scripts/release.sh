#!/usr/bin/env bash
# Usage: ./scripts/release.sh 0.2.0
set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" || ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Usage: ./scripts/release.sh X.Y.Z"
  exit 1
fi

TAG="v${VERSION}"

# --- Preflight checks -------------------------------------------------------

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Error: working tree is dirty. Commit or stash changes first."
  exit 1
fi

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "Error: must be on main branch."
  exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Error: tag $TAG already exists."
  exit 1
fi

CURRENT=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
if [[ "$CURRENT" == "$VERSION" ]]; then
  echo "Error: version is already $VERSION."
  exit 1
fi

# --- Version bump ------------------------------------------------------------

echo "Bumping version: $CURRENT → $VERSION"

sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
sed -i '' "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/tui_input/__init__.py

# --- Commit + tag + push ----------------------------------------------------

git add pyproject.toml src/tui_input/__init__.py
git commit -m "chore: bump version to $VERSION"
git tag "$TAG"
git push origin main --tags

echo ""
echo "✅ Released $TAG"
echo "   → GitHub Actions will now: build → PyPI → GitHub Release → Homebrew"
