#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


class TemplateError(Exception):
    pass


class Node:
    def render(self, context: dict) -> str:
        raise NotImplementedError()


class TextNode(Node):
    def __init__(self, text: str):
        self.text = text

    def render(self, context: dict) -> str:
        return self.text


class VarNode(Node):
    def __init__(self, expr: str):
        self.expr = expr

    def render(self, context: dict) -> str:
        try:
            return str(resolve_expr(self.expr, context))
        except Exception as e:
            raise TemplateError(f"Error rendering variable {self.expr!r}: {e}") from e


class ForNode(Node):
    def __init__(self, var_name: str, iterable_expr: str, body_nodes: list[Node]):
        self.var_name = var_name
        self.iterable_expr = iterable_expr
        self.body_nodes = body_nodes

    def render(self, context: dict) -> str:
        try:
            items = resolve_expr(self.iterable_expr, context)
        except Exception as e:
            raise TemplateError(f"Error resolving loop collection {self.iterable_expr!r}: {e}") from e
        if not isinstance(items, list):
            raise TemplateError(f"Loop collection {self.iterable_expr!r} must be a list, got {type(items).__name__}")

        result = []
        n = len(items)
        for i, item in enumerate(items):
            child_context = dict(context)
            child_context[self.var_name] = item
            child_context["loop"] = {
                "index": i + 1,
                "index0": i,
                "first": i == 0,
                "last": i == n - 1,
            }
            for node in self.body_nodes:
                result.append(node.render(child_context))
        return "".join(result)


class IfNode(Node):
    def __init__(self, condition_expr: str, body_nodes: list[Node], else_nodes: list[Node] = None):
        self.condition_expr = condition_expr
        self.body_nodes = body_nodes
        self.else_nodes = else_nodes or []

    def render(self, context: dict) -> str:
        try:
            cond = resolve_expr(self.condition_expr, context)
        except Exception as e:
            raise TemplateError(f"Error resolving condition {self.condition_expr!r}: {e}") from e

        nodes = self.body_nodes if cond else self.else_nodes
        return "".join(node.render(context) for node in nodes)


def xml_escape(val) -> str:
    s = str(val)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")


def csv_escape(val) -> str:
    s = str(val)
    if any(c in s for c in (',', '"', '\n', '\r')):
        return '"' + s.replace('"', '""') + '"'
    return s


def tsv_escape(val) -> str:
    s = str(val)
    return s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n').replace('\r', '\\r')


def resolve_expr(expr: str, context: dict) -> object:
    expr = expr.strip()
    is_negated = False
    if expr.startswith("not "):
        is_negated = True
        expr = expr[4:].strip()

    parts = [p.strip() for p in expr.split("|")]
    base_expr = parts[0]
    filters = parts[1:]

    keys = base_expr.split(".")
    val = context
    for key in keys:
        if isinstance(val, dict) and key in val:
            val = val[key]
        else:
            raise ValueError(f"Could not resolve {key!r} in expression {expr!r}")

    if is_negated:
        val = not val

    for f in filters:
        if f == "json":
            val = json.dumps(val)
        elif f == "json_escape":
            val = json.dumps(str(val))[1:-1]
        elif f == "xml":
            val = xml_escape(val)
        elif f == "csv":
            val = csv_escape(val)
        elif f == "tsv":
            val = tsv_escape(val)
        else:
            raise ValueError(f"Unknown filter {f!r}")
    return val


def is_control_only_line(line: str) -> bool:
    stripped = re.sub(r'\{%.*?%\}', '', line)
    return stripped.strip() == ""


def parse_blocks(text: str) -> list[Node]:
    pattern = re.compile(r'(\{%.*?%\}|\{\{.*?\}\})', re.DOTALL)
    tokens = pattern.split(text)

    stack = [([], None)]

    for i, token in enumerate(tokens):
        if not token:
            continue
        if i % 2 == 0:
            stack[-1][0].append(TextNode(token))
        else:
            if token.startswith("{{"):
                expr = token[2:-2].strip()
                stack[-1][0].append(VarNode(expr))
            elif token.startswith("{%"):
                content = token[2:-2].strip()
                parts = content.split()
                if not parts:
                    raise TemplateError("Empty control tag")
                tag_name = parts[0]

                if tag_name == "for":
                    if len(parts) < 4 or parts[2] != "in":
                        raise TemplateError(f"Invalid for loop syntax: {token}")
                    var_name = parts[1]
                    iterable_expr = parts[3]
                    stack.append(([], ("for", var_name, iterable_expr)))
                elif tag_name == "if":
                    if len(parts) < 2:
                        raise TemplateError(f"Invalid if syntax: {token}")
                    condition_expr = " ".join(parts[1:])
                    stack.append(([], ("if", condition_expr)))
                elif tag_name == "else":
                    nodes, info = stack.pop()
                    if info is None or info[0] != "if":
                        raise TemplateError("Unmatched {% else %}")
                    stack.append(([], ("else", info[1], nodes)))
                elif tag_name == "endfor":
                    nodes, info = stack.pop()
                    if info is None or info[0] != "for":
                        raise TemplateError("Unmatched {% endfor %}")
                    stack[-1][0].append(ForNode(info[1], info[2], nodes))
                elif tag_name == "endif":
                    nodes, info = stack.pop()
                    if info is None:
                        raise TemplateError("Unmatched {% endif %}")
                    if info[0] == "if":
                        stack[-1][0].append(IfNode(info[1], nodes))
                    elif info[0] == "else":
                        stack[-1][0].append(IfNode(info[1], info[2], nodes))
                    else:
                        raise TemplateError("Unmatched {% endif %}")
                else:
                    raise TemplateError(f"Unknown control tag: {tag_name}")

    if len(stack) > 1:
        _, info = stack[-1]
        raise TemplateError(f"Unclosed tag: {info[0]}")

    return stack[0][0]


def render_template(template_text: str, context: dict) -> str:
    lines = template_text.splitlines(keepends=True)
    new_lines = []
    for line in lines:
        if is_control_only_line(line):
            tags = re.findall(r'\{%.*?%\}', line)
            new_lines.append("".join(tags))
        else:
            new_lines.append(line)

    processed_text = "".join(new_lines)
    nodes = parse_blocks(processed_text)
    return "".join(node.render(context) for node in nodes)


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"{path}: invalid JSON: {error}") from error
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected JSON object")
    return data


def read_version(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise SystemExit(f"{path}: empty version")
    return value


def string_field(item: dict, key: str, source: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise SystemExit(f"{source}: missing non-empty string field {key}")
    return value


def artifact_manifests(args: argparse.Namespace) -> list[dict]:
    if not args.artifact_manifest_dir.is_dir():
        raise SystemExit(f"missing artifact manifest directory: {args.artifact_manifest_dir}")
    paths = sorted(args.artifact_manifest_dir.glob("*.json"))
    if not paths:
        raise SystemExit(f"no artifact manifests found in {args.artifact_manifest_dir}")

    items = []
    for path in paths:
        item = load_json(path)
        string_field(item, "filename", str(path))
        string_field(item, "sha256", str(path))
        string_field(item, "suffix", str(path))
        items.append(item)
    return items


def get_artifacts(args: argparse.Namespace) -> list[dict]:
    manifests = artifact_manifests(args)
    for manifest in manifests:
        filename = string_field(manifest, "filename", "artifact manifest")
        artifact_path = args.artifact_dir / filename
        if not artifact_path.is_file():
            raise SystemExit(f"missing artifact referenced by manifest: {artifact_path}")
    return manifests


def output_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise SystemExit(f"output path must be relative: {raw_path}")
    
    workspace = Path.cwd().resolve()
    if not path.resolve().is_relative_to(workspace):
        raise SystemExit(f"output path must not escape the workspace: {raw_path}")
    return path


def cmd_generate(args: argparse.Namespace) -> None:
    spec = load_json(args.spec)
    schema = spec.get("schema")
    if schema is None:
        raise SystemExit(f"{args.spec}: missing schema version")
    if schema != 1:
        raise SystemExit(f"{args.spec}: unsupported schema version: {schema}")

    outputs = spec.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise SystemExit(f"{args.spec}: outputs must be a non-empty list")

    globals_ = {
        "version": read_version(args.version_file),
    }

    generated: list[Path] = []
    artifacts: list[dict] | None = None

    for out_spec in outputs:
        if not isinstance(out_spec, dict):
            raise SystemExit(f"{args.spec}: output entries must be objects")

        path_str = out_spec.get("path")
        if not isinstance(path_str, str) or not path_str:
            raise SystemExit(f"{args.spec}: each output needs a non-empty path")

        template_str = out_spec.get("template")
        if not isinstance(template_str, str) or not template_str:
            raise SystemExit(f"{args.spec}: each output needs a non-empty template path")

        template_path = Path(template_str)
        if not template_path.is_absolute():
            template_path = args.spec.parent / template_path

        if not template_path.is_file():
            raise SystemExit(f"missing template file: {template_path}")

        try:
            template_text = template_path.read_text(encoding="utf-8")
        except Exception as error:
            raise SystemExit(f"failed to read template {template_path}: {error}")

        out_path = output_path(path_str)

        if artifacts is None:
            artifacts = get_artifacts(args)

        context = dict(globals_)
        context["artifacts"] = artifacts

        try:
            rendered = render_template(template_text, context)
        except Exception as error:
            raise SystemExit(f"failed to render template {template_path}: {error}")

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8", newline="\n")
        except Exception as error:
            raise SystemExit(f"failed to write output {out_path}: {error}")

        generated.append(out_path)

    if args.list_out:
        args.list_out.write_text("".join(f"{path}\n" for path in generated), encoding="utf-8", newline="\n")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Generate release result files from a JSON result spec")
    sub = root.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate")
    generate.add_argument("--spec", type=Path, required=True)
    generate.add_argument("--artifact-dir", type=Path, default=Path("dist"))
    generate.add_argument("--artifact-manifest-dir", type=Path, default=Path("dist/artifact-manifests"))
    generate.add_argument("--version-file", type=Path, default=Path("version.txt"))
    generate.add_argument("--list-out", type=Path, default=Path(".result-files.list"))
    generate.set_defaults(func=cmd_generate)

    return root


def main() -> int:
    args = parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
