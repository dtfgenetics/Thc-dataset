#!/usr/bin/env bash
# Publish files to a GitHub release without overwriting existing, potentially different bytes.
set -euo pipefail
if (($# < 2)); then
  echo "Usage: $0 TAG FILE..." >&2
  exit 2
fi
tag="$1"; shift
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY must be set}"
command -v gh >/dev/null
command -v jq >/dev/null
declare -A names
for file in "$@"; do
  [[ -f "$file" ]] || { echo "Not a regular file: $file" >&2; exit 2; }
  name="${file##*/}"
  [[ -z "${names[$name]+x}" ]] || { echo "Duplicate source basename: $name" >&2; exit 2; }
  names[$name]=1
done
release_id="$(gh api "repos/$repo/releases/tags/$tag" --jq .id)"
assets="$(gh api --paginate "repos/$repo/releases/$release_id/assets?per_page=100" --jq '.[] | [.id, .name, .size, (.digest // "-"), .state] | @tsv')"
for file in "$@"; do
  name="${file##*/}"
  size="$(stat -c%s "$file")"
  checksum="$(sha256sum "$file" | cut -d' ' -f1)"
  existing="$(printf '%s\n' "$assets" | awk -F '\t' -v name="$name" '$2 == name {print; exit}')"
  if [[ -n "$existing" ]]; then
    IFS=$'\t' read -r asset_id existing_name existing_size existing_digest existing_state <<< "$existing"
    if [[ "$existing_state" != "uploaded" ]]; then
      echo "BLOCKED $name: release asset state is '$existing_state' (id $asset_id); incomplete upload requires explicit cleanup" >&2
      exit 1
    fi
    if [[ "$existing_size" != "$size" ]]; then
      echo "CONFLICT $name: existing size $existing_size differs from $size" >&2
      exit 1
    fi
    if [[ "$existing_digest" == "sha256:$checksum" ]]; then
      echo "SKIP identical $name (API SHA256)"
      continue
    fi
    # Older release assets may lack a digest: hash the actual existing bytes.
    tmp="$(mktemp -d)"
    gh release download "$tag" --repo "$repo" --pattern "$name" --dir "$tmp" --clobber
    remote_sha="$(sha256sum "$tmp/$name" | cut -d' ' -f1)"
    rm -rf "$tmp"
    if [[ "$remote_sha" == "$checksum" ]]; then
      echo "SKIP identical $name (downloaded SHA256)"
      continue
    fi
    echo "CONFLICT $name: existing bytes differ; refusing overwrite" >&2
    exit 1
  fi
  echo "UPLOAD $name"
  gh release upload "$tag" "$file" --repo "$repo"
done
