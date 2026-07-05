import os
import re
import urllib.parse
from glob import glob

def extract_title_from_md(md_content, fallback_name):
    match = re.search(r'^#\s+(.+)$', md_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return fallback_name

def get_source_files(out_dir, docs_root=None):
    files = []
    docs_dir = None
    
    if docs_root is not None:
        if not os.path.exists(docs_root) or not os.path.isdir(docs_root):
            raise ValueError(f"Specified docs-root does not exist or is not a directory: {docs_root}")
        docs_dir = docs_root
        files = glob(os.path.join(docs_root, "**/*.md"), recursive=True)
        files.extend(glob(os.path.join(docs_root, "LICENSE*")))
        files.extend(glob(os.path.join(docs_root, "COPYING*")))
        files.extend(glob("LICENSE*"))
        files.extend(glob("COPYING*"))
    else:
        if os.path.exists("docs") and os.path.isdir("docs"):
            docs_dir = "docs"
            files = glob("docs/**/*.md", recursive=True)
            files.extend(glob("docs/LICENSE*"))
            files.extend(glob("docs/COPYING*"))
            files.extend(glob("LICENSE*"))
            files.extend(glob("COPYING*"))
        else:
            files = glob("*.md")
            files.extend(glob("LICENSE*"))
            files.extend(glob("COPYING*"))
        
    unique_files = {}
    for f in files:
        abs_path = os.path.abspath(f)
        if os.path.isfile(abs_path):
            if f"{os.sep}{out_dir}{os.sep}" in abs_path or abs_path.endswith(os.sep + out_dir) or "target" in abs_path or ".temp_api_docs" in abs_path:
                continue
            unique_files[abs_path] = f
            
    sorted_paths = list(unique_files.keys())
    
    def sort_key(path):
        base = os.path.basename(path).lower()
        name, ext = os.path.splitext(base)
        if name in ["readme", "index"]:
            return (0, name)
        if name.startswith("license") or name.startswith("copying"):
            return (2, name)
        return (1, name)
        
    sorted_paths.sort(key=sort_key)
    return docs_dir, [unique_files[p] for p in sorted_paths]

def build_menu_items(docs_dir, source_files):
    menu_items = []
    for src_path in source_files:
        rel_path = os.path.relpath(src_path, docs_dir if docs_dir else ".")
        name_no_ext = os.path.splitext(rel_path)[0]
        
        title = name_no_ext.replace("-", " ").replace("_", " ").title()
        if title.lower() in ["index", "readme"]:
            title = "Home"

        try:
            with open(src_path, "r") as f:
                content = f.read()
                title = extract_title_from_md(content, title)
        except Exception:
            pass

        if name_no_ext.lower() in ["index", "readme"]:
            target_name = "index.html"
        else:
            safe_target = name_no_ext.replace(os.sep, "_")
            target_name = f"{safe_target}.html"
            
        menu_items.append({
            "title": title,
            "target": target_name,
            "src_path": src_path
        })
        
    return menu_items

def rewrite_markdown_links(md_text, current_src_path, menu_items, current_target, span=None):
    def replace_link(match):
        text = match.group("text")
        url = match.group("url")
        
        if url.startswith(("http://", "https://", "mailto:", "ftp:")):
            return match.group(0)
            
        if "#" in url:
            link_path, fragment = url.split("#", 1)
            fragment_str = f"#{fragment}"
        else:
            link_path = url
            fragment_str = ""
            
        link_path = urllib.parse.unquote(link_path)
        
        # Try resolving relative to current file's directory
        abs_link_path = os.path.abspath(os.path.join(os.path.dirname(current_src_path), link_path))
        
        # If it doesn't exist and we have a span, try resolving relative to original Rust file's directory
        if not os.path.exists(abs_link_path) and span:
            span_file = span.get("filename")
            if span_file:
                abs_link_path = os.path.abspath(os.path.join(os.path.dirname(span_file), link_path))
                
        # Find matching menu item
        matched_item = None
        for mi in menu_items:
            if os.path.abspath(mi["src_path"]) == abs_link_path:
                matched_item = mi
                break
                
        if matched_item:
            current_dir = os.path.dirname(current_target)
            rel_path = os.path.relpath(matched_item["target"], current_dir)
            rel_path = rel_path.replace(os.sep, "/")
            return f"[{text}]({rel_path}{fragment_str})"
            
        return match.group(0)
        
    pattern = r'\[(?P<text>[^\]]*)\]\((?P<url>[^)]+)\)'
    return re.sub(pattern, replace_link, md_text)

def get_visibility_badge(item):
    if not item:
        return ""
    vis = item.get("visibility")
    kind = ""
    if "inner" in item:
        kind = list(item["inner"].keys())[0]
        
    if kind in ["variant", "impl"] or vis == "public":
        return ""
        
    if vis in ["crate", "default"] or (isinstance(vis, dict) and "restricted" in vis):
        tooltip = "private"
        if vis == "crate":
            tooltip = "pub(crate)"
        elif isinstance(vis, dict) and "restricted" in vis:
            path = vis["restricted"].get("path", "")
            tooltip = f"pub(in {path})"
            
        return (
            f'<span class="visibility-lock" title="{tooltip}">'
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round" class="lock-icon">'
            '<rect x="6" y="10" width="12" height="9" rx="1.5"></rect>'
            '<path d="M8 10V7a4 4 0 0 1 8 0v3"></path>'
            '<circle cx="12" cy="13" r="1.2"></circle>'
            '<path d="M12 14.2v2"></path>'
            '</svg>'
            '</span>'
        )
    return ""

