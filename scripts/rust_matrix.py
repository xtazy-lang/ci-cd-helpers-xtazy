#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path


REQUIRED_FIELDS = {
    "os",
    "arch",
    "runner",
    "target",
    "suffix",
    "family",
    "lookup_os",
    "lookup_arch",
}


OPTIONAL_FIELDS = {
    "pre_build_script",
}


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate(data, path)
    return data


def validate(data: dict, path: Path) -> None:
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected JSON object")
    matrix = data.get("build_matrix")
    if not isinstance(matrix, list) or not matrix:
        raise SystemExit(f"{path}: build_matrix must be a non-empty list")

    suffixes = set()
    targets = set()
    lookup_keys = set()

    for index, item in enumerate(matrix):
        if not isinstance(item, dict):
            raise SystemExit(f"{path}: build_matrix[{index}] must be an object")

        missing = REQUIRED_FIELDS - set(item)
        if missing:
            raise SystemExit(f"{path}: build_matrix[{index}] missing {', '.join(sorted(missing))}")

        unknown = set(item) - REQUIRED_FIELDS - OPTIONAL_FIELDS
        if unknown:
            raise SystemExit(f"{path}: build_matrix[{index}] unknown fields {', '.join(sorted(unknown))}")

        suffix = string_field(item, "suffix", path, index)
        target = string_field(item, "target", path, index)
        family = string_field(item, "family", path, index)
        lookup_os = string_field(item, "lookup_os", path, index)

        if suffix in suffixes:
            raise SystemExit(f"{path}: duplicate suffix {suffix}")
        if target in targets:
            raise SystemExit(f"{path}: duplicate Rust target {target}")
        suffixes.add(suffix)
        targets.add(target)

        lookup_arch = item["lookup_arch"]
        if not isinstance(lookup_arch, list) or not lookup_arch:
            raise SystemExit(f"{path}: build_matrix[{index}].lookup_arch must be a non-empty list")
        for arch in lookup_arch:
            if not isinstance(arch, str) or not arch:
                raise SystemExit(f"{path}: build_matrix[{index}].lookup_arch entries must be non-empty strings")
            lookup_key = (family, f"{lookup_os}_{arch}")
            if lookup_key in lookup_keys:
                raise SystemExit(f"{path}: duplicate lookup key {lookup_key[0]} {lookup_key[1]}")
            lookup_keys.add(lookup_key)


def string_field(item: dict, key: str, path: Path, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise SystemExit(f"{path}: build_matrix[{index}].{key} must be a non-empty string")
    return value


def output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def cmd_validate(args: argparse.Namespace) -> None:
    load(args.matrix)


def cmd_github(args: argparse.Namespace) -> None:
    data = load(args.matrix)
    value = json.dumps({"include": data["build_matrix"]}, separators=(",", ":"))
    output(args.output_name, value)
    print(value)


def cmd_suffixes(args: argparse.Namespace) -> None:
    data = load(args.matrix)
    for item in data["build_matrix"]:
        print(item["suffix"])


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Rust build matrix helper")
    sub = root.add_subparsers(dest="command", required=True)

    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("--matrix", type=Path, default=Path("rust_build_matrix.json"))
    validate_cmd.set_defaults(func=cmd_validate)

    github_cmd = sub.add_parser("github")
    github_cmd.add_argument("--matrix", type=Path, default=Path("rust_build_matrix.json"))
    github_cmd.add_argument("--output-name", default="matrix")
    github_cmd.set_defaults(func=cmd_github)

    suffixes_cmd = sub.add_parser("suffixes")
    suffixes_cmd.add_argument("--matrix", type=Path, default=Path("rust_build_matrix.json"))
    suffixes_cmd.set_defaults(func=cmd_suffixes)

    return root


def main() -> int:
    args = parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
