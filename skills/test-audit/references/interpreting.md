# Interpreting the matrix

## Surviving mutants: equivalent or a real gap?

A mutant is **equivalent** if no input can tell it apart from the original. Classic shapes:
- A boundary flip inside a clamp or guard that returns the boundary value anyway
  (`if x < lo: return lo` → `x <= lo`).
- Mutating dead or defensive code that the invariants make unreachable. That may be a
  `proof-simplify` candidate.
- An arithmetic change that is cancelled downstream, for example by rounding.

Everything else is a **real gap**. Name the smallest assertion that would kill it, and
the partition or boundary it belongs to. Real gaps in critical code are findings, even in
an audit about *reducing* tests. Report them. Do not silently add tests.

## Zero-signal tests

A test is zero-signal when it kills no mutant in scope. Before calling it dead, check:
- Does it exercise code outside `--src` (config, templates, SQL, other packages)? Then
  widen the scope or mark it out of scope.
- Is it the only test at a real boundary where the mutation operators have no mutant (for
  example, string formatting)? Then it may still be valuable. Protect it with `--keep`
  and note why.
- Does it assert nothing (a `no-assertion` smell)? Then it is dead for certain.

## Pseudo-tested functions (extreme mutation)

With `--operators extreme`, a surviving "empty body of f()" mutant means **no test notices
f doing nothing** (Niedermayr et al.: 11% of unit-tested methods and 35% of system-tested
methods). Either f has no observable effect (dead code, `proof-simplify`), or every test
of it is weak.

## History mutants

A mutant with `op: "history"` is a real bug from the git log, re-introduced into HEAD.
- **Killed:** the suite catches a bug that actually happened. The certificate will preserve that.
- **Survived:** the suite would not catch that bug again today. That is the most important
  weakness finding there is.

## Duplicates vs subsumed vs jointly covered

- **Duplicate:** an identical kill set to a retained test. The safest removal, and usually
  a copy-paste.
- **Subsumed:** a strict subset of one retained test. Usually a weaker version of a
  stronger test.
- **Jointly covered:** needs two or more retained tests to replace it. It is still
  certified, but it has the most probation value.
