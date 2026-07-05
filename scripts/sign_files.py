#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path


def require_env(names: list[str]) -> None:
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"missing required environment variables: {', '.join(missing)}")


def parse_file_ref(value: str) -> Path:
    value = value.strip()
    if value.startswith("sig(") and value.endswith(")"):
        value = value[4:-1].strip()
    if not value:
        raise SystemExit("empty file reference")
    return Path(value)


def files(args: argparse.Namespace) -> list[Path]:
    result = [parse_file_ref(item) for item in args.files]
    if args.file_list:
        for line in args.file_list.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            result.append(parse_file_ref(line))
    if not result:
        raise SystemExit("no files to sign")
    return result


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise SystemExit(f"missing {label}: {path}")


def sign(
    path: Path,
    xsig_bin: str,
    private_key: Path,
    delegation: Path,
    password: str,
    password_env: str,
) -> Path:
    if not path.is_file():
        raise SystemExit(f"missing file: {path}")
    output = Path(f"{path}.xsigfile")
    env = os.environ.copy()
    # The child xsig process receives the secret only on stdin, not as an env var.
    env.pop(password_env, None)
    subprocess.run(
        [
            xsig_bin,
            "sign",
            "--private",
            str(private_key),
            "--delegation",
            str(delegation),
            "--file",
            str(path),
            "--out",
            str(output),
        ],
        input=password,
        text=True,
        check=True,
        env=env,
    )
    if not output.is_file():
        raise SystemExit(f"sign command did not create {output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign files with xsig")
    parser.add_argument("files", nargs="*")
    parser.add_argument("--file-list", type=Path)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--delegation", type=Path, required=True)
    parser.add_argument("--password-env", default="XSIG_PASSWORD")
    parser.add_argument("--xsig-bin", default="xsig")
    args = parser.parse_args()

    require_file(args.private, "private key")
    require_file(args.delegation, "delegation")
    require_env([args.password_env])

    password = os.environ[args.password_env]
    if not password:
        raise SystemExit(f"empty required environment variable: {args.password_env}")
    for path in files(args):
        print(sign(path, args.xsig_bin, args.private, args.delegation, password, args.password_env))
    return 0


if __name__ == "__main__":
    sys.exit(main())
