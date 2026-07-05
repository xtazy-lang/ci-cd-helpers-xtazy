#!/usr/bin/env python3
import os
import json
import re
import subprocess
from glob import glob

from html_builder import generate_breadcrumbs_html, generate_link_definitions
from utils import get_visibility_badge

def scan_crate_items(root_id, get_item, crate_name):
    item_map = {}
    
    def traverse_module(mod_id, path_stack):
        mod_item = get_item(mod_id)
        if not mod_item:
            return
            
        rel_url = "/".join(path_stack + ["index.html"]) if path_stack else "index.html"
        item_map[str(mod_id)] = {
            "name": mod_item["name"],
            "kind": "module",
            "path_stack": list(path_stack),
            "rel_url": rel_url,
            "full_path": [crate_name] + path_stack,
            "span": mod_item.get("span")
        }
        
        child_ids = mod_item["inner"]["module"]["items"]
        for c_id in child_ids:
            child = get_item(c_id)
            if not child or child.get("crate_id") != 0:
                continue
                
            kind = list(child["inner"].keys())[0]
            c_name = child["name"]
            
            if kind == "module":
                traverse_module(child["id"], path_stack + [c_name])
            elif kind in ["struct", "enum", "function", "trait", "constant", "type_alias"]:
                prefix_map = {
                    "struct": "struct",
                    "enum": "enum",
                    "function": "fn",
                    "trait": "trait",
                    "constant": "constant",
                    "type_alias": "type"
                }
                prefix = prefix_map[kind]
                item_filename = f"{prefix}.{c_name}.html"
                item_rel_url = "/".join(path_stack + [item_filename]) if path_stack else item_filename
                
                item_map[str(child["id"])] = {
                    "name": c_name,
                    "kind": kind,
                    "path_stack": list(path_stack),
                    "rel_url": item_rel_url,
                    "full_path": [crate_name] + path_stack + [c_name],
                    "span": child.get("span")
                }
                
    traverse_module(root_id, [])
    return item_map

def format_visibility_prefix(vis):
    if not vis:
        return ""
    if vis == "public":
        return "pub "
    if vis == "crate":
        return "pub(crate) "
    if isinstance(vis, dict) and "restricted" in vis:
        path = vis["restricted"].get("path", "")
        clean_path = path.lstrip(":")
        if clean_path:
            return f"pub(in crate::{clean_path}) "
        return "pub(crate) "
    return ""

def get_stable_version(item):
    if not item:
        return None
    attrs = item.get("attrs", [])
    for attr in attrs:
        attr_str = ""
        if isinstance(attr, str):
            attr_str = attr
        elif isinstance(attr, dict) and "other" in attr:
            attr_str = attr["other"]
            
        if not attr_str:
            continue
            
        # e.g. #[stable(feature = "...", since = "1.0.0")]
        match = re.search(r'since\s*=\s*"([^"]+)"', attr_str)
        if match:
            return match.group(1)
        # e.g. #[since("1.0.0")] or #[since = "1.0.0"]
        match = re.search(r'since\s*\(\s*"([^"]+)"\s*\)', attr_str)
        if match:
            return match.group(1)
    return None

def resolve_external_type_url(path):
    parts = path.split("::")
    
    if path == "Option":
        return "https://doc.rust-lang.org/stable/std/option/enum.Option.html"
    if path == "Result":
        return "https://doc.rust-lang.org/stable/std/result/enum.Result.html"
    if path == "String":
        return "https://doc.rust-lang.org/stable/std/string/struct.String.html"
    if path == "Vec":
        return "https://doc.rust-lang.org/stable/std/vec/struct.Vec.html"
    if path == "Box":
        return "https://doc.rust-lang.org/stable/std/boxed/struct.Box.html"
    if path == "PathBuf":
        return "https://doc.rust-lang.org/stable/std/path/struct.PathBuf.html"
    if path == "Path":
        return "https://doc.rust-lang.org/stable/std/path/struct.Path.html"
        
    if parts[0] in ["std", "core", "alloc"]:
        std_mapping = {
            "std::path::Path": "path/struct.Path.html",
            "std::path::PathBuf": "path/struct.PathBuf.html",
            "std::process::Command": "process/struct.Command.html",
            "std::process::Output": "process/struct.Output.html",
            "std::process::ExitStatus": "process/struct.ExitStatus.html",
            "std::fs::File": "fs/struct.File.html",
            "std::io::Error": "io/struct.Error.html",
            "std::io::Result": "io/type.Result.html",
            "std::io::Read": "io/trait.Read.html",
            "std::io::Write": "io/trait.Write.html",
            "std::io::Seek": "io/trait.Seek.html",
            "std::fmt::Debug": "fmt/trait.Debug.html",
            "std::fmt::Display": "fmt/trait.Display.html",
            "std::fmt::Formatter": "fmt/struct.Formatter.html",
            "std::fmt::Result": "fmt/type.Result.html",
            "std::clone::Clone": "clone/trait.Clone.html",
            "std::marker::Copy": "marker/trait.Copy.html",
            "std::marker::Send": "marker/trait.Send.html",
            "std::marker::Sync": "marker/trait.Sync.html",
            "std::marker::Sized": "marker/trait.Sized.html",
            "std::cmp::Eq": "cmp/trait.Eq.html",
            "std::cmp::PartialEq": "cmp/trait.PartialEq.html",
            "std::cmp::Ord": "cmp/trait.Ord.html",
            "std::cmp::PartialOrd": "cmp/trait.PartialOrd.html",
            "std::convert::From": "convert/trait.From.html",
            "std::convert::Into": "convert/trait.Into.html",
            "std::convert::TryFrom": "convert/trait.TryFrom.html",
            "std::convert::TryInto": "convert/trait.TryInto.html",
            "std::ops::Deref": "ops/trait.Deref.html",
            "std::ops::DerefMut": "ops/trait.DerefMut.html",
            "std::time::Duration": "time/struct.Duration.html",
            "std::time::Instant": "time/struct.Instant.html",
            "std::collections::HashMap": "collections/struct.HashMap.html",
            "std::collections::HashSet": "collections/struct.HashSet.html",
        }
        
        full_path = "::".join(parts)
        if full_path in std_mapping:
            return f"https://doc.rust-lang.org/stable/std/{std_mapping[full_path]}"
            
        if len(parts) >= 3:
            module = parts[1]
            name = parts[-1]
            kind = "struct"
            if name in ["Read", "Write", "Seek", "BufRead", "Debug", "Display", "Clone", "Copy", "Send", "Sync", "Sized", "Eq", "PartialEq", "Ord", "PartialOrd", "From", "Into", "Error", "Deref", "DerefMut", "AsRef", "AsMut", "Borrow", "BorrowMut", "Default", "Iterator", "IntoIterator"]:
                kind = "trait"
            elif name in ["Result", "Option", "Ordering", "IpAddr"]:
                kind = "enum"
            return f"https://doc.rust-lang.org/stable/std/{module}/{kind}.{name}.html"
            
    if parts[0] == "clap":
        clap_mapping = {
            "clap::Command": "struct.Command.html",
            "clap::ArgMatches": "struct.ArgMatches.html",
            "clap::Error": "struct.Error.html",
            "clap::Args": "trait.Args.html",
            "clap::Parser": "trait.Parser.html",
            "clap::Subcommand": "trait.Subcommand.html",
        }
        full_path = "::".join(parts)
        if full_path in clap_mapping:
            return f"https://docs.rs/clap/latest/clap/{clap_mapping[full_path]}"
            
        name = parts[-1]
        kind = "struct"
        if name in ["Parser", "Args", "Subcommand", "ValueEnum"]:
            kind = "trait"
        return f"https://docs.rs/clap/latest/clap/{kind}.{name}.html"

    if parts[0] == "serde":
        name = parts[-1]
        kind = "trait" if name in ["Serialize", "Deserialize", "Serializer", "Deserializer"] else "struct"
        return f"https://docs.rs/serde/latest/serde/{kind}.{name}.html"
        
    return None

def highlight_signature_html(sig_html):
    import re
    from pygments import highlight
    from pygments.lexers import RustLexer
    from pygments.formatters import HtmlFormatter
    
    links = []
    def replace_link(match):
        placeholder = f"___LINK_PLACEHOLDER_{len(links)}___"
        links.append((placeholder, match.group(0)))
        return placeholder
        
    raw_sig = sig_html
    raw_sig = raw_sig.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    
    raw_sig_with_placeholders = re.sub(r'<a\s+[^>]*>.*?</a>', replace_link, raw_sig)
    
    highlighted = highlight(raw_sig_with_placeholders, RustLexer(), HtmlFormatter(nowrap=True))
    
    for placeholder, original_link in links:
        highlighted = highlighted.replace(placeholder, original_link)
        
    return highlighted.strip()


def convert_rustdoc_json_to_markdown(json_path, temp_api_dir, crate_name_filter="", repo_owner="", repo_name=""):
    os.makedirs(temp_api_dir, exist_ok=True)
    with open(json_path, "r") as f:
        data = json.load(f)
        
    index = data["index"]
    root_id = str(data["root"])
    crate_name = index[root_id]["name"]
    
    def get_item(item_id):
        return index.get(str(item_id))
        
    item_map = scan_crate_items(root_id, get_item, crate_name)
    
    def get_source_url(item, path_stack):
        span = item.get("span")
        if not span:
            return None
        filename = span["filename"]
        if os.path.isabs(filename):
            return None
        start_line = span["begin"][0]
        depth = len(path_stack)
        relative_prefix = "../" * depth
        return f"{relative_prefix}{filename}.html#L{start_line}"
    
    def format_type_literal(t):
        if not t:
            return "()"
        if isinstance(t, str):
            return t
        if "resolved_path" in t:
            path = t["resolved_path"]["path"]
            path = path.replace("$crate::", "")
            args = t["resolved_path"].get("args")
            if args and "angle_bracketed" in args:
                arg_list = []
                for arg in args["angle_bracketed"].get("args", []):
                    if "type" in arg:
                        arg_list.append(format_type_literal(arg["type"]))
                if arg_list:
                    path += f"<{', '.join(arg_list)}>"
            return path
        if "borrowed_ref" in t:
            ref = t["borrowed_ref"]
            mut_str = "mut " if ref["is_mutable"] else ""
            lifetime_str = f"'{ref['lifetime']} " if ref.get("lifetime") else ""
            return f"&{lifetime_str}{mut_str}{format_type_literal(ref['type'])}"
        if "generic" in t:
            return t["generic"]
        if "primitive" in t:
            return t["primitive"]
        if "tuple" in t:
            return f"({', '.join(format_type_literal(x) for x in t['tuple'])})"
        if "slice" in t:
            return f"[{format_type_literal(t['slice'])}]"
        if "array" in t:
            return f"[{format_type_literal(t['array']['type'])}; {t['array']['len']}]"
        if "raw_ptr" in t:
            ptr = t["raw_ptr"]
            mut_str = "mut" if ptr["is_mutable"] else "const"
            return f"*{mut_str} {format_type_literal(ptr['type'])}"
        return str(t)

    def format_type_html(t, current_path_stack, item_map):
        if not t:
            return "()"
        if isinstance(t, str):
            return t
        if "resolved_path" in t:
            path = t["resolved_path"]["path"]
            path = path.replace("$crate::", "")
            short_name = path.split("::")[-1]
            
            ref_id = str(t["resolved_path"].get("id", ""))
            if ref_id in item_map:
                D = len(current_path_stack)
                relative_prefix = "../" * D
                target_url = relative_prefix + item_map[ref_id]["rel_url"]
                
                args = t["resolved_path"].get("args")
                args_str = ""
                if args and "angle_bracketed" in args:
                    arg_list = []
                    for arg in args["angle_bracketed"].get("args", []):
                        if "type" in arg:
                            arg_list.append(format_type_html(arg["type"], current_path_stack, item_map))
                    if arg_list:
                        args_str = f"&lt;{', '.join(arg_list)}&gt;"
                return f'<a href="{target_url}">{short_name}</a>{args_str}'
            else:
                external_url = resolve_external_type_url(path)
                
                args = t["resolved_path"].get("args")
                args_str = ""
                if args and "angle_bracketed" in args:
                    arg_list = []
                    for arg in args["angle_bracketed"].get("args", []):
                        if "type" in arg:
                            arg_list.append(format_type_html(arg["type"], current_path_stack, item_map))
                    if arg_list:
                        args_str = f"&lt;{', '.join(arg_list)}&gt;"
                        
                if external_url:
                    return f'<a href="{external_url}" target="_blank">{short_name}</a>{args_str}'
                return f"{short_name}{args_str}"
        if "borrowed_ref" in t:
            ref = t["borrowed_ref"]
            mut_str = "mut " if ref["is_mutable"] else ""
            lifetime_str = f"'{ref['lifetime']} " if ref.get("lifetime") else ""
            return f"&amp;{lifetime_str}{mut_str}{format_type_html(ref['type'], current_path_stack, item_map)}"
        if "generic" in t:
            return t["generic"]
        if "primitive" in t:
            p = t["primitive"]
            return f'<a href="https://doc.rust-lang.org/stable/std/primitive.{p}.html" target="_blank">{p}</a>'
        if "tuple" in t:
            return f"({', '.join(format_type_html(x, current_path_stack, item_map) for x in t['tuple'])})"
        if "slice" in t:
            return f"[{format_type_html(t['slice'], current_path_stack, item_map)}]"
        if "array" in t:
            return f"[{format_type_html(t['array']['type'], current_path_stack, item_map)}; {t['array']['len']}]"
        if "raw_ptr" in t:
            ptr = t["raw_ptr"]
            mut_str = "mut" if ptr["is_mutable"] else "const"
            return f"*{mut_str} {format_type_html(ptr['type'], current_path_stack, item_map)}"
        return str(t)

    def format_struct_signature(s, current_path_stack, item_map):
        s_name = s["name"]
        struct_data = s["inner"]["struct"]
        kind = struct_data["kind"]
        vis_prefix = format_visibility_prefix(s.get("visibility"))
        if "plain" in kind:
            field_ids = kind["plain"]["fields"]
            fields = []
            for f_id in field_ids:
                f_item = get_item(f_id)
                if f_item and "struct_field" in f_item["inner"]:
                    f_type = format_type_html(f_item["inner"]["struct_field"], current_path_stack, item_map)
                    f_vis = format_visibility_prefix(f_item.get("visibility"))
                    fields.append(f"    {f_vis}{f_item['name']}: {f_type},")
            if fields:
                return f"{vis_prefix}struct {s_name} {{\n" + "\n".join(fields) + "\n}"
            else:
                return f"{vis_prefix}struct {s_name};"
        elif "tuple" in kind:
            field_ids = kind["tuple"]
            types = []
            for f_id in field_ids:
                f_item = get_item(f_id)
                if f_item and "struct_field" in f_item["inner"]:
                    types.append(format_type_html(f_item["inner"]["struct_field"], current_path_stack, item_map))
            if types:
                return f"{vis_prefix}struct {s_name}({', '.join(types)});"
        return f"{vis_prefix}struct {s_name};"

    def format_enum_signature(e, current_path_stack, item_map):
        e_name = e["name"]
        enum_data = e["inner"]["enum"]
        variant_ids = enum_data["variants"]
        vis_prefix = format_visibility_prefix(e.get("visibility"))
        variants = []
        for v_id in variant_ids:
            v_item = get_item(v_id)
            if v_item:
                v_kind = v_item["inner"]["variant"]
                v_name = v_item["name"]
                kind_val = v_kind["kind"]
                if kind_val == "plain":
                    variants.append(f"    {v_name},")
                elif isinstance(kind_val, dict) and "tuple" in kind_val:
                    types = []
                    for f_id in kind_val["tuple"]:
                        f_item = get_item(f_id)
                        if f_item and "struct_field" in f_item["inner"]:
                            types.append(format_type_html(f_item["inner"]["struct_field"], current_path_stack, item_map))
                    variants.append(f"    {v_name}({', '.join(types)}),")
                elif isinstance(kind_val, dict) and "struct" in kind_val:
                    fields = []
                    for f_id in kind_val["struct"]["fields"]:
                        f_item = get_item(f_id)
                        if f_item and "struct_field" in f_item["inner"]:
                            f_type = format_type_html(f_item["inner"]["struct_field"], current_path_stack, item_map)
                            fields.append(f"        {f_item['name']}: {f_type},")
                    variants.append(f"    {v_name} {{\n" + "\n".join(fields) + "\n    },")
        if variants:
            return f"{vis_prefix}enum {e_name} {{\n" + "\n".join(variants) + "\n}"
        return f"{vis_prefix}enum {e_name};"

    def format_function_signature(fn, current_path_stack, item_map):
        fn_name = fn["name"]
        inner_fn = fn["inner"]["function"]
        vis_prefix = format_visibility_prefix(fn.get("visibility"))
        inputs = [f"{arg[0]}: {format_type_html(arg[1], current_path_stack, item_map)}" for arg in inner_fn["sig"]["inputs"]]
        ret = format_type_html(inner_fn["sig"]["output"], current_path_stack, item_map)
        ret_str = f" -> {ret}" if ret != "()" else ""
        header = inner_fn.get("header", {})
        quals = []
        if header.get("async"): quals.append("async")
        if header.get("const"): quals.append("const")
        if header.get("unsafe"): quals.append("unsafe")
        qual_str = " ".join(quals) + " " if quals else ""
        return f"{vis_prefix}{qual_str}fn {fn_name}({', '.join(inputs)}){ret_str}"

    def format_trait_signature(t, current_path_stack, item_map):
        t_name = t["name"]
        trait_data = t["inner"]["trait"]
        vis_prefix = format_visibility_prefix(t.get("visibility"))
        unsafe_str = "unsafe " if trait_data.get("is_unsafe") else ""
        items = []
        for item_id in trait_data.get("items", []):
            item = get_item(item_id)
            if item and "function" in item["inner"]:
                inner_fn = item["inner"]["function"]
                inputs = [f"{arg[0]}: {format_type_html(arg[1], current_path_stack, item_map)}" for arg in inner_fn["sig"]["inputs"]]
                ret = format_type_html(inner_fn["sig"]["output"], current_path_stack, item_map)
                ret_str = f" -> {ret}" if ret != "()" else ""
                items.append(f"    fn {item['name']}({', '.join(inputs)}){ret_str};")
        if items:
            return f"{vis_prefix}{unsafe_str}trait {t_name} {{\n" + "\n".join(items) + "\n}"
        return f"{vis_prefix}{unsafe_str}trait {t_name};"

    def format_constant_signature(c, current_path_stack, item_map):
        c_name = c["name"]
        const_data = c["inner"]["constant"]
        vis_prefix = format_visibility_prefix(c.get("visibility"))
        c_type = format_type_html(const_data["type"], current_path_stack, item_map)
        c_expr = const_data["const"]["expr"]
        return f"{vis_prefix}const {c_name}: {c_type} = {c_expr};"

    def format_type_alias_signature(ta, current_path_stack, item_map):
        ta_name = ta["name"]
        ta_data = ta["inner"]["type_alias"]
        vis_prefix = format_visibility_prefix(ta.get("visibility"))
        target_type = format_type_html(ta_data["type"], current_path_stack, item_map)
        params = []
        for param in ta_data.get("generics", {}).get("params", []):
            params.append(param["name"])
        gen_str = f"<{', '.join(params)}>" if params else ""
        return f"{vis_prefix}type {ta_name}{gen_str} = {target_type};"

    def generate_struct_page(s, path_stack):
        s_name = s["name"]
        s_docs = s.get("docs", "")
        
        source_url = get_source_url(s, path_stack)
        source_link = f' <a href="{source_url}" class="source-link">[source]</a>' if source_url else ""
        
        version = get_stable_version(s)
        version_badge = f' <span class="since-version" title="Stable since {version}">since {version}</span>' if version else ""
        
        md = []
        vis_badge = get_visibility_badge(s)
        md.append(generate_breadcrumbs_html(s_name, path_stack, crate_name))
        md.append(f"# {vis_badge}Struct {s_name}{version_badge}{source_link}\n")
        
        sig = format_struct_signature(s, path_stack, item_map)
        highlighted_sig = highlight_signature_html(sig)
        md.append('<div class="item-decl codehilite">')
        md.append(f"<pre><code>{highlighted_sig}</code></pre>")
        md.append("</div>\n")
        
        if s_docs:
            md.append(f"{s_docs}\n")
            
        struct_data = s["inner"]["struct"]
        fields_data = []
        if "plain" in struct_data["kind"]:
            field_ids = struct_data["kind"]["plain"]["fields"]
            for f_id in field_ids:
                f_item = get_item(f_id)
                if f_item:
                    fields_data.append(f_item)
                    
        if fields_data:
            md.append("## Fields\n")
            for f_item in fields_data:
                f_type_str = ""
                if "struct_field" in f_item["inner"]:
                    f_type_str = ": " + format_type_html(f_item["inner"]["struct_field"], path_stack, item_map)
                
                f_badge = get_visibility_badge(f_item)
                md.append(f"### {f_badge}`{f_item['name']}`")
                
                f_vis = format_visibility_prefix(f_item.get("visibility"))
                f_sig = f"{f_vis}{f_item['name']}{f_type_str}"
                f_sig_highlighted = highlight_signature_html(f_sig)
                md.append('<div class="codehilite">')
                md.append(f"<pre><code>{f_sig_highlighted}</code></pre>")
                md.append("</div>\n")
                
                desc = f_item.get("docs", "")
                if desc:
                    md.append(f"{desc}\n")
            md.append("")
            
        impl_ids = struct_data["impls"]
        methods_data = []
        for impl_id in impl_ids:
            impl_item = get_item(impl_id)
            if impl_item and "impl" in impl_item["inner"]:
                impl_data = impl_item["inner"]["impl"]
                if not impl_data["trait"]:
                    for method_id in impl_data["items"]:
                        method_item = get_item(method_id)
                        if method_item and "function" in method_item["inner"]:
                            methods_data.append(method_item)
                            
        if methods_data:
            md.append("## Methods\n")
            for m_item in sorted(methods_data, key=lambda x: x["name"]):
                inner_fn = m_item["inner"]["function"]
                inputs = [f"{arg[0]}: {format_type_html(arg[1], path_stack, item_map)}" for arg in inner_fn["sig"]["inputs"]]
                ret = format_type_html(inner_fn["sig"]["output"], path_stack, item_map)
                ret_str = f" -> {ret}" if ret != "()" else ""
                
                m_vis = format_visibility_prefix(m_item.get("visibility"))
                header = inner_fn.get("header", {})
                quals = []
                if header.get("async"): quals.append("async")
                if header.get("const"): quals.append("const")
                if header.get("unsafe"): quals.append("unsafe")
                qual_str = " ".join(quals) + " " if quals else ""
                
                sig_str = f"{m_vis}{qual_str}fn {m_item['name']}({', '.join(inputs)}){ret_str}"
                
                m_source_url = get_source_url(m_item, path_stack)
                m_source_link = f' <a href="{m_source_url}" class="source-link">[source]</a>' if m_source_url else ""
                
                m_badge = get_visibility_badge(m_item)
                md.append(f"### {m_badge}`{m_item['name']}`{m_source_link}")
                
                sig_highlighted = highlight_signature_html(sig_str)
                md.append('<div class="codehilite">')
                md.append(f"<pre><code>{sig_highlighted}</code></pre>")
                md.append("</div>\n")
                if m_item.get("docs"):
                    md.append(m_item['docs'])
                md.append("")
            md.append("")
            
        md.append(generate_link_definitions(path_stack, item_map))
        
        filename = f"struct.{s_name}.md"
        dest_dir = os.path.join(temp_api_dir, *path_stack)
        with open(os.path.join(dest_dir, filename), "w") as f_out:
            f_out.write("\n".join(md))
 
    def generate_enum_page(e, path_stack):
        e_name = e["name"]
        e_docs = e.get("docs", "")
        
        source_url = get_source_url(e, path_stack)
        source_link = f' <a href="{source_url}" class="source-link">[source]</a>' if source_url else ""
        
        version = get_stable_version(e)
        version_badge = f' <span class="since-version" title="Stable since {version}">since {version}</span>' if version else ""
        
        md = []
        vis_badge = get_visibility_badge(e)
        md.append(generate_breadcrumbs_html(e_name, path_stack, crate_name))
        md.append(f"# {vis_badge}Enum {e_name}{version_badge}{source_link}\n")
        
        sig = format_enum_signature(e, path_stack, item_map)
        highlighted_sig = highlight_signature_html(sig)
        md.append('<div class="item-decl codehilite">')
        md.append(f"<pre><code>{highlighted_sig}</code></pre>")
        md.append("</div>\n")
        
        if e_docs:
            md.append(f"{e_docs}\n")
            
        enum_data = e["inner"]["enum"]
        variants_data = [get_item(v_id) for v_id in enum_data["variants"]]
        variants_data = [v for v in variants_data if v]
        
        if variants_data:
            md.append("## Variants\n")
            for v_item in variants_data:
                v_kind = v_item["inner"]["variant"]
                v_name = v_item["name"]
                kind_val = v_kind["kind"]
                
                v_fields_str = ""
                if isinstance(kind_val, dict) and "tuple" in kind_val:
                    types = []
                    for f_id in kind_val["tuple"]:
                        f_item = get_item(f_id)
                        if f_item and "struct_field" in f_item["inner"]:
                            types.append(format_type_html(f_item["inner"]["struct_field"], path_stack, item_map))
                    v_fields_str = f"({', '.join(types)})"
                elif isinstance(kind_val, dict) and "struct" in kind_val:
                    fields = []
                    for f_id in kind_val["struct"]["fields"]:
                        f_item = get_item(f_id)
                        if f_item and "struct_field" in f_item["inner"]:
                            f_type = format_type_html(f_item["inner"]["struct_field"], path_stack, item_map)
                            fields.append(f"    {f_item['name']}: {f_type},")
                    v_fields_str = " {\n" + "\n".join(fields) + "\n}"
                
                md.append(f"### `{v_name}`")
                
                v_sig = f"{v_name}{v_fields_str}"
                v_sig_highlighted = highlight_signature_html(v_sig)
                md.append('<div class="codehilite">')
                md.append(f"<pre><code>{v_sig_highlighted}</code></pre>")
                md.append("</div>\n")
                
                desc = v_item.get("docs", "")
                if desc:
                    md.append(f"{desc}\n")
            md.append("")
            
        md.append(generate_link_definitions(path_stack, item_map))
        
        filename = f"enum.{e_name}.md"
        dest_dir = os.path.join(temp_api_dir, *path_stack)
        with open(os.path.join(dest_dir, filename), "w") as f_out:
            f_out.write("\n".join(md))
 
    def generate_function_page(fn, path_stack):
        fn_name = fn["name"]
        fn_docs = fn.get("docs", "")
        
        source_url = get_source_url(fn, path_stack)
        source_link = f' <a href="{source_url}" class="source-link">[source]</a>' if source_url else ""
        
        version = get_stable_version(fn)
        version_badge = f' <span class="since-version" title="Stable since {version}">since {version}</span>' if version else ""
        
        md = []
        vis_badge = get_visibility_badge(fn)
        md.append(generate_breadcrumbs_html(fn_name, path_stack, crate_name))
        md.append(f"# {vis_badge}Function {fn_name}{version_badge}{source_link}\n")
        
        sig = format_function_signature(fn, path_stack, item_map)
        highlighted_sig = highlight_signature_html(sig)
        md.append('<div class="item-decl codehilite">')
        md.append(f"<pre><code>{highlighted_sig}</code></pre>")
        md.append("</div>\n")
        
        if fn_docs:
            md.append(f"{fn_docs}\n")
            
        md.append(generate_link_definitions(path_stack, item_map))
        
        filename = f"fn.{fn_name}.md"
        dest_dir = os.path.join(temp_api_dir, *path_stack)
        with open(os.path.join(dest_dir, filename), "w") as f_out:
            f_out.write("\n".join(md))
 
    def generate_trait_page(t, path_stack):
        t_name = t["name"]
        t_docs = t.get("docs", "")
        
        source_url = get_source_url(t, path_stack)
        source_link = f' <a href="{source_url}" class="source-link">[source]</a>' if source_url else ""
        
        version = get_stable_version(t)
        version_badge = f' <span class="since-version" title="Stable since {version}">since {version}</span>' if version else ""
        
        md = []
        vis_badge = get_visibility_badge(t)
        md.append(generate_breadcrumbs_html(t_name, path_stack, crate_name))
        md.append(f"# {vis_badge}Trait {t_name}{version_badge}{source_link}\n")
        
        sig = format_trait_signature(t, path_stack, item_map)
        highlighted_sig = highlight_signature_html(sig)
        md.append('<div class="item-decl codehilite">')
        md.append(f"<pre><code>{highlighted_sig}</code></pre>")
        md.append("</div>\n")
        
        if t_docs:
            md.append(f"{t_docs}\n")
            
        trait_data = t["inner"]["trait"]
        methods_data = []
        for item_id in trait_data.get("items", []):
            item = get_item(item_id)
            if item and "function" in item["inner"]:
                methods_data.append(item)
                
        if methods_data:
            md.append("## Required Methods\n")
            for m_item in sorted(methods_data, key=lambda x: x["name"]):
                inner_fn = m_item["inner"]["function"]
                inputs = [f"{arg[0]}: {format_type_html(arg[1], path_stack, item_map)}" for arg in inner_fn["sig"]["inputs"]]
                ret = format_type_html(inner_fn["sig"]["output"], path_stack, item_map)
                ret_str = f" -> {ret}" if ret != "()" else ""
                
                sig_str = f"fn {m_item['name']}({', '.join(inputs)}){ret_str}"
                
                m_source_url = get_source_url(m_item, path_stack)
                m_source_link = f' <a href="{m_source_url}" class="source-link">[source]</a>' if m_source_url else ""
                
                md.append(f"### `{m_item['name']}`{m_source_link}")
                
                sig_highlighted = highlight_signature_html(sig_str)
                md.append('<div class="codehilite">')
                md.append(f"<pre><code>{sig_highlighted}</code></pre>")
                md.append("</div>\n")
                if m_item.get("docs"):
                    md.append(m_item['docs'])
                md.append("")
            md.append("")
            
        md.append(generate_link_definitions(path_stack, item_map))
        
        filename = f"trait.{t_name}.md"
        dest_dir = os.path.join(temp_api_dir, *path_stack)
        with open(os.path.join(dest_dir, filename), "w") as f_out:
            f_out.write("\n".join(md))
 
    def generate_constant_page(c, path_stack):
        c_name = c["name"]
        c_docs = c.get("docs", "")
        
        source_url = get_source_url(c, path_stack)
        source_link = f' <a href="{source_url}" class="source-link">[source]</a>' if source_url else ""
        
        version = get_stable_version(c)
        version_badge = f' <span class="since-version" title="Stable since {version}">since {version}</span>' if version else ""
        
        md = []
        vis_badge = get_visibility_badge(c)
        md.append(generate_breadcrumbs_html(c_name, path_stack, crate_name))
        md.append(f"# {vis_badge}Constant {c_name}{version_badge}{source_link}\n")
        
        sig = format_constant_signature(c, path_stack, item_map)
        highlighted_sig = highlight_signature_html(sig)
        md.append('<div class="item-decl codehilite">')
        md.append(f"<pre><code>{highlighted_sig}</code></pre>")
        md.append("</div>\n")
        
        if c_docs:
            md.append(f"{c_docs}\n")
            
        md.append(generate_link_definitions(path_stack, item_map))
        
        filename = f"constant.{c_name}.md"
        dest_dir = os.path.join(temp_api_dir, *path_stack)
        with open(os.path.join(dest_dir, filename), "w") as f_out:
            f_out.write("\n".join(md))
 
    def generate_type_alias_page(ta, path_stack):
        ta_name = ta["name"]
        ta_docs = ta.get("docs", "")
        
        source_url = get_source_url(ta, path_stack)
        source_link = f' <a href="{source_url}" class="source-link">[source]</a>' if source_url else ""
        
        version = get_stable_version(ta)
        version_badge = f' <span class="since-version" title="Stable since {version}">since {version}</span>' if version else ""
        
        md = []
        vis_badge = get_visibility_badge(ta)
        md.append(generate_breadcrumbs_html(ta_name, path_stack, crate_name))
        md.append(f"# {vis_badge}Type Alias {ta_name}{version_badge}{source_link}\n")
        
        sig = format_type_alias_signature(ta, path_stack, item_map)
        highlighted_sig = highlight_signature_html(sig)
        md.append('<div class="item-decl codehilite">')
        md.append(f"<pre><code>{highlighted_sig}</code></pre>")
        md.append("</div>\n")
        
        if ta_docs:
            md.append(f"{ta_docs}\n")
            
        md.append(generate_link_definitions(path_stack, item_map))
        
        filename = f"type.{ta_name}.md"
        dest_dir = os.path.join(temp_api_dir, *path_stack)
        with open(os.path.join(dest_dir, filename), "w") as f_out:
            f_out.write("\n".join(md))

    all_modules_list = []
    
    def process_module(mod_id, path_stack):
        mod_item = get_item(mod_id)
        if not mod_item:
            return
            
        mod_name = mod_item["name"]
        mod_docs = mod_item.get("docs", "")
        
        if mod_id != root_id:
            all_modules_list.append("::".join(path_stack))
            
        mod_dir = os.path.join(temp_api_dir, *path_stack)
        os.makedirs(mod_dir, exist_ok=True)
        
        child_ids = mod_item["inner"]["module"]["items"]
        
        submodules = []
        structs = []
        enums = []
        functions = []
        traits = []
        constants = []
        type_aliases = []
        
        for c_id in child_ids:
            child = get_item(c_id)
            if not child or child.get("crate_id") != 0:
                continue
                
            kind = list(child["inner"].keys())[0]
            if kind == "module":
                submodules.append(child)
            elif kind == "struct":
                structs.append(child)
            elif kind == "enum":
                enums.append(child)
            elif kind == "function":
                functions.append(child)
            elif kind == "trait":
                traits.append(child)
            elif kind == "constant":
                constants.append(child)
            elif kind == "type_alias":
                type_aliases.append(child)
                
        md = []
        md.append(generate_breadcrumbs_html(mod_name, path_stack, crate_name, is_module=True))
        if mod_id == root_id:
            md.append(f"# {crate_name.title()} Code Reference\n")
        else:
            md.append(f"# Module {mod_name}\n")
            
        if mod_docs:
            md.append(f"{mod_docs}\n")
            
        if submodules:
            md.append("## Modules\n")
            for m in sorted(submodules, key=lambda x: x["name"]):
                desc = m.get("docs", "").split("\n")[0] if m.get("docs") else ""
                badge = get_visibility_badge(m)
                md.append(f"- **{badge}[{m['name']}]({m['name']}/index.html)**: {desc}")
            md.append("")
            
        if structs:
            md.append("## Structs\n")
            for s in sorted(structs, key=lambda x: x["name"]):
                desc = s.get("docs", "").split("\n")[0] if s.get("docs") else ""
                badge = get_visibility_badge(s)
                md.append(f"- **{badge}[{s['name']}](struct.{s['name']}.html)**: {desc}")
            md.append("")
            
        if enums:
            md.append("## Enums\n")
            for e in sorted(enums, key=lambda x: x["name"]):
                desc = e.get("docs", "").split("\n")[0] if e.get("docs") else ""
                badge = get_visibility_badge(e)
                md.append(f"- **{badge}[{e['name']}](enum.{e['name']}.html)**: {desc}")
            md.append("")
            
        if traits:
            md.append("## Traits\n")
            for t in sorted(traits, key=lambda x: x["name"]):
                desc = t.get("docs", "").split("\n")[0] if t.get("docs") else ""
                badge = get_visibility_badge(t)
                md.append(f"- **{badge}[{t['name']}](trait.{t['name']}.html)**: {desc}")
            md.append("")
            
        if functions:
            md.append("## Functions\n")
            for fn in sorted(functions, key=lambda x: x["name"]):
                desc = fn.get("docs", "").split("\n")[0] if fn.get("docs") else ""
                badge = get_visibility_badge(fn)
                md.append(f"- **{badge}[{fn['name']}](fn.{fn['name']}.html)**: {desc}")
            md.append("")
            
        if constants:
            md.append("## Constants\n")
            for c in sorted(constants, key=lambda x: x["name"]):
                desc = c.get("docs", "").split("\n")[0] if c.get("docs") else ""
                badge = get_visibility_badge(c)
                md.append(f"- **{badge}[{c['name']}](constant.{c['name']}.html)**: {desc}")
            md.append("")
            
        if type_aliases:
            md.append("## Type Aliases\n")
            for ta in sorted(type_aliases, key=lambda x: x["name"]):
                desc = ta.get("docs", "").split("\n")[0] if ta.get("docs") else ""
                badge = get_visibility_badge(ta)
                md.append(f"- **{badge}[{ta['name']}](type.{ta['name']}.html)**: {desc}")
            md.append("")
            
        md.append(generate_link_definitions(path_stack, item_map))
        
        filename = "index.md"
        with open(os.path.join(mod_dir, filename), "w") as f_out:
            f_out.write("\n".join(md))
            
        for m in submodules:
            process_module(m["id"], path_stack + [m["name"]])
            
        for s in structs:
            generate_struct_page(s, path_stack)
            
        for e in enums:
            generate_enum_page(e, path_stack)
            
        for fn in functions:
            generate_function_page(fn, path_stack)
            
        for t in traits:
            generate_trait_page(t, path_stack)
            
        for c in constants:
            generate_constant_page(c, path_stack)
            
        for ta in type_aliases:
            generate_type_alias_page(ta, path_stack)
            
    source_files_set = set()
    for item in index.values():
        span = item.get("span")
        if span and span.get("filename"):
            fn = span["filename"]
            if not os.path.isabs(fn):
                source_files_set.add(fn)

    # Scan filesystem for all other source files in src/
    if os.path.exists("src") and os.path.isdir("src"):
        for root, _, files in os.walk("src"):
            for file in files:
                if file.endswith(".rs"):
                    rel_path = os.path.join(root, file)
                    source_files_set.add(rel_path)

    process_module(root_id, [])
    return all_modules_list, item_map, source_files_set, index

def run_cargo_doc_json(crate_name):
    print("Generating Rust API documentation structure using cargo doc JSON...")
    cmd = ["cargo", "doc", "--no-deps"]
    env = os.environ.copy()
    env["RUSTC_BOOTSTRAP"] = "1"
    env["RUSTDOCFLAGS"] = "-Z unstable-options --output-format json"
    
    if crate_name:
        cmd.extend(["-p", crate_name])
        
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    if result.returncode != 0:
        print("Error generating cargo doc JSON output:")
        print(result.stderr)
        return None
        
    json_files = glob("target/doc/*.json")
    if json_files:
        if crate_name:
            for jf in json_files:
                if crate_name.replace("-", "_") in os.path.basename(jf):
                    return jf
        return json_files[0]
    return None

