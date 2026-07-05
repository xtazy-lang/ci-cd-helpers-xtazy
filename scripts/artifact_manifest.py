#!/usr/bin/env python3
import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"missing artifact: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_lookup_arch(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise SystemExit(f"invalid lookup arch JSON: {error}") from error
    if not isinstance(parsed, list) or not parsed or not all(isinstance(item, str) and item for item in parsed):
        raise SystemExit("lookup arch JSON must be a non-empty string array")
    return parsed


def cmd_write(args: argparse.Namespace) -> None:
    manifest = {
        "schema": 1,
        "filename": args.artifact.name,
        "sha256": sha256_file(args.artifact),
        "version": args.version,
        "prefix": args.prefix,
        "suffix": args.suffix,
        "family": args.family,
        "lookup_os": args.lookup_os,
        "lookup_arch": parse_lookup_arch(args.lookup_arch),
        "archive_format": args.archive_format,
        "target": args.target,
        "os": args.os,
        "arch": args.arch,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Write release artifact manifest metadata")
    sub = root.add_subparsers(dest="command", required=True)

    write = sub.add_parser("write")
    write.add_argument("--out", type=Path, required=True)
    write.add_argument("--artifact", type=Path, required=True)
    write.add_argument("--version", required=True)
    write.add_argument("--prefix", required=True)
    write.add_argument("--suffix", required=True)
    write.add_argument("--family", required=True)
    write.add_argument("--lookup-os", required=True)
    write.add_argument("--lookup-arch", required=True)
    write.add_argument("--archive-format", required=True)
    write.add_argument("--target", required=True)
    write.add_argument("--os", required=True)
    write.add_argument("--arch", required=True)
    write.set_defaults(func=cmd_write)

    return root


def main() -> int:
    args = parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
