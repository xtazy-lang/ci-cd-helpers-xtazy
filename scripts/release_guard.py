#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys
from pathlib import Path


SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


def parse_semver(value: str) -> tuple[int, int, int, tuple[object, ...]]:
    match = SEMVER_RE.match(value)
    if not match:
        raise SystemExit(f"not a valid semver version: {value}")
    pre = match.group("pre")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        parse_pre_release(pre),
    )


def parse_pre_release(value: str | None) -> tuple[object, ...]:
    if value is None:
        return ()
    result: list[object] = []
    for part in value.split("."):
        if part.isdigit():
            result.append(int(part))
        else:
            result.append(part)
    return tuple(result)


def compare_pre_release(left: tuple[object, ...], right: tuple[object, ...]) -> int:
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1

    for left_item, right_item in zip(left, right):
        if left_item == right_item:
            continue
        left_is_int = isinstance(left_item, int)
        right_is_int = isinstance(right_item, int)
        if left_is_int and right_is_int:
            return 1 if left_item > right_item else -1
        if left_is_int:
            return -1
        if right_is_int:
            return 1
        return 1 if str(left_item) > str(right_item) else -1

    if len(left) == len(right):
        return 0
    return 1 if len(left) > len(right) else -1


def compare_semver(left: str, right: str) -> int:
    left_parts = parse_semver(left)
    right_parts = parse_semver(right)
    if left_parts[:3] != right_parts[:3]:
        return 1 if left_parts[:3] > right_parts[:3] else -1
    return compare_pre_release(left_parts[3], right_parts[3])


def manifest_version(manifest: Path) -> str:
    try:
        import tomllib
    except ImportError as error:
        raise SystemExit("Python 3.11+ with tomllib is required") from error

    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    package = data.get("package")
    if not isinstance(package, dict):
        raise SystemExit(f"{manifest}: missing [package] table")
    value = package.get("version")
    if not isinstance(value, str) or not value:
        raise SystemExit(f"{manifest}: missing package.version")
    return value


def git_tags(prefix: str) -> list[str]:
    result = subprocess.run(
        ["git", "tag", "--list", "--", f"{prefix}*"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def latest_semver_tag(tags: list[str], prefix: str) -> str | None:
    versions = []
    for tag in tags:
        if not tag.startswith(prefix):
            continue
        version = tag[len(prefix) :]
        try:
            parse_semver(version)
        except SystemExit:
            continue
        versions.append(version)
    if not versions:
        return None
    return max(versions, key=semver_sort_key)


def semver_sort_key(value: str) -> tuple[int, int, int, int, tuple[tuple[int, object], ...]]:
    major, minor, patch, pre = parse_semver(value)
    pre_weight = 1 if not pre else 0
    normalized_pre: list[tuple[int, object]] = []
    for item in pre:
        if isinstance(item, int):
            normalized_pre.append((0, item))
        else:
            normalized_pre.append((1, str(item)))
    return (major, minor, patch, pre_weight, tuple(normalized_pre))


def write_output(name: str, value: str) -> None:
    import os

    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def cmd_check(args: argparse.Namespace) -> None:
    manifest = manifest_version(args.manifest)
    requested = manifest
    if not requested:
        raise SystemExit("empty release version")
    parse_semver(requested)

    tags = git_tags(args.tag_prefix)
    tag = f"{args.tag_prefix}{requested}"
    if tag in tags:
        raise SystemExit(f"release tag already exists: {tag}")

    latest = latest_semver_tag(tags, args.tag_prefix)
    if latest and compare_semver(requested, latest) <= 0:
        raise SystemExit(f"release version {requested} must be greater than latest released tag {args.tag_prefix}{latest}")

    write_output("version", requested)
    write_output("tag", tag)
    if latest:
        write_output("latest_version", latest)

    print(f"release guard ok: {tag}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Validate release version and git tag state")
    sub = root.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("--manifest", type=Path, default=Path("Cargo.toml"))
    check.add_argument("--tag-prefix", default="v")
    check.set_defaults(func=cmd_check)

    return root


def main() -> int:
    args = parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
