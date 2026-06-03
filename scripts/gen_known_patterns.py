#!/usr/bin/env python3
"""Generate instance manifests for projects where local _inject.json files
are sparse, using known injection patterns from SESSION_HANDOFF.md.

Appends to instances/ alongside seed_instances.py output.
"""

import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "instances"
OUTPUT_DIR.mkdir(exist_ok=True)

# Known working lua injection patterns (from SESSION_HANDOFF.md, 80% hit rate)
LUA_PATTERNS = [
    {"file": "lgc.c", "before": "i < cl->nupvalues", "after": "i <= cl->nupvalues",
     "crash_type": "heap-buffer-overflow", "explanation": "Loop-bound off-by-one in GC upvalue traversal — iterates one past the end of the closure's upvalue array."},
    {"file": "lgc.c", "before": "i < asize", "after": "i <= asize",
     "crash_type": "heap-buffer-overflow", "explanation": "Loop-bound off-by-one in GC array part traversal — reads one slot past the end of the table's array portion."},
    {"file": "lgc.c", "before": "i < f->sizek", "after": "i <= f->sizek",
     "crash_type": "heap-buffer-overflow", "explanation": "Loop-bound off-by-one in GC constants traversal — marks one past the end of the proto's constant array."},
    {"file": "ltable.c", "before": "i < sizenode(t)", "after": "i <= sizenode(t)",
     "crash_type": "heap-buffer-overflow", "explanation": "Loop-bound off-by-one in hash table traversal — accesses one node past the end of the node array."},
    {"file": "lvm.c", "before": "i < nup", "after": "i <= nup",
     "crash_type": "heap-buffer-overflow", "explanation": "Loop-bound off-by-one in VM upvalue initialization — copies one extra upvalue past the allocation."},
    {"file": "lgc.c", "before": "i < f->sizeupvalues", "after": "i <= f->sizeupvalues",
     "crash_type": "heap-buffer-overflow", "explanation": "Loop-bound off-by-one in GC upvalue descriptor traversal — marks past the upvalue array end."},
    {"file": "lgc.c", "before": "i < f->sizep", "after": "i <= f->sizep",
     "crash_type": "heap-buffer-overflow", "explanation": "Loop-bound off-by-one in GC proto traversal — marks one past the child proto array end."},
    {"file": "lgc.c", "before": "i < f->sizelocvars", "after": "i <= f->sizelocvars",
     "crash_type": "heap-buffer-overflow", "explanation": "Loop-bound off-by-one in GC local variable traversal — marks past the locvar array end."},
    {"file": "lvm.c", "before": "n > 0", "after": "n >= 0",
     "crash_type": "heap-buffer-overflow", "explanation": "Bounds-check weakening in VM — allows one extra iteration when n decrements to 0, reading/writing past buffer."},
    {"file": "lparser.c", "before": "fs->np >= f->sizep", "after": "fs->np > f->sizep",
     "crash_type": "heap-buffer-overflow", "explanation": "Bounds-check weakening in parser — allows writing one proto past the allocated array before resize triggers."},
]

# Known cjson injection patterns
CJSON_PATTERNS = [
    {"file": "cJSON.c", "line": 350,
     "before": "number_c_string = (unsigned char *) input_buffer->hooks.allocate(number_string_length + 1);",
     "after": "number_c_string = (unsigned char *) input_buffer->hooks.allocate(number_string_length);",
     "crash_type": "heap-buffer-overflow",
     "explanation": "Removing +1 for null terminator means the NUL write goes one byte past the allocation."},
    {"file": "cJSON.c",
     "before": "if ((input_buffer->offset + sizeof(\"\")) >= input_buffer->length)",
     "after": "if ((input_buffer->offset + sizeof(\"\")) > input_buffer->length)",
     "crash_type": "heap-buffer-overflow",
     "explanation": "Off-by-one boundary check — allows reading exactly at buffer end."},
    {"file": "cJSON.c",
     "before": "output_pointer = ensure(output_buffer, input_pointer - input_buffer + 5 + fmt_len);",
     "after": "output_pointer = ensure(output_buffer, input_pointer - input_buffer + 4 + fmt_len);",
     "crash_type": "heap-buffer-overflow",
     "explanation": "Undersized ensure for unicode escape — allows print to write one byte past allocation."},
    {"file": "cJSON.c",
     "before": "if (input_buffer->depth >= CJSON_NESTING_LIMIT)",
     "after": "if (input_buffer->depth > CJSON_NESTING_LIMIT)",
     "crash_type": "stack-buffer-overflow",
     "explanation": "Nesting limit off-by-one — allows one extra level of recursion past the stack limit."},
    {"file": "cJSON.c",
     "before": "output = (char*) hooks->allocate(default_buffer_size);",
     "after": "output = (char*) hooks->allocate(default_buffer_size - 1);",
     "crash_type": "heap-buffer-overflow",
     "explanation": "Print buffer undersized by 1 — first print operation can overflow."},
    {"file": "cJSON.c",
     "before": "newbuffer = (unsigned char*)p->hooks.reallocate(p->buffer, newsize);",
     "after": "newbuffer = (unsigned char*)p->hooks.reallocate(p->buffer, newsize - 1);",
     "crash_type": "heap-buffer-overflow",
     "explanation": "Realloc undersized by 1 — subsequent writes overflow the print buffer."},
    {"file": "cJSON.c",
     "before": "new_item->valuestring = (char*) cJSON_strdup((const unsigned char*)string, &global_hooks);",
     "after": "new_item->valuestring = (char*) hooks->allocate(strlen(string));",
     "crash_type": "heap-buffer-overflow",
     "explanation": "Replacing strdup with strlen-only allocation omits NUL terminator — strcpy overflows by 1."},
    {"file": "cJSON.c",
     "before": "if (buffer_at_offset(input_buffer)[0] != ':')",
     "after": "if (buffer_at_offset(input_buffer)[0] == ':')",
     "crash_type": "heap-buffer-overflow",
     "explanation": "Logic inversion in object parsing — accepts malformed objects, causing uninitialized pointer use."},
    {"file": "cJSON.c",
     "before": "if (can_access_at_index(input_buffer, 0))",
     "after": "if (1)",
     "crash_type": "heap-buffer-overflow",
     "explanation": "Removing bounds check allows reading past input buffer end."},
    {"file": "cJSON.c",
     "before": "output_pointer = ensure(output_buffer, (size_t)(output_length + sizeof(\"\")));",
     "after": "output_pointer = ensure(output_buffer, (size_t)(output_length));",
     "crash_type": "heap-buffer-overflow",
     "explanation": "String print buffer undersized — missing NUL terminator space causes 1-byte overflow."},
]
PCRE2_PATTERNS = [
    {"file": "src/pcre2_compile.c", "before": "if (cb->parens_depth >= limit)", "after": "if (cb->parens_depth > limit)",
     "crash_type": "stack-buffer-overflow", "explanation": "Bounds-check weakening — allows one extra level of parenthesis nesting past the stack-based recursion limit."},
    {"file": "src/pcre2_match.c", "before": "if (Frdepth >= cb->heap_limit)", "after": "if (Frdepth > cb->heap_limit)",
     "crash_type": "heap-buffer-overflow", "explanation": "Off-by-one in recursion depth check — allows one extra recursion frame past the heap limit."},
    {"file": "src/pcre2_compile.c", "before": "if (meta >= META_END)", "after": "if (meta > META_END)",
     "crash_type": "heap-buffer-overflow", "explanation": "Meta value check off-by-one — META_END itself is no longer treated as terminal, causing one extra parse step."},
    {"file": "src/pcre2_jit_compile.c", "before": "if (common->start[cc + 1] >= common->start[cc])", "after": "if (common->start[cc + 1] > common->start[cc])",
     "crash_type": "heap-buffer-overflow", "explanation": "JIT compiler bounds check weakened — allows processing of equal-start entries which should be skipped."},
    {"file": "src/pcre2_compile.c", "before": "cb->names_found >= cb->name_entry_size", "after": "cb->names_found > cb->name_entry_size",
     "crash_type": "heap-buffer-overflow", "explanation": "Name table overflow check off-by-one — allows one extra named group past the allocated table."},
    {"file": "src/pcre2_match.c", "before": "if (Feptr >= mb->end_subject)", "after": "if (Feptr > mb->end_subject)",
     "crash_type": "heap-buffer-overflow", "explanation": "Subject boundary check off-by-one — allows reading one byte past the end of the input subject string."},
    {"file": "src/pcre2_compile.c", "before": "if (i >= max_group)", "after": "if (i > max_group)",
     "crash_type": "heap-buffer-overflow", "explanation": "Group number limit check off-by-one — allows allocating group number max_group which indexes past the group array."},
    {"file": "src/pcre2_match.c", "before": "if (Lmin >= Lmax)", "after": "if (Lmin > Lmax)",
     "crash_type": "heap-buffer-overflow", "explanation": "Match repetition limit check off-by-one — allows one extra repetition iteration."},
    {"file": "src/pcre2_compile.c", "before": "if (class_count >= 256)", "after": "if (class_count > 256)",
     "crash_type": "stack-buffer-overflow", "explanation": "Character class count limit off-by-one — allows 257 entries in a 256-slot class bitmap."},
    {"file": "src/pcre2_study.c", "before": "if (recurse_count >= cb->start_pattern[0])", "after": "if (recurse_count > cb->start_pattern[0])",
     "crash_type": "heap-buffer-overflow", "explanation": "Recursion count check off-by-one in study phase — allows one extra recursion past the pattern's expected depth."},
]

# Known zstd injection patterns
ZSTD_PATTERNS = [
    {"file": "lib/decompress/zstd_decompress_block.c", "before": "if (nbSeq > litSize + seqPos)", "after": "if (nbSeq >= litSize + seqPos)",
     "crash_type": "heap-buffer-overflow", "explanation": "Off-by-one in sequence count validation — allows one extra sequence past literal+position bounds."},
    {"file": "lib/decompress/zstd_decompress_block.c", "before": "if (op + length > oend)", "after": "if (op + length >= oend)",
     "crash_type": "heap-buffer-overflow", "explanation": "Output boundary check off-by-one — refuses exactly-fitting writes, causing fallthrough to unbounded copy."},
    {"file": "lib/decompress/huf_decompress.c", "before": "if (op >= oend)", "after": "if (op > oend)",
     "crash_type": "heap-buffer-overflow", "explanation": "Huffman output check off-by-one — allows one write at exactly oend."},
    {"file": "lib/common/fse_decompress.c", "before": "if (symbol >= maxSV1)", "after": "if (symbol > maxSV1)",
     "crash_type": "heap-buffer-overflow", "explanation": "FSE symbol validation off-by-one — allows symbol == maxSV1 which indexes past the symbol table."},
    {"file": "lib/decompress/zstd_decompress_block.c", "before": "if (sequence.matchLength > remaining)", "after": "if (sequence.matchLength >= remaining)",
     "crash_type": "heap-buffer-overflow", "explanation": "Match length boundary off-by-one — rejects exactly-fitting matches, allowing fallthrough."},
    {"file": "lib/decompress/zstd_decompress.c", "before": "if (dctx->fParams.windowSize > maxWindowSize)", "after": "if (dctx->fParams.windowSize >= maxWindowSize)",
     "crash_type": "heap-buffer-overflow", "explanation": "Window size check off-by-one — rejects exactly max-sized windows, changing allocation path."},
    {"file": "lib/compress/zstd_compress.c", "before": "if (srcSize > ZSTD_BLOCKSIZE_MAX)", "after": "if (srcSize >= ZSTD_BLOCKSIZE_MAX)",
     "crash_type": "heap-buffer-overflow", "explanation": "Block size check off-by-one in compression — allows exactly BLOCKSIZE_MAX which overflows internal buffer."},
    {"file": "lib/common/zstd_internal.h", "before": "if (litLength >= WILDCOPY_OVERLENGTH)", "after": "if (litLength > WILDCOPY_OVERLENGTH)",
     "crash_type": "heap-buffer-overflow", "explanation": "Wildcopy length check off-by-one — allows overlength == WILDCOPY_OVERLENGTH to take the fast path with insufficient buffer."},
    {"file": "lib/decompress/zstd_decompress_block.c", "before": "if (nbSeq > maxNbSeq)", "after": "if (nbSeq >= maxNbSeq)",
     "crash_type": "heap-buffer-overflow", "explanation": "Sequence count limit off-by-one — allows exactly maxNbSeq which writes past the sequence buffer."},
    {"file": "lib/decompress/zstd_decompress_block.c", "before": "if (litPtr + litLength > litEnd)", "after": "if (litPtr + litLength >= litEnd)",
     "crash_type": "heap-buffer-overflow", "explanation": "Literal pointer boundary off-by-one — rejects exactly-fitting literal copies, altering control flow."},
]


def generate(project: str, patterns: list[dict], line_base: int = 100):
    instances = []
    for idx, pat in enumerate(patterns):
        inst = {
            "id": f"T1_{project}_{idx+1:04d}",
            "project": project,
            "diff": {
                "file": pat["file"],
                "line": pat.get("line", line_base + idx * 50),
                "before": pat["before"],
                "after": pat["after"],
            },
            "crash_type": pat.get("crash_type", "heap-buffer-overflow"),
            "family": pat.get("family", "F3"),
            "explanation": pat.get("explanation", ""),
        }
        instances.append(inst)
    return instances


def main():
    for project, patterns in [
        ("lua", LUA_PATTERNS),
        ("cjson", CJSON_PATTERNS),
        ("pcre2", PCRE2_PATTERNS),
        ("zstd", ZSTD_PATTERNS),
    ]:
        instances = generate(project, patterns)
        out_file = OUTPUT_DIR / f"{project}.json"
        out_file.write_text(json.dumps(instances, indent=2))
        print(f"{project}: {len(instances)} instances → {out_file}")


if __name__ == "__main__":
    main()
