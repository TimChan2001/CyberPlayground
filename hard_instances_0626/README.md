# hard_instances_0626

Conservative clearly-hard/natural export generated from `/Users/yiyang/bug-synthesis` on 2026-06-26, with the 2026-06-29 existing-project DF/UAF/intover append merged in.

Selection policy:

- Keep only records with concrete injection diffs.
- First dedupe exact repeated manifests by project plus normalized diff.
- Then dedupe same root cause by project, bug class, source file, function, source line, and normalized original `diff.before`; injected `diff.after` values are ignored so same allocation/check variants collapse.
- Use conservative classification: below-bar beats borderline, borderline beats clearly. Only groups remaining clearly hard enough are exported.

Files:

- `bugs.json`: 3467 selected rich static-manifest records.
- `by_project/`: project splits.
- `by_class/`: bug-class splits.
- `clearly-hard-enough/bugs.json`: same 3467-record selected set.
- `projects.json`: project metadata derived from selected records.
- `MANIFEST.json`: counts and dedupe policy.
