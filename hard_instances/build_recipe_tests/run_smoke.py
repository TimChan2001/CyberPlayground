#!/usr/bin/env python3
"""Smoke-test CyberPlayground build recipes against local hard-corpus sources.

The test uses the same recipe contract as the server:

    SRC, OUT, SAN, HARNESS, COMMON

Each project source is copied to a scratch directory before running the recipe so
the original release trees stay clean.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / "hard_instances" / "build_recipe_tests"
RECIPE_DIR = ROOT / "build_recipes"
COMMON_DIR = ROOT / "common"
WORK_DIR = TEST_ROOT / "work"
LOG_DIR = TEST_ROOT / "logs"
RESULTS_JSON = TEST_ROOT / "results.json"
SUMMARY_MD = TEST_ROOT / "SUMMARY.md"

SAN = "-fsanitize=address -g -O1"
TIMEOUT_SECONDS = 240

SOURCE_CANDIDATES: dict[str, list[str]] = {
    "cgltf": ["/Users/yiyang/cybergym-inject/local/_repos/cgltf"],
    "cjson": ["/Users/yiyang/bug-synthesis/hard/_sources/cjson-v1.7.19"],
    "dr_flac": ["/Users/yiyang/cybergym-inject/local/_repos/dr_wav"],
    "dr_mp3": ["/Users/yiyang/cybergym-inject/local/_repos/dr_wav"],
    "dr_wav": ["/Users/yiyang/cybergym-inject/local/_repos/dr_wav"],
    "expat": ["/Users/yiyang/bug-synthesis/hard/_sources/expat-2.8.1"],
    "ezxml": ["/Users/yiyang/cybergym-inject/local/_repos/ezxml"],
    "freetype": ["/Users/yiyang/bug-synthesis/hard/_sources/freetype-2.14.3"],
    "frozen": ["/Users/yiyang/cybergym-inject/local/_repos/frozen"],
    "giflib": ["/Users/yiyang/bug-synthesis/hard/_sources/giflib-5.2.2"],
    "heatshrink": ["/Users/yiyang/cybergym-inject/local/_repos/heatshrink"],
    "http_parser": ["/Users/yiyang/cybergym-inject/local/_repos/http_parser"],
    "inih": ["/Users/yiyang/cybergym-inject/local/_repos/inih"],
    "iniparser": ["/Users/yiyang/cybergym-inject/local/_repos/iniparser"],
    "jsmn": ["/Users/yiyang/cybergym-inject/local/_repos/jsmn"],
    "json-c": ["/Users/yiyang/bug-synthesis/hard/_sources/json-c-0.18"],
    "json_parser": ["/Users/yiyang/cybergym-inject/local/_repos/json_parser"],
    "lcms": ["/Users/yiyang/lcms"],
    "libconfini": ["/Users/yiyang/cybergym-inject/local/_repos/libconfini"],
    "libcsv": ["/Users/yiyang/cybergym-inject/local/_repos/libcsv"],
    "libpng": ["/Users/yiyang/bug-synthesis/hard/_sources/libpng-1.6.58"],
    "libtiff": ["/Users/yiyang/cybergym-static-src/tiff-4.7.1"],
    "libucl": ["/Users/yiyang/bug-synthesis/hard/_sources/libucl-0.9.4"],
    "libxml2": ["/Users/yiyang/cybergym-static-src/libxml2-v2.15.3"],
    "lua": ["/Users/yiyang/bug-synthesis/hard/_sources/lua-5.5.0/src"],
    "lz4": ["/Users/yiyang/bug-synthesis/hard/_sources/lz4-1.10.0"],
    "md4c": ["/Users/yiyang/cybergym-inject/local/_repos/md4c"],
    "miniz": ["/Users/yiyang/cybergym-inject/local/_repos/miniz"],
    "mjson": ["/Users/yiyang/bug-synthesis/hard/_sources/mjson-1.2.7"],
    "nanosvg": ["/Users/yiyang/cybergym-inject/local/_repos/nanosvg"],
    "oniguruma": ["/Users/yiyang/bug-synthesis/hard/_sources/onig-6.9.10"],
    "parson": ["/Users/yiyang/cybergym-inject/local/_repos/parson"],
    "pcre2": ["/Users/yiyang/bug-synthesis/hard/_sources/pcre2-pcre2-10.47"],
    "slre": ["/Users/yiyang/cybergym-inject/local/_repos/slre"],
    "stb": ["/Users/yiyang/cybergym-inject/local/_repos/stb"],
    "tomlc99": ["/Users/yiyang/cybergym-inject/local/_repos/tomlc99"],
    "utf8proc": ["/Users/yiyang/cybergym-inject/local/_repos/utf8proc"],
    "yyjson": ["/Users/yiyang/cybergym-inject/local/_repos/yyjson"],
    "zlib": ["/Users/yiyang/bug-synthesis/hard/_sources/zlib-1.3.2"],
    "zstd": ["/Users/yiyang/bug-synthesis/hard/_sources/zstd-1.5.7"],
}

SOURCE_REVISIONS: dict[str, dict[str, str]] = {
    "cgltf": {"kind": "git_commit", "revision": "85cd62382dfea638278962690cf515023f33ed00"},
    "cjson": {"kind": "git_commit", "revision": "c859b25da02955fef659d658b8f324b5cde87be3"},
    "dr_flac": {"kind": "git_commit", "revision": "243e26ffa08a24dc8ae2e7a8c57123d9e504690c"},
    "dr_mp3": {"kind": "git_commit", "revision": "243e26ffa08a24dc8ae2e7a8c57123d9e504690c"},
    "dr_wav": {"kind": "git_commit", "revision": "243e26ffa08a24dc8ae2e7a8c57123d9e504690c"},
    "expat": {"kind": "release_tag", "revision": "R_2_8_1"},
    "ezxml": {"kind": "git_commit", "revision": "dcb17484da2591e42c739598729fe5bdf687cca6"},
    "freetype": {"kind": "release_tag", "revision": "VER-2-14-3"},
    "frozen": {"kind": "git_commit", "revision": "a42fc3365d7d4e96a5be146b88870dabc794bbc8"},
    "giflib": {"kind": "release_archive", "revision": "giflib-5.2.2"},
    "heatshrink": {"kind": "git_commit", "revision": "7d419e1fa4830d0b919b9b6a91fe2fb786cf3280"},
    "http_parser": {"kind": "git_commit", "revision": "ec8b5ee63f0e51191ea43bb0c6eac7bfbff3141d"},
    "inih": {"kind": "git_commit", "revision": "577ae2dee1f0d9c2d11c7f10375c1715f3d6940c"},
    "iniparser": {"kind": "git_commit", "revision": "4bef811283e0ec1658c60e09950bd5a1ddc92e4b"},
    "jsmn": {"kind": "git_commit", "revision": "25647e692c7906b96ffd2b05ca54c097948e879c"},
    "json-c": {"kind": "release_tag", "revision": "json-c-0.18-20240915"},
    "json_parser": {"kind": "git_commit", "revision": "8ac4477ad3e63dc107e17ad49484edaa17d18d35"},
    "lcms": {"kind": "git_commit", "revision": "21c582a594fe5279f90c0b93437c398f93bf62b0"},
    "libconfini": {"kind": "git_commit", "revision": "607241689ff0da8b88bb63fb293dc7efa4770f0d"},
    "libcsv": {"kind": "git_commit", "revision": "b1d5212831842ee5869d99bc208a21837e4037d5"},
    "libpng": {"kind": "release_tag", "revision": "v1.6.58"},
    "libtiff": {"kind": "release_tag", "revision": "v4.7.1"},
    "libucl": {"kind": "release_tag", "revision": "0.9.4"},
    "libxml2": {"kind": "release_tag", "revision": "v2.15.3"},
    "lua": {"kind": "release_archive", "revision": "lua-5.5.0"},
    "lz4": {"kind": "release_tag", "revision": "v1.10.0"},
    "md4c": {"kind": "git_commit", "revision": "81b871f917ec97b94322f3890fc12f0657ed3d94"},
    "miniz": {"kind": "git_commit", "revision": "5cf1e56a9c968c11fdd1a6414f3a95f84314c437"},
    "mjson": {"kind": "release_tag", "revision": "1.2.7"},
    "nanosvg": {"kind": "git_commit", "revision": "5cefd9847949af6df13f65027fd43af5a7513633"},
    "oniguruma": {"kind": "release_tag", "revision": "v6.9.10"},
    "parson": {"kind": "git_commit", "revision": "ba29f4eda9ea7703a9f6a9cf2b0532a2605723c3"},
    "pcre2": {"kind": "release_tag", "revision": "pcre2-10.47"},
    "slre": {"kind": "git_commit", "revision": "9075c67cad47d62ba4a4f8f452ae46bb21124f7b"},
    "stb": {"kind": "git_commit", "revision": "31c1ad37456438565541f4919958214b6e762fb4"},
    "tomlc99": {"kind": "git_commit", "revision": "29076dfd095bbbbd50a3c1b2760d29f4b83e74ac"},
    "utf8proc": {"kind": "git_commit", "revision": "b3e0f28adaec943ac25e3e27514dd6037e7a022e"},
    "yyjson": {"kind": "git_commit", "revision": "f0fbeae7cc40218fd1af310391cdf83cfc1abff1"},
    "zlib": {"kind": "git_commit", "revision": "da607da739fa6047df13e66a2af6b8bec7c2a498"},
    "zstd": {"kind": "release_tag", "revision": "v1.5.7"},
}


def project_names() -> list[str]:
    projects = json.loads((ROOT / "hard_instances" / "projects.json").read_text())
    return sorted(projects)


def first_existing(paths: list[str]) -> Path | None:
    for raw in paths:
        p = Path(raw)
        if p.exists():
            return p
    return None


def copy_source(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)

    def ignore(_: str, names: list[str]) -> set[str]:
        ignored = {
            ".git",
            "build-cg",
            "build-debug",
            "cmake-build-debug",
            "compile_commands.json",
        }
        return {name for name in names if name in ignored}

    shutil.copytree(src, dst, ignore=ignore, ignore_dangling_symlinks=True)


def write_harness(path: Path) -> None:
    path.write_text(
        "#include <stddef.h>\n"
        "#include <stdint.h>\n\n"
        "int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {\n"
        "    (void)data;\n"
        "    (void)size;\n"
        "    return 0;\n"
        "}\n"
    )


def write_nproc(path: Path) -> None:
    path.write_text("#!/usr/bin/env sh\nprintf '2\\n'\n")
    path.chmod(0o755)


def run_one(project: str, recipe_name: str) -> dict:
    recipe = RECIPE_DIR / f"{recipe_name}.sh"
    source = first_existing(SOURCE_CANDIDATES.get(project, []))
    result = {
        "project": project,
        "recipe": str(recipe.relative_to(ROOT)) if recipe.exists() else "",
        "source_kind": SOURCE_REVISIONS.get(project, {}).get("kind", ""),
        "source_revision": SOURCE_REVISIONS.get(project, {}).get("revision", ""),
        "status": "not_run",
        "elapsed_seconds": 0.0,
        "reason": "",
    }

    if not recipe.exists():
        result["status"] = "missing_recipe"
        result["reason"] = f"no recipe at build_recipes/{recipe_name}.sh"
        return result
    if source is None:
        result["status"] = "missing_source"
        result["reason"] = "no local source candidate configured/found"
        return result

    project_work = WORK_DIR / project
    src_copy = project_work / "src"
    harness = project_work / "harness.c"
    out = project_work / "a.out"
    fake_bin = project_work / "bin"
    log = LOG_DIR / f"{project}.log"

    project_work.mkdir(parents=True, exist_ok=True)
    fake_bin.mkdir(parents=True, exist_ok=True)
    write_nproc(fake_bin / "nproc")
    copy_source(source, src_copy)
    write_harness(harness)

    env = os.environ.copy()
    env.update({
        "SRC": str(src_copy),
        "OUT": str(out),
        "SAN": SAN,
        "HARNESS": str(harness),
        "COMMON": str(COMMON_DIR),
        "JOBS": "2",
        "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
    })

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            ["bash", str(recipe)],
            env=env,
            cwd=str(project_work),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        output = proc.stdout
        result["status"] = "pass" if proc.returncode == 0 and out.exists() else "fail"
        result["reason"] = f"exit={proc.returncode}, out_exists={out.exists()}"
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        result["status"] = "timeout"
        result["reason"] = f"timeout after {TIMEOUT_SECONDS}s"
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - t0, 3)

    log.write_text(output)
    return result


def write_outputs(results: list[dict]) -> None:
    RESULTS_JSON.write_text(json.dumps(results, indent=2) + "\n")
    counts: dict[str, int] = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    lines = [
        "# Build Recipe Smoke Test Summary",
        "",
        f"Total hard-corpus projects: {len(results)}",
        "",
        "| status | count |",
        "|---|---:|",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"| {status} | {count} |")
    lines.extend([
        "",
        "| project | status | reason | elapsed |",
        "|---|---|---|---:|",
    ])
    for item in results:
        lines.append(
            f"| {item['project']} | {item['status']} | "
            f"{item['reason'].replace('|', '/')} | {item['elapsed_seconds']} |"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n")


def main() -> int:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    projects = json.loads((ROOT / "hard_instances" / "projects.json").read_text())
    results = [
        run_one(project, projects[project].get("build_recipe", project))
        for project in sorted(projects)
    ]
    write_outputs(results)
    print(json.dumps({r["status"]: sum(1 for x in results if x["status"] == r["status"]) for r in results}, indent=2))
    return 0 if all(r["status"] in {"pass", "missing_recipe", "missing_source"} for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
