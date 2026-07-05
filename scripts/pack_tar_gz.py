#!/usr/bin/env python3
import argparse
import gzip
import sys
import tarfile
from pathlib import Path


def normalize(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def add(tar: tarfile.TarFile, source: Path, arcname: str) -> None:
    info = normalize(tar.gettarinfo(str(source), arcname))
    if source.is_dir():
        tar.addfile(info)
        for child in sorted(source.iterdir(), key=lambda value: value.name):
            add(tar, child, f"{arcname}/{child.name}")
        return
    if source.is_file():
        with source.open("rb") as handle:
            tar.addfile(info, handle)
        return
    raise SystemExit(f"unsupported input: {source}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create deterministic tar.gz")
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root-name")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"missing source: {args.source}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    root_name = args.root_name or args.source.name
    with args.out.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gzip_file:
            with tarfile.open(fileobj=gzip_file, mode="w") as tar:
                add(tar, args.source, root_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
