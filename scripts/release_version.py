#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def strip_v(value: str) -> str:
    return value[1:] if value.startswith("v") and len(value) > 1 else value


def from_github_ref() -> str | None:
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        ref = os.environ.get("GITHUB_REF_NAME")
        if ref:
            return strip_v(ref)
    ref = os.environ.get("GITHUB_REF", "")
    prefix = "refs/tags/"
    if ref.startswith(prefix):
        return strip_v(ref[len(prefix):])
    return None


def from_cargo(package: str | None) -> str | None:
    try:
        output = subprocess.check_output(
            ["cargo", "metadata", "--no-deps", "--format-version", "1"],
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    data = json.loads(output)
    packages = data.get("packages", [])
    if package:
        for item in packages:
            if item.get("name") == package:
                return item.get("version")
        return None
    if len(packages) == 1:
        return packages[0].get("version")
    root = data.get("resolve", {}).get("root")
    if root:
        for item in packages:
            if item.get("id") == root:
                return item.get("version")
    return None


def write_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive release version")
    parser.add_argument("--source", choices=["auto", "github-tag", "cargo"], default="auto")
    parser.add_argument("--cargo-package")
    parser.add_argument("--out", type=Path, default=Path("version.txt"))
    args = parser.parse_args()

    value = None
    if args.source in {"auto", "github-tag"}:
        value = from_github_ref()
    if value is None and args.source in {"auto", "cargo"}:
        value = from_cargo(args.cargo_package)
    if value is None:
        raise SystemExit("failed to derive release version from GitHub tag or Cargo metadata")

    args.out.write_text(f"{value}\n", encoding="utf-8", newline="\n")
    write_output("version", value)
    print(value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
