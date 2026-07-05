#!/usr/bin/env python3
import os
import sys
import json
import shutil
import re
import argparse
from glob import glob

# Import modular components
from utils import extract_title_from_md, get_source_files, build_menu_items
from rust_parser import run_cargo_doc_json, convert_rustdoc_json_to_markdown
from html_builder import build_html_pages, build_api_html_pages, build_source_pages

def parse_args():
    parser = argparse.ArgumentParser(description="Universal Documentation Builder")
    parser.add_argument("--logo", help="Path to logo file or URL")
    parser.add_argument("--styles", help="Path to style JSON or inline JSON string")
    parser.add_argument("--repo-owner", default="", help="GitHub repository owner/org")
    parser.add_argument("--repo-name", default="", help="GitHub repository name")
    parser.add_argument("--subpath", default="", help="Subpath for hosting (e.g., 'docs')")
    parser.add_argument("--out-dir", default="docs-out", help="Output directory")
    parser.add_argument("--crate-name", default="", help="Specific crate to document")
    parser.add_argument("--docs-root", default=None, help="Root directory for markdown docs")
    parser.add_argument("--include-rust-api", default="auto", choices=["true", "false", "auto"],
                        help="Include Rust API docs generation (true, false, or auto if Cargo.toml exists)")
    return parser.parse_args()

def load_style_config(script_dir, repo_owner, styles_arg):
    style = {}
    
    # 1. Default to generic style
    default_style_path = os.path.join(script_dir, "default_style.json")
    if os.path.exists(default_style_path):
        with open(default_style_path, "r") as f:
            style.update(json.load(f))
            
    # 2. Check if xtazy-lang org
    is_xtazy = repo_owner.lower() == "xtazy-lang"
    if is_xtazy:
        xtazy_style_path = os.path.join(script_dir, "xtazy_style.json")
        if os.path.exists(xtazy_style_path):
            with open(xtazy_style_path, "r") as f:
                style.update(json.load(f))

    # 3. Apply custom styles if provided
    if styles_arg:
        try:
            if os.path.exists(styles_arg):
                with open(styles_arg, "r") as f:
                    custom = json.load(f)
            else:
                custom = json.loads(styles_arg)
            style.update(custom)
        except Exception as e:
            print(f"Warning: Could not parse styles input '{styles_arg}': {e}. Using defaults.")
            
    return style, is_xtazy

def resolve_logo(script_dir, logo_arg, is_xtazy):
    import base64
    logo_svg = None
    logo_url = None
    svg_content = None

    if is_xtazy and not logo_arg:
        xtazy_logo_path = os.path.join(script_dir, "xtazy_logo.svg")
        if os.path.exists(xtazy_logo_path):
            with open(xtazy_logo_path, "r") as f:
                svg_content = f.read()

    elif logo_arg:
        if os.path.exists(logo_arg):
            if logo_arg.lower().endswith(".svg"):
                with open(logo_arg, "r") as f:
                    svg_content = f.read()
            else:
                logo_url = logo_arg
        else:
            logo_url = logo_arg

    if svg_content:
        encoded = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
        logo_url = f"data:image/svg+xml;base64,{encoded}"
            
    return logo_svg, logo_url

def main():
    args = parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Load styles
    style_config, is_xtazy = load_style_config(script_dir, args.repo_owner, args.styles)
    print(f"Loaded theme styles. Org is 'xtazy-lang': {is_xtazy}")
    
    # 2. Resolve logo
    logo_svg, logo_url = resolve_logo(script_dir, args.logo, is_xtazy)
    
    # Calculate target output dir based on subpath
    dest_out_dir = args.out_dir
    if args.subpath:
        dest_out_dir = os.path.join(args.out_dir, args.subpath)
        
    if os.path.exists(dest_out_dir):
        shutil.rmtree(dest_out_dir)
    os.makedirs(dest_out_dir, exist_ok=True)
    
    # 3. Find source files
    try:
        docs_dir, source_files = get_source_files(args.out_dir, args.docs_root if args.docs_root else None)
    except ValueError as e:
        raise SystemExit(str(e))
    print(f"Found source files: {source_files}")
    
    menu_items = build_menu_items(docs_dir, source_files)
    
    # 4. Check if Rust docs should be built
    has_api_docs = False
    api_modules_list = []
    item_map = {}
    source_files_set = set()
    index_json = {}
    temp_api_dir = os.path.join(script_dir, ".temp_api_docs")
    if os.path.exists(temp_api_dir):
        shutil.rmtree(temp_api_dir)
        
    should_include_rust = False
    if args.include_rust_api == "true":
        should_include_rust = True
    elif args.include_rust_api == "false":
        should_include_rust = False
    else: # auto
        should_include_rust = os.path.exists("Cargo.toml")

    if should_include_rust:
        if args.include_rust_api == "true" and not os.path.exists("Cargo.toml"):
            raise SystemExit("include-rust-api is set to true, but Cargo.toml does not exist")
        json_path = run_cargo_doc_json(args.crate_name)
        if json_path:
            api_modules_list, item_map, source_files_set, index_json = convert_rustdoc_json_to_markdown(
                json_path, temp_api_dir, args.crate_name, args.repo_owner, args.repo_name
            )
            has_api_docs = True
            print("Rust API documentation structure parsed and generated as Markdown files.")
            
    # 5. Generate search index
    search_data = []
    for item in menu_items:
        try:
            with open(item["src_path"], "r") as f:
                content = f.read()
            clean_content = re.sub(r'<[^>]+>', '', content)
            clean_content = re.sub(r'[#*`_\-\[\]()]', ' ', clean_content)
            clean_content = ' '.join(clean_content.split())
            search_data.append({
                "title": item["title"],
                "url": item["target"],
                "content": clean_content[:2000]
            })
        except Exception as e:
            print(f"Warning: Could not index {item['src_path']} for search: {e}")
            
    if has_api_docs:
        api_md_files = glob(os.path.join(temp_api_dir, "**/*.md"), recursive=True)
        for src_path in api_md_files:
            rel_path = os.path.relpath(src_path, temp_api_dir)
            rel_url_path = rel_path[:-3] + ".html"
            target_url = f"api/{rel_url_path}"
            
            try:
                with open(src_path, "r") as f:
                    content = f.read()
                
                title = extract_title_from_md(content, os.path.splitext(os.path.basename(src_path))[0])
                if title.lower() == "index":
                    # Determine module name if sub-index
                    rel_dir = os.path.dirname(rel_path)
                    if rel_dir:
                        title = f"Module {os.path.basename(rel_dir)}"
                    else:
                        title = "Code Reference"
                else:
                    title = f"API: {title}"
                    
                clean_content = re.sub(r'<[^>]+>', '', content)
                clean_content = re.sub(r'[#*`_\-\[\]()]', ' ', clean_content)
                clean_content = ' '.join(clean_content.split())
                search_data.append({
                    "title": title,
                    "url": target_url,
                    "content": clean_content[:2000]
                })
            except Exception as e:
                print(f"Warning: Could not index API page {src_path} for search: {e}")
                
    search_index_json = json.dumps(search_data)
    
    if style_config.get("docs_home"):
        for item in menu_items:
            if item["target"] == "index.html":
                item["title"] = "Readme"

    # 6. Render main Markdown files
    build_html_pages(
        docs_dir=docs_dir,
        source_files=source_files,
        menu_items=menu_items,
        template_str=None,
        style_config=style_config,
        logo_svg=logo_svg,
        logo_url=logo_url,
        has_api_docs=has_api_docs,
        base_out_dir=dest_out_dir,
        search_index_json=search_index_json,
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        is_xtazy=is_xtazy
    )
    
    # 7. Render API HTML files
    if has_api_docs:
        build_api_html_pages(
            temp_api_dir=temp_api_dir,
            menu_items=menu_items,
            template_str=None,
            style_config=style_config,
            logo_svg=logo_svg,
            logo_url=logo_url,
            base_out_dir=dest_out_dir,
            search_index_json=search_index_json,
            item_map=item_map,
            index_json=index_json,
            repo_owner=args.repo_owner,
            repo_name=args.repo_name,
            is_xtazy=is_xtazy
        )
        
        # Build local source code pages
        build_source_pages(
            source_files=source_files_set,
            template_str=None,
            style_config=style_config,
            logo_svg=logo_svg,
            logo_url=logo_url,
            base_out_dir=dest_out_dir,
            menu_items=menu_items,
            search_index_json=search_index_json,
            repo_owner=args.repo_owner,
            repo_name=args.repo_name,
            is_xtazy=is_xtazy
        )
        shutil.rmtree(temp_api_dir)
        
    # 8. Create subpath redirect if subpath is used, or a root redirect if index.html is missing
    if args.subpath:
        redirect_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="refresh" content="0; url={args.subpath}/index.html">
  <title>Redirecting...</title>
</head>
<body>
  <p>Redirecting to <a href="{args.subpath}/index.html">documentation</a>...</p>
</body>
</html>
"""
        with open(os.path.join(args.out_dir, "index.html"), "w") as f:
            f.write(redirect_html)
    else:
        root_index_path = os.path.join(dest_out_dir, "index.html")
        if not os.path.exists(root_index_path):
            first_target = None
            if menu_items:
                first_target = menu_items[0]["target"]
            elif has_api_docs:
                first_target = "api/index.html"
                
            if first_target:
                redirect_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="refresh" content="0; url={first_target}">
  <title>Redirecting...</title>
</head>
<body>
  <p>Redirecting to <a href="{first_target}">documentation</a>...</p>
</body>
</html>
"""
                with open(root_index_path, "w") as f:
                    f.write(redirect_html)
            
    print(f"Documentation successfully built into {args.out_dir}/")

if __name__ == "__main__":
    main()
