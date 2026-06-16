# Project Selection

Use this reference when ranking target projects for bug synthesis.

## Primary Ranking Factors

Score projects on:

- **Input complexity:** parsers, codecs, interpreters, protocol stacks,
  document/image/archive/database formats, regex engines, bytecode runtimes, and
  crypto/ASN.1/X.509 logic are high-value surfaces.
- **Memory-risk implementation:** C and C++ usually rank highest; mixed unsafe
  components can qualify if the harness reaches them.
- **Historical evidence:** CVEs, sanitizer reports, mined corpus coverage, and
  upstream fix patterns indicate realistic bug surfaces.
- **Harnessability:** a normal file, packet, script, query, or document should
  exercise the library without API misuse.
- **Buildability:** stable build system, sanitizer compatibility, available
  dependencies, and reasonable build time.
- **Release policy:** prefer latest stable releases. If release data is stale or
  unavailable, record the checkout/tag/commit assumption.
- **Bug-class breadth:** projects supporting multiple classes rank above projects
  that only support one easy class.
- **Audit density:** code should have enough structure to hide nontrivial bugs
  but not be so large or platform-bound that each candidate is unauditable.

## Known-Good Seed Targets

When local build or harness recipes already exist, seed the shortlist from those
projects before re-ranking from scratch. Still verify the current release,
dependencies, and harness reachability for the requested run.

High-throughput seeds from prior CyberGym-style C harness work:

- `lua`, `cjson`, `tomlc99`, `giflib`, `stb_image`
- `oniguruma`, `pcre2`, `lz4`, `libucl`, `json-c`
- `libpng`, `freetype`, `expat`, `mbedtls`, `libtiff`, `zstd`

Prefer these only when the requested bug classes match the reachable surface.
For temporal, uninit, or type-confusion work, a slower but richer parser may
outrank a fast single-file target.

## Red Flags

Lower rank or skip projects when:

- The only reachable code is CLI glue or examples.
- The build requires unusual services, devices, credentials, or interactive
  setup.
- The harness must misuse private APIs to reach bugs.
- Most candidate edits are adjacent one-line checks with no path depth.
- Dependencies dominate the crash surface more than the project itself.
- The target has no stable release and no clear commit policy.

## Ranking Output

For each project, provide:

- Rank and project name.
- Language and primary input surface.
- Version or release policy.
- Expected bug classes.
- Build/harness risk.
- Why it should or should not be injected now.
- Any corpus evidence used.

Do not use fabricated CVE counts. If exact current counts matter, verify them
from reliable sources or state that the ranking is qualitative.
