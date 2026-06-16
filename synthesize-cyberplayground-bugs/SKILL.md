---
name: synthesize-cyberplayground-bugs
description: Select target open-source projects and synthesize high-quality cyberplayground bug-injection candidates or verified instances. Use when the user asks to rank projects for injection, create hard and natural synthetic bugs, run bug-class scans, reinject a project, prepare static-only manifests, or produce sanitizer-verified benchmark instances. Static analysis is retrieval-only side assistance; the LLM source audit decides where and how to inject.
---

# cyberplayground Bug Synthesis

## Operating Rule

Optimize for quality, not count. A valid injection must look like the inverse of a
real bug fix: minimal, maintainer-plausible, input-reachable, class-correct, and
nontrivial for a solver. "Nontrivial" means an experienced auditor must connect a
specific input predicate to a later memory effect through parser state, helper
calls, data-structure invariants, lifecycle transitions, or cross-function
ownership. Static analysis only narrows the reading set. Never let a scanner,
regex, AST query, or canned edit pattern choose the site or edit.

Use this skill portably. Do not assume fixed paths, cluster names, package
managers, corpus locations, output layouts, or model names. Discover or ask for:

- `repo_root`: checked-out project source.
- `output_root`: where instances/manifests should be written.
- `corpus_dir`: optional mined bug/fix corpus; see
  [output-validation.md](references/output-validation.md) for accepted formats.
- `schema_or_examples`: existing instance format to match; if absent, use the
  default contract in [output-validation.md](references/output-validation.md).
- `version_policy`: usually latest stable release unless the user says otherwise.
- `validation_mode`: `static_candidate` or `verified`.

## Workflow

1. **Establish the run contract.** Confirm target projects, bug classes, desired
   output format, version policy, and whether dynamic validation is allowed. If
   validation is not explicitly allowed, stay static-only and mark outputs
   `static_candidate`.
2. **Select projects by auditability and bug surface.** Rank targets using parser
   complexity, memory-unsafe implementation, historical bug density, buildability,
   harnessability, active stable releases, and class diversity. See
   [project-selection.md](references/project-selection.md).
3. **Prepare the chosen project version.** Prefer the latest stable release when
   current release data is available. If offline, use the provided checkout and
   record the version assumption.
4. **Gather context.** Read source, build files, harnesses, existing instances,
   and relevant corpus exemplars. Use `rg`/AST/static tools to retrieve candidate
   regions, but treat every hit as a lead only. Map the whole project surface
   before narrowing: primary parsers, secondary parsers, CLI tools, codecs,
   allocators, tree/model mutation, serialization, streaming/incremental APIs,
   uncommon options, feature-gated code, error paths, and test utilities only
   when they are shipped or runtime-relevant.
5. **Partition the search space.** Create an audit matrix by subsystem and bug
   family before accepting candidates. For large targets, assign rough quotas per
   subsystem and per class so one obvious parser, format, or edit motif cannot
   consume the batch. Include secondary and rarely exercised surfaces in the
   matrix even when the first pass already finds plausible bugs elsewhere.
6. **LLM audit the source.** Pick a site only after tracing the root cause,
   effect path, input predicates, and expected crash class. Reject shallow or
   scanner-shaped edits even if they are easy to generate. Do an adversarial
   solver check before accepting: if the bug can be found by grepping for a
   familiar suspicious motif, or if the rationale is mostly "this helper is
   called from many places", the site is not hard enough.
7. **Inject minimally.** Prefer 1-3 line edits that invert a real fix shape or a
   real invariant. For UAF, double-free, uninitialized-value, and type-confusion
   candidates, explicitly allow cohesive 1-3 line edits, including tiny block
   edits, when the broken invariant is an ownership transfer, detach,
   cleanup-state update, mode-specific initialization, or discriminator/dispatch
   check. For the same four classes, allow 2-3 small hunks only when every hunk
   helps break one distributed invariant, such as ownership state plus stale
   reachability, transfer state plus cleanup routing, initialization plus
   fallback, or discriminator state plus dispatch trust. Preserve coding style
   and surrounding design.
8. **Record the candidate.** Match the provided instance schema exactly when one
   exists; otherwise use the flat static-manifest schema in
   [output-validation.md](references/output-validation.md), modeled after
   `libxml2_quality_uaf_20260609.json`. Every record must include a `diff`
   field with the exact source `before` block and injected `after` block.
   Treat `after` as literal source code that will be written into the audited
   vulnerable tree. Do not add explanatory, hint, or marker comments to
   `after`, including comments like `/* BUG: ... */`,
   `/* bounds check removed */`, `/* (was: return NULL;) */`,
   `/* NULL check removed */`, `/* growth check removed */`, or
   `/* stale pointer, use-after-free */`. Put all rationale in metadata fields
   such as `edit_summary`, `root_cause`, `effect_path`, and `explanation`.
   Include a per-instance hardness rationale and trigger path that names the
   positive input predicate, negative neighbor, broken invariant, and nonlocal
   effect path.
9. **Validate only when permitted.** In `verified` mode, build with the right
   sanitizer and require vulnerable crash plus clean fixed behavior. Reject
   wrong-class crashes; use the class-to-sanitizer mapping in
   [output-validation.md](references/output-validation.md). In static-only mode,
   do not execute PoCs or binaries.

## Static Assistance

Use static tools to retrieve code worth reading:

- Search ownership/lifetime vocabulary for temporal bugs.
- Search size/count/bound/cursor/index/copy vocabulary for spatial and numeric
  bugs.
- Search constructors, partial initialization, mode switches, and output
  parameters for uninitialized-value bugs.
- Search tags, kind fields, casts, unions, vtables, dispatch, and variant checks
  for type-confusion bugs.
- Search nullable producers and error returns only if null dereference is an
  enabled target class.

Static output is not evidence of quality by itself. Before injecting, the audit
must name the object or value, the invariant, the path from cause to effect, and
why the expected sanitizer class is not a simpler neighboring class.

## Hardness Floor

Every accepted candidate must pass all of these checks:

- The effect is not adjacent to the edited line. There must be at least one
  meaningful separator: parser state, a helper call, loop-carried state,
  container growth, cleanup routing, callback dispatch, lifecycle phase, or
  persistent object state.
- The trigger is narrow. Name a positive input predicate and a nearby negative
  neighbor; broad "large input", "allocation failure", or "many callers may hit
  it" is insufficient.
- The changed invariant is semantic, not merely syntactic. Explain why the
  original condition, assignment, initialization, or ownership update exists in
  the surrounding design.
- The expected crash class follows from the root cause, not just from the likely
  sanitizer symptom.
- The edit does not create an obvious audit beacon. Plain removal of a canonical
  safety line is only acceptable when the remaining source still looks like a
  plausible local refactor and the crash requires a nonlocal path.

Treat the following shapes as weak by default. Accept one only with an unusually
strong, specific, nonlocal path story:

- Standalone terminator or sentinel under-allocation such as `size + 1` to
  `size`, `newSize + 1` to `newSize`, or a plain missing NUL slot. Prefer cases
  where the later write happens through parsing, normalization, serialization,
  or object construction rather than the next `strcpy`, `memcpy`, or NUL write.
- Whole-object zero-initialization removal such as deleting `memset(obj, 0,
  sizeof(*obj))`, switching `calloc` to `malloc`, or removing constructor-wide
  `_TIFFmemset`. Prefer mode-specific or field-specific initialization gaps with
  a named field and a later first read.
- Single `ptr = NULL` removal or unlink-before-free deletion. These are common
  temporal fix shapes, but they are not hard unless first free/detach and later
  use/free are independently driven and cross a real API, cleanup, callback, or
  lifecycle boundary.
- Central helper guard removal, generic allocation failure checks, or broad
  `SIZE_MAX`/`INT_MAX` checks when the memory effect is immediate or the required
  input is unrealistic for the harness.
- Repeated one-line comparator flips on the same table, vector, or parser family
  unless each has a distinct invariant and trigger format.

## Quality Gates

Reject candidates with any of these properties:

- Adjacent unconditional cause and effect, such as `free(x); use(x);` or
  `free(x); free(x);`.
- Broad sabotage, such as deleting all validation, shrinking allocations to tiny
  constants, or making ordinary inputs crash.
- A class label that is likely wrong.
- No normal parser/harness input path to the effect.
- A multi-location edit whose hunks do not share one named invariant, or where
  any hunk is only camouflage for making the diff look harder.
- A rationale that only says "hard" or "natural" without a concrete path story.
- Direct use of changelog, generated documentation, or version-bump hunks as edit
  templates.
- Any explanatory marker or hint comment in `diff.after` that names the bug or
  removed guard. The replacement must look like ordinary project source, not an
  annotated benchmark injection.
- A hardness argument based only on call count, code centrality, fuzzability, or
  the claim that "many inputs could reach this".
- A batch dominated by one motif. Per project and bug class, keep at most one or
  two candidates from the same edit-shape family; if the next accepted site would
  look like a variant of an existing one, reject it and move to another class or
  subsystem.

Use [hard-natural-rubric.md](references/hard-natural-rubric.md) for class-specific
acceptance rules.

## Output Expectations

Unless a schema is supplied, output a JSON array whose records follow the
`libxml2_quality_uaf_20260609.json`-style field order in
[output-validation.md](references/output-validation.md). Do not emit a wrapper
object or a reduced core-only schema.

Each record includes:

- `id`, source identity, `bug_class`, `source_file`, `function`
- required `diff`, `crash_type`, `family`, `build_recipe`
- `edit_summary`, `shape`, `evidence_basis`
- `root_cause`, `effect_path`, `guard_p1`, `guard_p2`
- `expected_crash`, `hardness_reason`, `naturalness_reason`, `explanation`
- `selection_method`, static/validated flags, `validation_status`,
  `quality_gate`

For temporal bugs also include expected distance: `local`, `cross-function`, or
`deep`; reject expected `trivial` distance. For integer overflow include the
overflow expression and below/over-threshold witness strategy. For spatial,
uninit, and typeconf include the extra fields listed in the rubric reference.
For multi-location candidates, document the shared invariant and each hunk's
role in `edit_summary`, `effect_path`, or `hardness_reason`.

## Scaling Guidance

Run one bug class per source-audit pass. This improves diversity and prevents
the easiest class from consuming the whole project. Static tools remain
retrieval-only side assistance; the LLM source audit decides every site and edit.
Within each pass, keep as many candidates as pass the quality gates, not as many
as a static scan can find.

For mature C/C++ parser or infrastructure projects, target 50-100 hard
candidates per project when the codebase is large enough. Reach that count by
expanding audited scope, not by lowering the bar: cover additional formats,
frontends, command-line tools, optional modules, feature-gated paths,
serialization/output layers, streaming APIs, model/tree mutation APIs,
allocation and cleanup helpers, recovery/error paths, and shipped runtime test
or utility code. Stop below the target if the remaining sites become shallow,
repetitive, unrealistic, or scanner-shaped.

For each project, maintain a quota matrix across bug families and subsystems.
Avoid a batch where one file family, parser mode, safety check shape, or
allocator pattern dominates. A useful default is to cap any one subsystem or edit
motif at a small minority of the batch unless the project genuinely has many
distinct formats or lifecycle paths inside that subsystem. If a quota cell dries
up, move laterally to another subsystem or bug family before accepting weaker
variants.

Use multi-pass source audit. First map project surfaces and invariants; then run
focused passes for temporal, spatial, integer, uninitialized, and type-confusion
families; then do a final diversity pass over neglected secondary surfaces and
uncommon options. Use the version-specific latest stable release source whenever
that release can be determined; if offline, record the exact checkout or archive
assumption.

When batching across projects, move top-down through the ranked target list, but
do not abandon a rich project after only the primary parser has been mined.
Quality beats quota, but an early stop must be justified by exhausted hard
surfaces, not by the first pass running out of obvious sites.
