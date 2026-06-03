#!/usr/bin/env python3
"""Seed the prototype with 50 instances across 5 projects.

Reads _inject.json + _backlog.json from the cybergym-inject tree and
writes normalized instance manifests into cyberplayground/instances/.

Usage:
    python3 scripts/seed_instances.py [--inject-dir /path/to/cybergym-inject]
"""

import argparse
import json
import sys
from pathlib import Path

# 5 projects for the prototype — mix of fast/medium/slow builds
PROTO_PROJECTS = ["lua", "cjson", "oniguruma", "pcre2", "zstd"]
INSTANCES_PER_PROJECT = 10

# Canonical repo URLs (from llm_injector_tier1.py)
PROJECT_META = {
    "lua":       {"repo_url": "https://github.com/lua/lua.git",           "build_recipe": "lua",       "description": "Lua scripting language"},
    "cjson":     {"repo_url": "https://github.com/DaveGamble/cJSON.git", "build_recipe": "cjson",     "description": "Ultralightweight JSON parser"},
    "oniguruma": {"repo_url": "https://github.com/kkos/oniguruma.git",    "build_recipe": "oniguruma", "description": "Regular expression library"},
    "pcre2":     {"repo_url": "https://github.com/PCRE2Project/pcre2.git","build_recipe": "pcre2",     "description": "Perl Compatible Regular Expressions"},
    "zstd":      {"repo_url": "https://github.com/facebook/zstd.git",     "build_recipe": "zstd",      "description": "Zstandard compression"},
    # full list for scaling later
    "mbedtls":   {"repo_url": "https://github.com/Mbed-TLS/mbedtls.git",  "build_recipe": "mbedtls",   "description": "TLS/crypto library"},
    "libpng":    {"repo_url": "https://github.com/pnggroup/libpng.git",    "build_recipe": "libpng",    "description": "PNG reference library"},
    "libtiff":   {"repo_url": "https://github.com/libsdl-org/libtiff.git", "build_recipe": "libtiff",   "description": "TIFF image library"},
    "expat":     {"repo_url": "https://github.com/libexpat/libexpat.git",  "build_recipe": "expat",     "description": "XML parser"},
    "freetype":  {"repo_url": "https://github.com/freetype/freetype.git",  "build_recipe": "freetype",  "description": "Font rendering engine"},
    "brotli":    {"repo_url": "https://github.com/google/brotli.git",      "build_recipe": "brotli",    "description": "Brotli compression"},
    "libwebp":   {"repo_url": "https://github.com/webmproject/libwebp.git","build_recipe": "libwebp",   "description": "WebP image codec"},
    "lz4":       {"repo_url": "https://github.com/lz4/lz4.git",           "build_recipe": "lz4",       "description": "LZ4 compression"},
    "libucl":    {"repo_url": "https://github.com/vstakhov/libucl.git",    "build_recipe": "libucl",    "description": "Universal config library"},
    "giflib":    {"repo_url": "https://github.com/giflib/giflib.git",      "build_recipe": "giflib",    "description": "GIF image library"},
    "lcms":      {"repo_url": "https://github.com/mm2/Little-CMS.git",    "build_recipe": "lcms",      "description": "Color management"},
    "libxml2":   {"repo_url": "https://gitlab.gnome.org/GNOME/libxml2.git","build_recipe": "libxml2",   "description": "XML parser"},
    "libxslt":   {"repo_url": "https://gitlab.gnome.org/GNOME/libxslt.git","build_recipe": "libxslt",  "description": "XSLT processor"},
    "lwan":      {"repo_url": "https://github.com/lpereira/lwan.git",      "build_recipe": "lwan",      "description": "Lightweight web server"},
    "wolfssl":   {"repo_url": "https://github.com/wolfSSL/wolfssl.git",    "build_recipe": "wolfssl",   "description": "TLS library"},
    "wasm3":     {"repo_url": "https://github.com/wasm3/wasm3.git",        "build_recipe": "wasm3",     "description": "WASM interpreter"},
    "ndpi":      {"repo_url": "https://github.com/ntop/nDPI.git",          "build_recipe": "ndpi",      "description": "Deep packet inspection"},
    "yara":      {"repo_url": "https://github.com/VirusTotal/yara.git",    "build_recipe": "yara",      "description": "Pattern matching"},
    "mruby":     {"repo_url": "https://github.com/mruby/mruby.git",        "build_recipe": "mruby",     "description": "Lightweight Ruby"},
    "flac":      {"repo_url": "https://github.com/xiph/flac.git",          "build_recipe": "flac",      "description": "FLAC audio codec"},
    "cmark":     {"repo_url": "https://github.com/commonmark/cmark.git",   "build_recipe": "cmark",     "description": "CommonMark parser"},
    "stb_image": {"repo_url": "https://github.com/nothings/stb.git",       "build_recipe": "stb_image", "description": "Single-header image loader"},
    "tomlc99":   {"repo_url": "https://github.com/cktan/tomlc99.git",      "build_recipe": "tomlc99",   "description": "TOML parser"},
    "jq":        {"repo_url": "https://github.com/jqlang/jq.git",          "build_recipe": "jq",        "description": "JSON processor"},
    "json-c":    {"repo_url": "https://github.com/json-c/json-c.git",      "build_recipe": "json-c",    "description": "JSON C library"},
    "harfbuzz":  {"repo_url": "https://github.com/harfbuzz/harfbuzz.git",   "build_recipe": "harfbuzz",  "description": "Text shaping engine"},
}


def collect_instances(inject_dir: Path) -> dict[str, list[dict]]:
    """Collect _inject.json data from all available sources."""
    by_project: dict[str, list[dict]] = {}

    # source 1: tier1_export/_backlog.json (has file/line but may lack before/after)
    backlog = inject_dir / "tier1_export" / "_backlog.json"
    if backlog.exists():
        data = json.loads(backlog.read_text())
        for proj, instances in data.items():
            for inst in instances:
                if "before" not in inst or "after" not in inst:
                    continue
                inst.setdefault("project", proj)
                by_project.setdefault(proj, []).append(inst)

    # source 2: walk entire inject_dir for _inject.json files with before/after
    for p in inject_dir.rglob("_inject.json"):
        try:
            raw = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if "before" not in raw or "after" not in raw:
            continue
        parent = str(p)
        project = _infer_project(raw, parent)
        if project:
            raw["project"] = project
            raw["source_path"] = str(p)
            by_project.setdefault(project, []).append(raw)

    return by_project


def _infer_project(data: dict, path_str: str) -> str:
    sid = data.get("slot_id", "")
    if sid.startswith("T1_"):
        parts = sid.split("_")
        if len(parts) >= 3:
            return parts[1]
    # try LLM_ prefix in slot id or dirname
    for prefix in ["LLM_"]:
        if prefix in path_str:
            # extract project from LLM_<project>_NNN pattern
            import re
            m = re.search(r"LLM_(\w+?)_\d+", path_str)
            if m:
                candidate = m.group(1).lower()
                if candidate in PROJECT_META:
                    return candidate
    # try matching project name in path
    path_lower = path_str.lower()
    for proj in sorted(PROJECT_META.keys(), key=len, reverse=True):
        if proj in path_lower:
            return proj
    return ""


def deduplicate(instances: list[dict]) -> list[dict]:
    """Dedup by (file, line, before, after)."""
    seen = set()
    result = []
    for inst in instances:
        diff = inst.get("diff", inst)
        key = (diff.get("file", ""), diff.get("line", 0),
               diff.get("before", ""), diff.get("after", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(inst)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inject-dir", type=Path,
                        default=Path.home() / "cybergym-inject")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parent.parent / "instances")
    parser.add_argument("--projects", nargs="+", default=PROTO_PROJECTS)
    parser.add_argument("--per-project", type=int, default=INSTANCES_PER_PROJECT)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # write projects.json
    projects_out = {}
    for proj in PROJECT_META:
        meta = PROJECT_META[proj]
        projects_out[proj] = {
            "repo_url": meta["repo_url"],
            "commit": "HEAD",  # will be pinned on first clone
            "build_recipe": meta["build_recipe"],
            "description": meta["description"],
        }
    projects_file = args.output_dir / "projects.json"
    projects_file.write_text(json.dumps(projects_out, indent=2))
    print(f"wrote {projects_file} ({len(projects_out)} projects)")

    # collect all instances
    all_instances = collect_instances(args.inject_dir)
    print(f"found instances for projects: {list(all_instances.keys())}")

    total = 0
    for proj in args.projects:
        raw = all_instances.get(proj, [])
        if not raw:
            print(f"  {proj}: no instances found, skipping")
            continue

        unique = deduplicate(raw)
        selected = unique[:args.per_project]

        instances = []
        for idx, item in enumerate(selected):
            diff = item.get("diff", item)
            if "before" not in diff or "after" not in diff:
                continue
            inst = {
                "id": item.get("slot_id", f"T1_{proj}_{idx+1:04d}"),
                "project": proj,
                "diff": {
                    "file": diff["file"],
                    "line": diff["line"],
                    "before": diff["before"],
                    "after": diff["after"],
                },
                "crash_type": item.get("crash_type", diff.get("crash_type", "")),
                "family": item.get("family", ""),
                "explanation": item.get("explanation", diff.get("explanation", "")),
            }
            instances.append(inst)

        out_file = args.output_dir / f"{proj}.json"
        out_file.write_text(json.dumps(instances, indent=2))
        print(f"  {proj}: {len(instances)} instances → {out_file}")
        total += len(instances)

    print(f"\ntotal: {total} instances seeded")


if __name__ == "__main__":
    main()
