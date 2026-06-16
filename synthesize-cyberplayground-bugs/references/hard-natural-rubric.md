# Hard and Natural Rubric

Use this reference during candidate selection. Static scans provide leads; the
LLM source audit decides.

## Global Candidate Fields

Record:

- `bug_class`
- `evidence_basis`: corpus-backed, skill-backed, or mixed
- `shape`
- `root_cause`
- `effect_path`
- `guard_p1`
- `guard_p2`
- `expected_crash`
- `hardness_reason`
- `naturalness_reason`
- `validation_status`

`shape=other` is allowed only with a stronger invariant and path story. Real
corpora often classify most fixes as `other`; do not force a candidate into a
small taxonomy.

## Edit Size Guidance

Prefer the smallest edit that expresses one broken invariant. One-line edits are
acceptable when natural, but UAF, double-free, uninitialized-value, and
type-confusion candidates may use cohesive 1-3 line edits when a tiny block is
the natural fix shape. Do not expand edits merely to look harder, and reject
broad validation removal or unrelated cleanup churn.

For UAF, double-free, uninitialized-value, and type-confusion candidates, 2-3
small hunks are allowed when they jointly break one distributed invariant. Each
hunk must have a named role in the same cause chain; reject independent defects,
camouflage hunks, or edits whose combined effect is broad validation removal.

## Spatial

Natural:

- Boundary invariant is visible: count/capacity, cursor/end,
  length/terminator, table size, truncation limit, or copy length.
- Edit resembles a real off-by-one, missing semantic bound, loop tightening,
  truncation, or size-correction fix.

Hard:

- OOB access appears only at a boundary or specific format combination.
- Check and access are separated by parser state, helper calls, table growth, or
  decoding logic.
- Candidate has a below-boundary neighbor and a boundary/over-boundary input
  strategy.

Reject:

- Removing all validation.
- Huge arbitrary length changes.
- Adjacent check/write with no nontrivial path.

Required extras:

- `boundary_invariant`, `boundary_case`, `neighbor_case`,
  `oob_site_expected`.

## Allocation

Natural:

- Allocation is too small because of a missing terminator, sentinel, separator,
  struct member, array element, or `sizeof` factor.
- Later write is legitimate under the surrounding logic.

Hard:

- Allocation and later write are separated by helper calls, serialization,
  object construction, or cleanup paths.
- Trigger requires exact-fit or format-dependent size.

Reject:

- `malloc(1)`, `malloc(size / 4)`, or obvious sabotage.
- Cases whose real root cause is integer overflow.

## Integer Overflow

Natural:

- Numeric wrap/conversion is the root cause.
- The edit deletes an overflow guard, narrows a type, drops a widening cast,
  removes a semantic bound, or moves validation too late.
- Wrapped value controls allocation, loop bound, table size, index, offset,
  read/write length, or parser limit.

Hard:

- Needs both below-threshold and over-threshold input strategies.
- Wrapped value flows through normal format logic before the memory effect.

Reject:

- Plain under-allocation with no wrap.
- Unsigned wrap with no proof it is unintended.
- ASan-only symptom with no named overflow expression.

Required extras:

- `overflow_expression`, `overflow_kind`, `pre_wrap_value_source`,
  `post_wrap_sink`, `below_threshold_case`, `over_threshold_case`.

## Uninitialized Value

Natural:

- Missing zero-init, initializer, init check, mode-specific assignment, or output
  parameter setup.
- Object remains otherwise valid and reaches generic code.
- A 1-3 line edit may remove or reorder a cohesive initialization/fallback block
  when only specific modes skip the assignment.
- A 2-3 hunk edit may pair skipped mode-specific initialization with a missing
  fallback/default assignment when both are required for the same uninitialized
  field to reach a later generic read.

Hard:

- First meaningful read is later than the constructor/setup site.
- Only some inputs skip initialization.
- Field is not overwritten on all paths.

Reject:

- Local variable read on the next line.
- No concrete first-read path.

Required extras:

- `init_site_expected`, `uninit_storage`, `skip_init_predicate`,
  `first_read_expected`.

## Type Confusion

Natural:

- A tag, enum, kind, class, union discriminator, cast, or dispatch check is
  weakened or moved too late.
- Code uses the object as a neighboring but wrong variant.
- A 1-3 line edit may move or weaken a cohesive discriminator/dispatch block
  when the first wrong-layout access remains separated from the cause.
- A 2-3 hunk edit may pair wrong discriminator preservation with a later
  dispatch/trust decision, as long as the wrong-layout access is still reached
  through normal variant logic.

Hard:

- Cause and effect are separated by traversal, callback dispatch, destructor
  routing, cached reuse, or multi-step parser state.
- Trigger requires a specific mix of object kinds.

Reject:

- Wrong cast adjacent to dereference with no path.
- Null-deref-only outcome.
- Numeric/spatial validation mislabeled as type confusion.

Required extras:

- `actual_type`, `expected_type`, `discriminator`, `wrong_layout_effect`.

## Temporal Distance Taxonomy

- `trivial`: cause and effect are adjacent or unconditional in the same basic
  block, such as immediate `free(x); use(x);` or `free(x); free(x);`. Reject.
- `local`: cause and effect are in the same function but separated by a branch,
  loop, cleanup label, state update, or deferred local traversal. Accept only
  with a concrete path story.
- `cross-function`: first and second event occur across caller/callee,
  destructor, cleanup helper, callback, or API boundary, but within one coherent
  operation.
- `deep`: the stale or duplicated ownership survives across lifecycle phases,
  persistent state, caches, tree links, callbacks, parser iterations, or
  parse/destroy/reuse sequences.

## Temporal: UAF

Natural:

- Freed object remains reachable through owner field, parent/sibling link, cache,
  parser context, callback state, returned object, or refcounted wrapper.
- Inverse fix shape may be missing NULL-out, missing unlink, borrowed pointer,
  weakened lifetime guard, reordered free, or missing detach.
- A 1-3 line edit may remove or reorder a cohesive ownership transfer, detach, or
  stale-link cleanup block when use remains non-adjacent.
- A 2-3 hunk edit may pair broken ownership transfer or detach state with stale
  reachability through a link, cache, callback, or wrapper, as long as the free
  and later use remain non-adjacent.

Hard:

- Prefer `cross-function` or `deep` cause-to-effect distance.
- Free predicate P1 and use predicate P2 should be independently input-driven
  when possible.
- Expected harness often needs parse -> destroy/free -> access again, two
  iterations, callback traversal, cache cleanup, or GC cleanup.

Reject:

- Adjacent `free(x); use(x);`.
- No stale pointer identity.
- Likely double-free or spatial crash instead.

Required extras:

- `distance_expected`, `cause_site_expected`, `effect_site_expected`,
  `conditional_expected`.

## Temporal: Double Free

Natural:

- Two plausible cleanup routes free the same object.
- Common stories: missing NULL-out, missing ownership transfer, dropped
  owned/freed flag, error cleanup plus normal cleanup, manual free plus scoped
  cleanup, container destructor plus member destructor.
- A 1-3 line edit may remove or reorder paired cleanup-state updates when that
  leaves two normal cleanup routes believing they own the same object.
- A 2-3 hunk edit may pair weakened ownership handoff with missing freed/owned
  state updates, as long as the two frees are reached through plausible distinct
  cleanup routes.

Hard:

- Prefer first and second frees in different functions or branches.
- Positive input drives both frees; negatives drive only one path or neither.
- Expected distance should be `cross-function` or `deep` when possible.

Reject:

- Adjacent `free(x); free(x);`.
- Two distinct allocations with similar names.
- Likely UAF rather than double-free.

Required extras:

- `distance_expected`, `first_free_site_expected`,
  `second_free_site_expected`, `conditional_expected`.

## Optional Null Dereference

Use only when the target schema enables this class.

Natural:

- A helper, allocation, lookup, parser factory, or error path can produce NULL,
  and a later path fails to honor that contract.

Hard:

- Producer and dereference are separated by helper calls, state updates, or error
  handling.

Reject:

- Adjacent `p = NULL; p->x`.
- Cases better labeled as temporal, spatial, integer overflow, or type
  confusion.

Required extras:

- `nullable_producer`, `deref_site_expected`, `missing_contract_check`.
