#!/usr/bin/env python3
"""Convert NAS export into per-project instance files and update projects.json with pinned commits.

Usage:
    python3 scripts/import_nas.py [--max-per-project 10]
"""

import argparse
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
INSTANCES_DIR = SCRIPT_DIR.parent / "instances"
NAS_EXPORT = INSTANCES_DIR / "nas_export.json"

REPO_URLS = {
    "brotli":    "https://github.com/google/brotli.git",
    "cjson":     "https://github.com/DaveGamble/cJSON.git",
    "cmark":     "https://github.com/commonmark/cmark.git",
    "curl":      "https://github.com/curl/curl.git",
    "expat":     "https://github.com/libexpat/libexpat.git",
    "flac":      "https://github.com/xiph/flac.git",
    "freetype":  "https://github.com/freetype/freetype.git",
    "giflib":    "https://github.com/giflib/giflib.git",
    "harfbuzz":  "https://github.com/harfbuzz/harfbuzz.git",
    "jq":        "https://github.com/jqlang/jq.git",
    "json-c":    "https://github.com/json-c/json-c.git",
    "lcms":      "https://github.com/mm2/Little-CMS.git",
    "libpng":    "https://github.com/pnggroup/libpng.git",
    "libtiff":   "https://github.com/libsdl-org/libtiff.git",
    "libucl":    "https://github.com/vstakhov/libucl.git",
    "libwebp":   "https://github.com/webmproject/libwebp.git",
    "libxml2":   "https://gitlab.gnome.org/GNOME/libxml2.git",
    "libxslt":   "https://gitlab.gnome.org/GNOME/libxslt.git",
    "lua":       "https://github.com/lua/lua.git",
    "lwan":      "https://github.com/lpereira/lwan.git",
    "lz4":       "https://github.com/lz4/lz4.git",
    "mbedtls":   "https://github.com/Mbed-TLS/mbedtls.git",
    "mruby":     "https://github.com/mruby/mruby.git",
    "ndpi":      "https://github.com/ntop/nDPI.git",
    "oniguruma": "https://github.com/kkos/oniguruma.git",
    "pcre2":     "https://github.com/PCRE2Project/pcre2.git",
    "stb_image": "https://github.com/nothings/stb.git",
    "tomlc99":   "https://github.com/cktan/tomlc99.git",
    "wasm3":     "https://github.com/wasm3/wasm3.git",
    "wolfssl":   "https://github.com/wolfSSL/wolfssl.git",
    "yara":      "https://github.com/VirusTotal/yara.git",
    "zstd":      "https://github.com/facebook/zstd.git",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-project", type=int, default=0,
                        help="Max instances per project (0=all)")
    parser.add_argument("--projects", nargs="+", default=None,
                        help="Only import these projects")
    args = parser.parse_args()

    data = json.loads(NAS_EXPORT.read_text())
    projects_meta = {}
    total = 0

    for proj in sorted(data.keys()):
        if args.projects and proj not in args.projects:
            continue

        raw_instances = data[proj]

        # deduplicate by (file, before, after)
        seen = set()
        unique = []
        for inst in raw_instances:
            before = inst["before"]
            after = inst["after"]
            if isinstance(before, list):
                before = "\n".join(before)
                inst["before"] = before
            if isinstance(after, list):
                after = "\n".join(after)
                inst["after"] = after
            key = (inst["file"], before, after)
            if key in seen:
                continue
            seen.add(key)
            unique.append(inst)

        if args.max_per_project:
            unique = unique[:args.max_per_project]

        # find commit (use most common)
        commits = [i.get("commit", "") for i in unique if i.get("commit")]
        commit = max(set(commits), key=commits.count) if commits else "HEAD"

        # build instance list
        instances = []
        for idx, inst in enumerate(unique):
            iid = inst.get("slot_id", f"T1_{proj}_{idx+1:04d}")
            instances.append({
                "id": iid,
                "project": proj,
                "diff": {
                    "file": inst["file"],
                    "line": inst.get("line", 0),
                    "before": inst["before"],
                    "after": inst["after"],
                },
                "crash_type": inst.get("crash_type", ""),
                "family": inst.get("family", ""),
                "explanation": inst.get("explanation", inst.get("description", "")),
            })

        out_file = INSTANCES_DIR / f"{proj}.json"
        out_file.write_text(json.dumps(instances, indent=2))
        print(f"{proj}: {len(instances)} instances → {out_file}")
        total += len(instances)

        projects_meta[proj] = {
            "repo_url": REPO_URLS.get(proj, ""),
            "commit": commit,
            "build_recipe": proj,
            "description": "",
        }

    # update projects.json
    projects_file = INSTANCES_DIR / "projects.json"
    if projects_file.exists():
        existing = json.loads(projects_file.read_text())
        existing.update(projects_meta)
        projects_meta = existing
    projects_file.write_text(json.dumps(projects_meta, indent=2))
    print(f"\nUpdated {projects_file} ({len(projects_meta)} projects)")
    print(f"Total: {total} instances")


if __name__ == "__main__":
    main()
