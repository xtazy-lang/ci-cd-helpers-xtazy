#!/usr/bin/env bash
set -euo pipefail

project_dir="${1:-.}"
cargo_toml="$project_dir/Cargo.toml"
main_rs="$project_dir/src/main.rs"

if [[ ! -f "$cargo_toml" ]]; then
  echo "missing Cargo.toml: $cargo_toml" >&2
  exit 1
fi

if [[ ! -f "$main_rs" ]]; then
  echo "missing binary entry file: $main_rs" >&2
  exit 1
fi

# Add the dependency using standard cargo tool
# This is safe and correctly formats the Cargo.toml
# We run it in the project directory
(cd "$project_dir" && cargo add tikv-jemallocator@0.6)

python3 - "$main_rs" <<'PY'
from pathlib import Path
import sys

main_rs = Path(sys.argv[1])

main = main_rs.read_text(encoding="utf-8")
marker = "tikv_jemallocator::Jemalloc"
if marker not in main:
    block = """#[cfg(all(target_family = \"unix\", not(target_os = \"macos\")))]\n#[global_allocator]\nstatic GLOBAL_ALLOCATOR: tikv_jemallocator::Jemalloc = tikv_jemallocator::Jemalloc;\n\n"""
    main_rs.write_text(block + main, encoding="utf-8", newline="\n")
PY
