import json
import subprocess
import tempfile
from pathlib import Path
import sys

def run_smoke_test():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # 1. Create version.txt
        version_file = tmp_path / "version.txt"
        version_file.write_text("1.2.3\n", encoding="utf-8")
        
        # 2. Create mock artifact files and directory
        artifact_dir = tmp_path / "dist"
        artifact_dir.mkdir()
        
        art1 = artifact_dir / "dealer-linux-amd64.tar.gz"
        art1.write_text("mock content 1", encoding="utf-8")
        
        art2 = artifact_dir / "dealer-windows-amd64.tar.gz"
        art2.write_text("mock content 2", encoding="utf-8")
        
        # 3. Create mock manifest files and directory
        manifest_dir = artifact_dir / "artifact-manifests"
        manifest_dir.mkdir()
        
        manifest1 = {
            "schema": 1,
            "filename": "dealer-linux-amd64.tar.gz",
            "sha256": "sha256hashlinux",
            "version": "1.2.3",
            "prefix": "dealer",
            "suffix": "linux-amd64",
            "family": "linux",
            "lookup_os": "linux",
            "lookup_arch": ["amd64", "x86_64"],
            "archive_format": "tar.gz",
            "target": "x86_64-unknown-linux-gnu",
            "os": "linux",
            "arch": "amd64"
        }
        (manifest_dir / "linux-amd64.json").write_text(json.dumps(manifest1), encoding="utf-8")
        
        manifest2 = {
            "schema": 1,
            "filename": "dealer-windows-amd64.tar.gz",
            "sha256": "sha256hashwindows",
            "version": "1.2.3",
            "prefix": "dealer",
            "suffix": "windows-amd64",
            "family": "windows",
            "lookup_os": "windows",
            "lookup_arch": ["amd64"],
            "archive_format": "tar.gz",
            "target": "x86_64-pc-windows-msvc",
            "os": "windows",
            "arch": "amd64"
        }
        (manifest_dir / "windows-amd64.json").write_text(json.dumps(manifest2), encoding="utf-8")

        # 4. Create templates directory
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        
        # A. Default TSV template
        tsv_template = templates_dir / "targets.tsv.xtpl"
        tsv_template.write_text(
            "{% for artifact in artifacts %}\n"
            "{% for arch in artifact.lookup_arch %}\n"
            "{{ artifact.family | tsv }}\t{{ artifact.lookup_os | tsv }}_{{ arch | tsv }}\t{{ artifact.suffix | tsv }}\t{{ artifact.sha256 | tsv }}\n"
            "{% endfor %}\n"
            "{% endfor %}\n",
            encoding="utf-8"
        )
        
        # B. CSV template
        csv_template = templates_dir / "artifacts.csv.xtpl"
        csv_template.write_text(
            "filename,sha256,family\n"
            "{% for artifact in artifacts %}\n"
            "{{ artifact.filename | csv }},{{ artifact.sha256 | csv }},{{ artifact.family | csv }}\n"
            "{% endfor %}\n",
            encoding="utf-8"
        )
        
        # C. JSON template
        json_template = templates_dir / "artifacts.json.xtpl"
        json_template.write_text(
            "{\n"
            "  \"version\": {{ version | json }},\n"
            "  \"artifacts\": [\n"
            "    {% for artifact in artifacts %}\n"
            "    {\n"
            "      \"filename\": {{ artifact.filename | json }},\n"
            "      \"sha256\": {{ artifact.sha256 | json }}\n"
            "    }{% if not loop.last %},{% endif %}\n"
            "    {% endfor %}\n"
            "  ]\n"
            "}\n",
            encoding="utf-8"
        )

        # D. Spec file
        spec_file = tmp_path / "spec.json"
        spec = {
            "schema": 1,
            "outputs": [
                {
                    "path": "out_targets.tsv",
                    "template": "templates/targets.tsv.xtpl"
                },
                {
                    "path": "out_artifacts.csv",
                    "template": "templates/artifacts.csv.xtpl"
                },
                {
                    "path": "out_artifacts.json",
                    "template": "templates/artifacts.json.xtpl"
                }
            ]
        }
        spec_file.write_text(json.dumps(spec), encoding="utf-8")

        # 5. Run result_files.py generate
        script_path = Path(__file__).parent / "result_files.py"
        list_out = tmp_path / "output.list"
        cmd = [
            sys.executable, str(script_path), "generate",
            "--spec", str(spec_file),
            "--artifact-dir", str(artifact_dir),
            "--artifact-manifest-dir", str(manifest_dir),
            "--version-file", str(version_file),
            "--list-out", str(list_out)
        ]
        
        subprocess.run(cmd, check=True, cwd=tmpdir)
        
        # 6. Verify outputs
        # Check TSV
        tsv_content = (tmp_path / "out_targets.tsv").read_text(encoding="utf-8")
        expected_tsv = (
            "linux\tlinux_amd64\tlinux-amd64\tsha256hashlinux\n"
            "linux\tlinux_x86_64\tlinux-amd64\tsha256hashlinux\n"
            "windows\twindows_amd64\twindows-amd64\tsha256hashwindows\n"
        )
        assert tsv_content == expected_tsv, f"TSV mismatch:\nGot: {tsv_content!r}\nExpected: {expected_tsv!r}"
        
        # Check CSV
        csv_content = (tmp_path / "out_artifacts.csv").read_text(encoding="utf-8")
        expected_csv = (
            "filename,sha256,family\n"
            "dealer-linux-amd64.tar.gz,sha256hashlinux,linux\n"
            "dealer-windows-amd64.tar.gz,sha256hashwindows,windows\n"
        )
        assert csv_content == expected_csv, f"CSV mismatch:\nGot: {csv_content!r}\nExpected: {expected_csv!r}"
        
        # Check JSON
        json_content = (tmp_path / "out_artifacts.json").read_text(encoding="utf-8")
        parsed_json = json.loads(json_content)
        expected_json = {
            "version": "1.2.3",
            "artifacts": [
                {
                    "filename": "dealer-linux-amd64.tar.gz",
                    "sha256": "sha256hashlinux"
                },
                {
                    "filename": "dealer-windows-amd64.tar.gz",
                    "sha256": "sha256hashwindows"
                }
            ]
        }
        assert parsed_json == expected_json, f"JSON mismatch:\nGot: {json_content!r}\nExpected structure: {expected_json!r}"
        
        # Verify output list
        list_content = list_out.read_text(encoding="utf-8")
        expected_list = "out_targets.tsv\nout_artifacts.csv\nout_artifacts.json\n"
        assert list_content == expected_list, f"List out mismatch:\nGot: {list_content!r}\nExpected: {expected_list!r}"

        # 7. Test workspace escape protection
        escape_spec_file = tmp_path / "escape_spec.json"
        escape_spec = {
            "schema": 1,
            "outputs": [
                {
                    "path": "../escape.tsv",
                    "template": "templates/targets.tsv.xtpl"
                }
            ]
        }
        escape_spec_file.write_text(json.dumps(escape_spec), encoding="utf-8")
        
        res = subprocess.run([
            sys.executable, str(script_path), "generate",
            "--spec", str(escape_spec_file),
            "--artifact-dir", str(artifact_dir),
            "--artifact-manifest-dir", str(manifest_dir),
            "--version-file", str(version_file)
        ], capture_output=True, text=True, cwd=tmpdir)
        assert res.returncode != 0
        assert "output path must not escape the workspace" in res.stderr
        
        # 8. Test missing template fails clearly
        missing_spec_file = tmp_path / "missing_spec.json"
        missing_spec = {
            "schema": 1,
            "outputs": [
                {
                    "path": "out.tsv",
                    "template": "templates/does_not_exist.xtpl"
                }
            ]
        }
        missing_spec_file.write_text(json.dumps(missing_spec), encoding="utf-8")
        
        res = subprocess.run([
            sys.executable, str(script_path), "generate",
            "--spec", str(missing_spec_file),
            "--artifact-dir", str(artifact_dir),
            "--artifact-manifest-dir", str(manifest_dir),
            "--version-file", str(version_file)
        ], capture_output=True, text=True, cwd=tmpdir)
        assert res.returncode != 0
        assert "missing template file" in res.stderr

        # 9. Test malformed spec fails clearly
        malformed_spec_file = tmp_path / "malformed_spec.json"
        malformed_spec_file.write_text("{ malformed json }", encoding="utf-8")
        
        res = subprocess.run([
            sys.executable, str(script_path), "generate",
            "--spec", str(malformed_spec_file),
            "--artifact-dir", str(artifact_dir),
            "--artifact-manifest-dir", str(manifest_dir),
            "--version-file", str(version_file)
        ], capture_output=True, text=True, cwd=tmpdir)
        assert res.returncode != 0
        assert "invalid JSON" in res.stderr

        # 10. Test missing schema fails clearly
        missing_schema_file = tmp_path / "missing_schema.json"
        missing_schema_file.write_text(json.dumps({"outputs": []}), encoding="utf-8")
        res = subprocess.run([
            sys.executable, str(script_path), "generate",
            "--spec", str(missing_schema_file),
            "--artifact-dir", str(artifact_dir),
            "--artifact-manifest-dir", str(manifest_dir),
            "--version-file", str(version_file)
        ], capture_output=True, text=True, cwd=tmpdir)
        assert res.returncode != 0
        assert "missing schema version" in res.stderr

        # 11. Test unsupported schema version fails clearly
        bad_schema_file = tmp_path / "bad_schema.json"
        bad_schema_file.write_text(json.dumps({"schema": 2, "outputs": []}), encoding="utf-8")
        res = subprocess.run([
            sys.executable, str(script_path), "generate",
            "--spec", str(bad_schema_file),
            "--artifact-dir", str(artifact_dir),
            "--artifact-manifest-dir", str(manifest_dir),
            "--version-file", str(version_file)
        ], capture_output=True, text=True, cwd=tmpdir)
        assert res.returncode != 0
        assert "unsupported schema version: 2" in res.stderr
        
        print("Smoke tests passed successfully!")

if __name__ == "__main__":
    run_smoke_test()
