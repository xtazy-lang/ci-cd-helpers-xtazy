# Result Files Template-based Output Generation

The `result-files` component is a generic template-based generator used to produce release result files (such as TSV, CSV, JSON, XML, or other plain text metadata).

## Result Files Spec Shape

A results specification file (e.g. `result_files.json`) defines the schema version and outputs to generate:

```json
{
  "schema": 1,
  "outputs": [
    {
      "path": "targets.tsv",
      "template": "templates/targets.tsv.xtpl"
    },
    {
      "path": "artifacts.json",
      "template": "templates/artifacts.json.xtpl"
    }
  ]
}
```

- **schema**: Must be exactly `1`.
- **outputs**: A list of output objects:
  - **path**: Relative path inside the workspace where the rendered file should be written. Paths cannot use `..` to escape the workspace directory.
  - **template**: Path to the template file. If relative, it is resolved **relative to the directory of the spec file**.

---

## Template Context Variables

Templates receive a rendering context with the following keys:

- `version`: The release version string loaded from the version file (e.g., `1.2.3`).
- `artifacts`: A list of artifact objects. Each object contains the metadata produced by `artifact_manifest.py`:
  - `filename`: Filename of the release archive (e.g. `dealer-linux-amd64.tar.gz`).
  - `sha256`: SHA-256 hash of the archive.
  - `version`: Version string of the release.
  - `prefix`: Prefix used for packaging (e.g. `dealer`).
  - `suffix`: Target suffix (e.g. `linux-amd64`).
  - `family`: Platform family (e.g. `linux`, `windows`, `macos`).
  - `lookup_os`: OS for matching lookups (e.g. `linux`, `windows`).
  - `lookup_arch`: A list of compatible architectures (e.g. `["amd64", "x86_64"]`).
  - `archive_format`: Package format (e.g. `tar.gz`).
  - `target`: Rust target triple.
  - `os`: Target OS.
  - `arch`: Target architecture.

---

## Template Syntax

The template engine supports basic control statements and variable interpolation.

### Loop Syntax

Use `{% for item in collection %}` and `{% endfor %}` to loop over lists (e.g., `artifacts` or `artifact.lookup_arch`).

```text
{% for artifact in artifacts %}
...
{% for arch in artifact.lookup_arch %}
...
{% endfor %}
{% endfor %}
```

Within loops, a special `loop` object is available with the following properties:
- `loop.index`: 1-based index of the current iteration.
- `loop.index0`: 0-based index of the current iteration.
- `loop.first`: `True` if it's the first element.
- `loop.last`: `True` if it's the last element.

### Condition Syntax

Use `{% if condition %}`, optional `{% else %}`, and `{% endif %}` for branching. Negation can be done with `not`.

```text
{% if loop.last %}
This is the end.
{% else %}
Not the end yet.
{% endif %}
```

```text
{% if not loop.first %},{% endif %}
```

### Variable Syntax

Use `{{ expression }}` to substitute values. You can traverse dictionaries or objects using dot notation:

```text
{{ version }}
{{ artifact.filename }}
{{ loop.index }}
```

---

## Filters (Escaping)

Filters are applied using the pipe symbol `|`. They ensure the output conforms safely to various file formats.

- `json`: Serializes the value as a complete JSON value (adds surrounding double quotes for string values, handles numbers/lists/booleans/null).
- `json_escape`: Serializes only the escaped content of a string without outer quotes (useful when placing variables inside manually written quotes in a JSON template).
- `xml`: Escapes characters for XML/HTML text nodes (`&`, `<`, `>`, `"`, `'`).
- `csv`: Escapes cells according to RFC 4180 (doubles quotes and encloses in double quotes if a comma, double quote, or newline is present).
- `tsv`: Escapes cells by converting backslashes, tabs, and newlines to `\\`, `\t`, and `\n` respectively.

### Difference between `json` and `json_escape`

- `{{ value | json }}`: For string `hello "world"`, emits `"hello \"world\""`.
- `{{ value | json_escape }}`: For string `hello "world"`, emits `hello \"world\"`.

---

## Running Smoke Tests

You can run the lightweight validation and smoke checks locally without GitHub Actions:

```bash
python3 ci-cd-helpers-xtazy/scripts/smoke_test_result_files.py
```
