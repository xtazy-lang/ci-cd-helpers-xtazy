#!/usr/bin/env python3
import os
import re
import shutil
import json
import urllib.parse
from glob import glob

import markdown
from jinja2 import Environment, FileSystemLoader

from utils import rewrite_markdown_links, get_visibility_badge

script_dir = os.path.dirname(os.path.abspath(__file__))
env = Environment(loader=FileSystemLoader(script_dir))

def apply_configured_link_rewrites(md_text, back_to_root, style_config):
    rewrites = style_config.get("link_rewrites") or []
    for rewrite in rewrites:
        pattern = rewrite.get("pattern")
        target = rewrite.get("target")
        if not pattern or target is None:
            continue
        resolved_target = target.replace("{back_to_root}", back_to_root)
        md_text = re.sub(pattern, resolved_target, md_text, flags=re.IGNORECASE)
    return md_text

def build_html_pages(docs_dir, source_files, menu_items, template_str, style_config, logo_svg, logo_url, has_api_docs, base_out_dir, search_index_json, repo_owner, repo_name, is_xtazy):
    os.makedirs(base_out_dir, exist_ok=True)
    project_name = os.path.basename(os.getcwd()).replace("-", " ").title()
    template = env.get_template("template.html")
    
    for item in menu_items:
        src_path = item["src_path"]
        target_name = item["target"]
        
        with open(src_path, "r") as f:
            md_text = f.read()
            
        rel_dir = os.path.dirname(target_name)
        depth = len(rel_dir.split(os.sep)) if rel_dir else 0
        back_to_root = "../" * depth if depth > 0 else ""
        
        # Rewrite relative Markdown links to point to .html target files
        md_text = rewrite_markdown_links(md_text, src_path, menu_items, target_name)
        md_text = apply_configured_link_rewrites(md_text, back_to_root, style_config)
        
        html_content = markdown.markdown(md_text, extensions=['extra', 'toc', 'codehilite'])
        
        resolved_logo_url = logo_url
        if logo_url and os.path.exists(logo_url):
            logo_filename = os.path.basename(logo_url)
            dest_logo_path = os.path.join(base_out_dir, logo_filename)
            shutil.copy2(logo_url, dest_logo_path)
            resolved_logo_url = back_to_root + logo_filename
            
        page_menu = []
        for menu_item in menu_items:
            # Skip licenses in main sidebar navigation menu
            basename = os.path.basename(menu_item["src_path"]).lower()
            if basename.startswith("license") or basename.startswith("copying"):
                continue
            page_menu.append({
                "title": menu_item["title"],
                "relative_path": back_to_root + menu_item["target"],
                "active": menu_item["target"] == target_name
            })
            
        if has_api_docs:
            page_menu.append({
                "title": "Code Reference",
                "relative_path": back_to_root + "api/index.html",
                "active": False
            })
            
        logo_alt = style_config.get("logo_alt", project_name)
        logo_href = style_config.get("logo_href", "index.html")
        resolved_logo_href = logo_href if logo_href.startswith(('http://', 'https://', '//')) else back_to_root + logo_href

        rendered_html = template.render(
            page_title=item["title"],
            project_name=project_name,
            styles=style_config,
            logo_svg=logo_svg,
            logo_url=resolved_logo_url,
            logo_alt=logo_alt,
            logo_href=resolved_logo_href,
            menu_items=page_menu,
            has_api_docs=has_api_docs,
            api_docs_path=f"{back_to_root}api/index.html",
            content=html_content,
            search_index_json=search_index_json,
            back_to_root=back_to_root,
            api_sidebar=None,
            is_api_page=False,
            repo_owner=repo_owner,
            repo_name=repo_name,
            is_xtazy=is_xtazy
        )
        
        dest_path = os.path.join(base_out_dir, target_name)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "w") as f:
            f.write(rendered_html)


def generate_breadcrumbs_html(name, path_stack, crate_name, is_module=False):
    D = len(path_stack)
    relative_prefix = "../" * D
    
    parts = []
    if D == 0:
        if is_module:
            return ""
        else:
            parts.append(f'<a href="index.html">{crate_name}</a>')
    else:
        parts.append(f'<a href="{relative_prefix}index.html">{crate_name}</a>')
        
    for i, folder in enumerate(path_stack):
        if is_module and i == len(path_stack) - 1:
            break
        levels_up = D - (i + 1)
        sub_prefix = "../" * levels_up
        parts.append(f'<a href="{sub_prefix}index.html">{folder}</a>')
        
    parts.append(f'<span class="current">{name}</span>')
    
    raw_path = "::".join([crate_name] + path_stack + [name])
    copy_btn = (
        f'<button class="copy-path-btn" data-clipboard-text="{raw_path}" title="Copy path: {raw_path}">'
        '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>'
        '</svg>'
        '</button>'
    )
    return f'<div class="breadcrumbs">{" :: ".join(parts)}{copy_btn}</div>\n'

def generate_link_definitions(page_path_stack, item_map):
    D = len(page_path_stack)
    relative_prefix = "../" * D
    
    defs = []
    seen_keys = set()
    
    for it in item_map.values():
        link_url = relative_prefix + it["rel_url"]
        keys = []
        name = it["name"]
        full_path = it["full_path"]
        
        keys.append(name)
        keys.append("::".join(full_path))
        if len(full_path) > 1:
            keys.append("::".join(full_path[1:]))
            keys.append("crate::" + "::".join(full_path[1:]))
            
        for k in keys:
            if k not in seen_keys:
                seen_keys.add(k)
                defs.append(f"[{k}]: {link_url}")
                
    return "\n" + "\n".join(defs) if defs else ""

def build_api_sidebar(page_path_stack, active_filename, item_map, crate_name, index=None):
    M_stack = page_path_stack
    D = len(M_stack)
    
    parent_link = None
    parent_name = None
    
    if active_filename == "index.html":
        if D > 0:
            parent_name = M_stack[-2] if D > 1 else crate_name
            parent_link = "../index.html"
    else:
        parent_name = M_stack[-1] if D > 0 else crate_name
        parent_link = "index.html"
        
    current_module_path = " :: ".join([crate_name] + M_stack)
    
    submodules = []
    structs = []
    enums = []
    traits = []
    functions = []
    constants = []
    type_aliases = []
    
    # 1. Locate active item to extract its internal outline sections
    active_item_id = None
    for it_id, it in item_map.items():
        filename = os.path.basename(it["rel_url"]) if it["kind"] != "module" else "index.html"
        if it["path_stack"] == page_path_stack and filename == active_filename:
            active_item_id = it_id
            break
            
    active_sections = []
    if index and active_item_id and active_item_id in index:
        raw_item = index[active_item_id]
        kind_keys = list(raw_item.get("inner", {}).keys())
        kind = kind_keys[0] if kind_keys else None
        
        if kind == "struct":
            struct_data = raw_item["inner"]["struct"]
            has_fields = False
            if "plain" in struct_data.get("kind", {}):
                field_ids = struct_data["kind"]["plain"].get("fields", [])
                if field_ids:
                    has_fields = True
            if has_fields:
                active_sections.append({"title": "Fields", "anchor": "#fields"})
                
            has_methods = False
            impl_ids = struct_data.get("impls", [])
            for impl_id in impl_ids:
                impl_item = index.get(str(impl_id))
                if impl_item and "impl" in impl_item["inner"]:
                    impl_data = impl_item["inner"]["impl"]
                    if not impl_data.get("trait"):
                        for method_id in impl_data.get("items", []):
                            method_item = index.get(str(method_id))
                            if method_item and "function" in method_item["inner"]:
                                has_methods = True
                                break
                if has_methods:
                    break
            if has_methods:
                active_sections.append({"title": "Methods", "anchor": "#methods"})
                
        elif kind == "enum":
            enum_data = raw_item["inner"]["enum"]
            if enum_data.get("variants"):
                active_sections.append({"title": "Variants", "anchor": "#variants"})
            has_methods = False
            impl_ids = enum_data.get("impls", [])
            for impl_id in impl_ids:
                impl_item = index.get(str(impl_id))
                if impl_item and "impl" in impl_item["inner"]:
                    impl_data = impl_item["inner"]["impl"]
                    if not impl_data.get("trait"):
                        for method_id in impl_data.get("items", []):
                            method_item = index.get(str(method_id))
                            if method_item and "function" in method_item["inner"]:
                                has_methods = True
                                break
                if has_methods:
                    break
            if has_methods:
                active_sections.append({"title": "Methods", "anchor": "#methods"})
                
        elif kind == "trait":
            trait_data = raw_item["inner"]["trait"]
            has_methods = False
            for item_id in trait_data.get("items", []):
                item = index.get(str(item_id))
                if item and "function" in item["inner"]:
                    has_methods = True
                    break
            if has_methods:
                active_sections.append({"title": "Required Methods", "anchor": "#required-methods"})

    # 2. Iterate and group module members
    for it_id, it in item_map.items():
        it_stack = it["path_stack"]
        it_kind = it["kind"]
        
        filename = os.path.basename(it["rel_url"]) if it_kind != "module" else f"{it['name']}/index.html"
        active = filename == active_filename
        
        raw_item = index.get(it_id) if index else None
        badge = get_visibility_badge(raw_item) if raw_item else ""
        
        if it_stack == M_stack:
            item_entry = {
                "name": it["name"],
                "filename": filename,
                "active": active,
                "badge": badge
            }
            
            if it_kind == "struct":
                structs.append(item_entry)
            elif it_kind == "enum":
                enums.append(item_entry)
            elif it_kind == "trait":
                traits.append(item_entry)
            elif it_kind == "function":
                functions.append(item_entry)
            elif it_kind == "constant":
                constants.append(item_entry)
            elif it_kind == "type_alias":
                type_aliases.append(item_entry)
                
        elif len(it_stack) == D + 1 and it_stack[:-1] == M_stack and it_kind == "module":
            submodules.append({
                "name": it["name"],
                "filename": filename,
                "active": active,
                "badge": badge
            })
            
    submodules.sort(key=lambda x: x["name"])
    structs.sort(key=lambda x: x["name"])
    enums.sort(key=lambda x: x["name"])
    traits.sort(key=lambda x: x["name"])
    functions.sort(key=lambda x: x["name"])
    constants.sort(key=lambda x: x["name"])
    type_aliases.sort(key=lambda x: x["name"])
    
    path_tree_steps = []
    # 1. Crate root step
    path_tree_steps.append({
        "name": crate_name,
        "link": None,
        "active": (D == 0 and active_filename == "index.html"),
        "indent": 0
    })
    
    # 2. Add modules along the path stack
    for i in range(0, D):
        mod_name = M_stack[i]
        is_active = (active_filename == "index.html" and i == D - 1)
        if is_active:
            link = None
        else:
            link = "../" * (D - 1 - i) + "index.html"
            
        path_tree_steps.append({
            "name": mod_name,
            "link": link,
            "active": is_active,
            "indent": i + 1
        })

    return {
        "parent_link": parent_link,
        "parent_name": parent_name,
        "current_module_path": current_module_path,
        "submodules": submodules,
        "structs": structs,
        "enums": enums,
        "traits": traits,
        "functions": functions,
        "constants": constants,
        "type_aliases": type_aliases,
        "active_sections": active_sections,
        "path_tree_steps": path_tree_steps
    }


def build_api_html_pages(temp_api_dir, menu_items, template_str, style_config, logo_svg, logo_url, base_out_dir, search_index_json, item_map, index_json, repo_owner, repo_name, is_xtazy):
    api_out_dir = os.path.join(base_out_dir, "api")
    os.makedirs(api_out_dir, exist_ok=True)
    project_name = os.path.basename(os.getcwd()).replace("-", " ").title()
    template = env.get_template("template.html")
    
    # Pre-scan index for crate name
    crate_name = project_name.lower().replace(" ", "_")
    for it in item_map.values():
        if it["kind"] == "module" and len(it["path_stack"]) == 0:
            crate_name = it["name"]
            break
            
    api_md_files = glob(os.path.join(temp_api_dir, "**/*.md"), recursive=True)
    
    for src_path in api_md_files:
        rel_path = os.path.relpath(src_path, temp_api_dir)
        rel_dir = os.path.dirname(rel_path)
        page_path_stack = rel_dir.split(os.sep) if rel_dir else []
        
        name_no_ext = os.path.splitext(os.path.basename(src_path))[0]
        active_filename = f"{name_no_ext}.html"
        
        with open(src_path, "r") as f:
            md_text = f.read()
            
        depth = 1 + len(page_path_stack)
        back_to_root = "../" * depth
        
        # Find if there is a matching item to extract span
        target_html_path = "/".join(page_path_stack + [active_filename]) if page_path_stack else active_filename
        span = None
        for it in item_map.values():
            if it["rel_url"] == target_html_path:
                span = it.get("span")
                break
                
        # Rewrite relative Markdown links to point to .html target files
        md_text = rewrite_markdown_links(md_text, src_path, menu_items, f"api/{target_html_path}", span)
        md_text = apply_configured_link_rewrites(md_text, back_to_root, style_config)
        
        html_content = markdown.markdown(md_text, extensions=['extra', 'toc', 'codehilite'])
        
        resolved_logo_url = logo_url
        if logo_url and os.path.exists(logo_url):
            logo_filename = os.path.basename(logo_url)
            resolved_logo_url = back_to_root + logo_filename
            
        page_menu = []
        for menu_item in menu_items:
            # Skip licenses in API menu as well
            basename = os.path.basename(menu_item["src_path"]).lower()
            if basename.startswith("license") or basename.startswith("copying"):
                continue
            page_menu.append({
                "title": menu_item["title"],
                "relative_path": back_to_root + menu_item["target"],
                "active": False
            })
            
        page_menu.append({
            "title": "Code Reference",
            "relative_path": back_to_root + "api/index.html",
            "active": True
        })
        
        api_sidebar = build_api_sidebar(page_path_stack, active_filename, item_map, crate_name, index_json)
        
        title = name_no_ext.replace("-", " ").replace("_", " ").title()
        if title.lower() == "index":
            if len(page_path_stack) == 0:
                title = "Code Reference"
            else:
                title = f"Module {page_path_stack[-1]}"
                
        logo_alt = style_config.get("logo_alt", project_name)
        logo_href = style_config.get("logo_href", "index.html")
        resolved_logo_href = logo_href if logo_href.startswith(('http://', 'https://', '//')) else back_to_root + logo_href

        rendered_html = template.render(
            page_title=title,
            project_name=project_name,
            styles=style_config,
            logo_svg=logo_svg,
            logo_url=resolved_logo_url,
            logo_alt=logo_alt,
            logo_href=resolved_logo_href,
            menu_items=page_menu,
            has_api_docs=True,
            api_docs_path=back_to_root + "api/index.html",
            content=html_content,
            search_index_json=search_index_json,
            back_to_root=back_to_root,
            api_sidebar=api_sidebar,
            is_api_page=True,
            repo_owner=repo_owner,
            repo_name=repo_name,
            is_xtazy=is_xtazy
        )
        
        dest_dir = os.path.join(api_out_dir, *page_path_stack)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, active_filename)
        with open(dest_path, "w") as f:
            f.write(rendered_html)


def split_highlighted_lines(highlighted_html):
    raw_lines = highlighted_html.split("\n")
    formatted_lines = []
    open_spans = [] # stack of classes
    
    # We want to find spans and closing spans.
    span_re = re.compile(r'(<span class="([^"]+)">|</span>)')
    
    for line in raw_lines:
        prefix = "".join(f'<span class="{c}">' for c in open_spans)
        
        # Now track spans in the current line
        for match in span_re.finditer(line):
            tag = match.group(1)
            cls = match.group(2)
            if tag == '</span>':
                if open_spans:
                    open_spans.pop()
            else:
                open_spans.append(cls)
                
        suffix = "</span>" * len(open_spans)
        formatted_lines.append(prefix + line + suffix)
        
    return formatted_lines

def build_source_pages(source_files, template_str, style_config, logo_svg, logo_url, base_out_dir, menu_items, search_index_json, repo_owner, repo_name, is_xtazy):
    api_out_dir = os.path.join(base_out_dir, "api")
    project_name = os.path.basename(os.getcwd()).replace("-", " ").title()
    template = env.get_template("template.html")
    
    from pygments import highlight
    from pygments.lexers import RustLexer
    from pygments.formatters import HtmlFormatter
    
    for src_file in sorted(source_files):
        if not os.path.exists(src_file) or not os.path.isfile(src_file):
            continue
            
        with open(src_file, "r") as f:
            raw_code = f.read()
            
        highlighted = highlight(raw_code, RustLexer(), HtmlFormatter(nowrap=True))
        lines = split_highlighted_lines(highlighted)
        if lines and not lines[-1].strip():
            lines.pop()
            
        formatted_lines = []
        for i, line_html in enumerate(lines, 1):
            formatted_lines.append(
                f'<div class="src-line" id="L{i}">'
                f'<a href="#L{i}" class="src-line-number" data-line-number="{i}"></a>'
                f'<code class="src-line-code">{line_html}</code>'
                f'</div>'
            )
            
        content_html = f'<div class="src-code-container codehilite">\n' + '\n'.join(formatted_lines) + '\n</div>'
        
        relative_target = os.path.join("api", f"{src_file}.html")
        depth = len(relative_target.split(os.sep)) - 1
        back_to_root = "../" * depth
        
        resolved_logo_url = logo_url
        if logo_url and os.path.exists(logo_url):
            resolved_logo_url = back_to_root + os.path.basename(logo_url)
            
        page_menu = []
        for menu_item in menu_items:
            basename = os.path.basename(menu_item["src_path"]).lower()
            if basename.startswith("license") or basename.startswith("copying"):
                continue
            page_menu.append({
                "title": menu_item["title"],
                "relative_path": back_to_root + menu_item["target"],
                "active": False
            })
        page_menu.append({
            "title": "Code Reference",
            "relative_path": back_to_root + "api/index.html",
            "active": True
        })
        
        source_files_data = []
        for f in sorted(source_files):
            source_files_data.append({
                "name": f,
                "relative_path": back_to_root + "api/" + f + ".html",
                "active": (f == src_file)
            })
        
        title = f"Source: {src_file}"
        
        logo_alt = style_config.get("logo_alt", project_name)
        logo_href = style_config.get("logo_href", "index.html")
        resolved_logo_href = logo_href if logo_href.startswith(('http://', 'https://', '//')) else back_to_root + logo_href

        rendered_html = template.render(
            page_title=title,
            project_name=project_name,
            styles=style_config,
            logo_svg=logo_svg,
            logo_url=resolved_logo_url,
            logo_alt=logo_alt,
            logo_href=resolved_logo_href,
            menu_items=page_menu,
            has_api_docs=True,
            api_docs_path=back_to_root + "api/index.html",
            content=content_html,
            search_index_json=search_index_json,
            back_to_root=back_to_root,
            api_sidebar=None,
            is_api_page=True,
            repo_owner=repo_owner,
            repo_name=repo_name,
            is_xtazy=is_xtazy,
            is_source_page=True,
            source_files_list=source_files_data,
            back_to_api_index=back_to_root + "api/index.html"
        )
        
        dest_path = os.path.join(base_out_dir, relative_target)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "w") as f:
            f.write(rendered_html)
