# Working on pylibmc

How we do things in this project. It is written for everyone who changes the
code, human or LLM agent, and for whoever has to work out why something is the
way it is. If you find it wrong or out of date, fix it in the same pull request
as the change that made it so.

pylibmc is a Python client for memcached: a C extension that wraps libmemcached,
plus a small Python package on top. Releases are wheels and an sdist on PyPI
and GitHub.

## Layout

| Path | What |
|---|---|
| `src/_pylibmcmodule.c`, `.h` | The C extension (`_pylibmc`). Most bugs live here. |
| `src/pylibmc-version.h` | The one source of the version number. `setup.py` and the C module both read it. |
| `src/pylibmc/` | The Python package: `client.py`, `pools.py`, `consts.py`, `autoconf.py`, `test.py`. |
| `tests/` | pytest tests plus `doctests.txt`. `tests/__init__.py` has `PylibmcTestCase` and `get_refcounts`. |
| `docs/` | Sphinx docs. `docs/changelog.rst` is the user-facing change log. |
| `bin/` | `runtests.py` (runs pytest, exits with its status), `with-memcached` (see the pitfalls below). |
| `.github/` | Workflows (`ci.yml`, `cd.yml`), the `setup-python-retry` action, and helper scripts in `.github/scripts`. |

## Building and testing locally

You need libmemcached headers and library (Homebrew: `brew install libmemcached`;
Debian/Ubuntu: `libmemcached-dev`), a `memcached` binary, and pytest.

```sh
python -m venv .venv && . .venv/bin/activate
pip install pytest setuptools
LIBMEMCACHED=/opt/homebrew/opt/libmemcached pip install .   # prefix of the libmemcached to use
```

Build options are in the header of `setup.py`: `LIBMEMCACHED=<prefix>` or
`--with-libmemcached=<dir>`, `ZLIB=<prefix>` / `--with-zlib`, `--with-sasl2`.
Always check which library you actually got:

```sh
python -c "import pylibmc, _pylibmc; print(pylibmc.libmemcached_version, _pylibmc.libmemcached_runtime_version)"
otool -L $(python -c "import _pylibmc; print(_pylibmc.__file__)")   # ldd on Linux
```

We always test the installed package, not the source tree. Start memcached
yourself, wait for it, run pytest from outside the checkout, then stop it:

```sh
memcached -p 11211 -l 127.0.0.1 &
until nc -z 127.0.0.1 11211; do sleep 0.3; done
(cd /tmp && python -m pytest --doctest-modules --doctest-glob='*.txt' /path/to/pylibmc/tests -q)
kill %1
```

### Pitfalls we have already paid for

- **`pip install .` builds in the source tree and reuses old objects.** After a
  build with different flags you silently get the previous object file. Run
  `rm -rf build src/pylibmc.egg-info` before every build. (In zsh, a glob that
  matches nothing aborts the whole command, so keep globs out of that line.)
- **Setting `CFLAGS` replaces the interpreter's optimisation flags, including
  `-DNDEBUG`, so asserts turn on.** That is how an assertion failure on empty
  values (#291) was found. Before changing C code, run the suite on a normal
  build and on a strict one (`CFLAGS="-Wall -Wextra -Wno-unused-parameter"`),
  each from a clean tree.
- **`bin/with-memcached` starts memcached in the background and runs the command
  at once**, so the first tests race its startup and fail with `NotAlive`. Start
  memcached yourself as above.
- **The full suite expects memcached on `127.0.0.1:11211`**
  (`tests/test_autoconf.py` assumes the default port). `MEMCACHED_HOST`,
  `MEMCACHED_PORT` and `MEMCACHED_TYPE` only steer the test client helper.
- **Two libmemcached families behave differently.** 1.0.x is the legacy floor
  (Homebrew, Ubuntu 22.04's apt package). 1.1.x is the maintained fork
  (awesomized/libmemcached; Ubuntu 24.04's apt package is 1.1.4). Timeouts,
  `remove_failed` and other details differ. Test both when you touch C code,
  `setup.py` or anything that depends on libmemcached behaviour.
- **A Homebrew-flavoured pyenv Python used to link the wrong libmemcached**
  because its `LDSHARED` names `-L/opt/homebrew/lib` first. `setup.py` now puts
  the requested prefix first, but still verify with the commands above.

## Writing C code in the extension

- Every `return NULL` needs an exception set. A failed `PyMem_New` or `malloc`
  sets none: call `PyErr_NoMemory()` first.
- Every error path releases what the function owns. Prefer one `cleanup:` label
  and `goto` it instead of early returns. `PyList_Append`,
  `PyObject_SetAttrString` and `PyDict_SetItem` do not steal references, so
  release the temporaries you pass them. `PyModule_AddObject` steals on success;
  `_make_excs` relies on that deliberately.
- libmemcached can return a `NULL` value pointer with length 0 for an empty
  value. `_PylibMC_parse_memcached_value` normalises that once for `get`, `gets`
  and `get_multi`; don't pass raw pointers on.
- Python-visible methods take arbitrary objects. Check the type before using
  macros such as `PyBytes_AS_STRING`; they do not.
- Release the GIL around blocking libmemcached calls and touch no Python object
  while it is released.
- Keep the code buildable across the supported libmemcached and Python ranges
  (guard on `LIBMEMCACHED_VERSION_HEX`). Don't use a C API that only newer
  Pythons have without a shim.
- Keep `assert`s and fix their callers when one fires. They are how latent bugs
  get found.

## Tests

- A bug fix comes with a regression test that fails before the fix and passes
  after it. Say in the PR how you checked that (for example, failing on
  `origin/master`).
- Refcount tests use freshly created objects (`uuid.uuid4().hex`), not literals
  or interned strings, whose counts change for unrelated reasons. A single
  before/after reading can't tell a leak from noise; repeat the operation many
  times so a leak grows with the count.
- Don't assert which exception third-party code raises: PyPy's `pickle` raises
  `EOFError` where CPython's raises `TypeError`.
- Tests must pass on CPython and PyPy. A test that needs one libmemcached
  family's behaviour skips on the other (see `tests/test_timeout.py`).
- "Flaky" is a conclusion, not a starting point. Try to reproduce first (many
  runs, under CPU load, on the failing version) and say plainly what you could
  not reproduce.

## Branches, commits and pull requests

- `master` is protected by a ruleset: changes arrive only through pull requests
  (one approving review is required); force-pushing and deleting it are
  blocked. The owner may bypass the review requirement when merging a PR.
- Branch from a freshly fetched `origin/master`. A local `master` can carry
  unpushed commits and drag them into your PR.
- Commits are small and each is one logical change. The subject is imperative
  and short; the body says why and what was verified. Non-code changes use a
  scope prefix (`ci:`, `tests:`). Link issues with `Fixes #N` in the PR
  description, one issue per line, so GitHub closes them on merge.
- Work an LLM helped with carries the `Co-Authored-By:` trailer your tooling
  provides. Credit ideas taken from other people or forks in the commit
  message ("Idea from <fork>").
- A PR description says what changed and why, how it was tested (versions, build
  types, results), and **what was not verified**. Be specific about the second
  part; a reviewer relies on it more than on the first.
- Humans merge. Agents open PRs and report; they do not merge, close other
  people's PRs, change repository settings, push tags or use the admin bypass
  unless the maintainer asks for exactly that in the current session.
- Rebasing your own PR branch needs a force push: use
  `--force-with-lease=<branch>:<expected sha>`, and only for that branch.
- When a PR supersedes another, say so in the new PR and close the old one with
  a comment once the replacement has merged.

## CI

- `ci.yml` runs on pull requests, and on pushes to `master` only (a push to a PR
  branch would otherwise run everything twice). The matrix covers CPython and
  PyPy.
- CI should test both libmemcached families and prove which one each job used.
  The apt package depends on the runner image (Ubuntu 22.04 has 1.0.18, 24.04
  has 1.1.4), so never assume it: a job should fail unless
  `pylibmc.libmemcached_version` equals the version it is meant to test. (A
  "1.0.18" job once ran 1.1.4 for months because `ubuntu-latest` moved.)
- Every third-party action is pinned to a commit SHA with the version in a
  comment. To pin one: `gh api repos/OWNER/REPO/git/ref/tags/TAG --jq '.object.sha+" "+.object.type'`;
  if the type is `tag`, dereference it with
  `gh api repos/OWNER/REPO/git/tags/SHA --jq .object.sha`.
- Workflows can only really be tested on GitHub. Say what you could not run
  locally in the PR, and read the logs of the first run instead of trusting
  the colour.
- A known flake: `setup-python` downloads CPython 3.8–3.10 (not on the runner
  image) from a GitHub release asset, and that sometimes returns HTTP 504. The
  local `setup-python-retry` action caches the interpreter and retries once. For
  an infrastructure failure, rerun only the failed jobs
  (`gh run rerun <run-id> --failed`). Anything else gets investigated. Reruns
  replace the earlier attempt's result, so mention a flake in the PR.
- There is no `timeout` command on macOS. Use `gh pr checks <n> --watch` to wait.
- Release builds are `cd.yml`: it runs when a tag is pushed, builds wheels with
  cibuildwheel and the sdist, and creates the GitHub release. It also has a
  manual `workflow_dispatch` that builds everything without releasing.

## Making a release

Pushing a tag starts the release pipeline, so never push one without the
maintainer's explicit go-ahead.

1. **Go over the open work, issue by issue.** Do this first, before writing
   notes or thanking anybody: what ships, and who deserves thanks, only becomes
   clear once the open work has been triaged.
   - PRs: `gh pr list`. Review, merge or consciously defer each.
   - Issues: `gh issue list --state open --limit 200`. Open every one, old ones
     included, and sort them: fixed on `master` and waiting for the release
     (comment, close at release time); blocks the release; can wait; no longer
     applies (say why and close). Read the recent comments: people ask for
     releases there. Note who reported, reproduced or helped with each issue
     you resolve; that list feeds the thanks below.
   - Forks and other maintenance threads: `gh api repos/OWNER/REPO/forks`, compare
     `ahead_by` against `master`, and read what is ahead. Take back what is
     worth taking (credit them), and answer any thread about the project's
     maintenance.
2. **Check the support policy is consistent.** We claim support for what CI
   actually tests, and nothing else. `python_requires` and the classifiers in
   `setup.py`, `tox.ini`, `docs/install.rst`, the CI matrix, and the
   interpreters cibuildwheel builds must all say the same thing. In particular,
   don't ship wheels for interpreters CI doesn't test (cibuildwheel also builds
   free-threaded `cp314t` unless told to skip it), and pin the cibuildwheel
   version in the release job so a new upstream release can't change what gets
   built. Decide deliberately which Python and libmemcached versions you stop
   supporting, and say so in the notes.
3. **Thank the people, after the issue review.** Collect everyone since the last
   tag:
   ```sh
   git log LAST_TAG..origin/master --no-merges --format='%an' | sort | uniq -c | sort -rn
   git log LAST_TAG..origin/master --format='%(trailers:key=Co-Authored-By,valueonly)'
   git log LAST_TAG..origin/master --format=%B | grep -i -E 'idea from|thanks to|reported by'
   gh pr list --state merged --search "merged:>YYYY-MM-DD" --limit 200 --json number,author,title
   gh issue list --state all --search "closed:>YYYY-MM-DD" --limit 200 --json number,author,title
   ```
   Thank, by name or handle, everyone whose code was merged, who filed a
   reproducible bug, who tested or reviewed, whose fork or fix supplied an idea
   that was used, and any collaborator who helped. Do it in three places: a
   paragraph in the `docs/changelog.rst` entry (earlier releases do this),
   the GitHub release notes, and a comment on each issue or PR once the release
   that fixes it is out. Use the name someone uses themselves and don't guess
   pronouns.
4. **Write the change log.** `docs/changelog.rst`, "New in version X":
   user-visible changes first, then fixes, then platform changes. Document what
   pylibmc changed or now exposes, which libmemcached versions we support, and
   which one the wheels contain. Do not describe changes inside libmemcached
   itself (new behaviour, renamed settings): that is their work and their
   release notes. State anything that can break an existing pylibmc user
   (changed exceptions or defaults, dropped platforms). Check that the docs build (see step 9; it is not part of CI).
5. **Set the version.** Edit `src/pylibmc-version.h`; the tag is the same string
   with no `v` (`1.7.0`; a release candidate is `1.7.0rc1`). Use an annotated
   tag (`git tag -a`).
6. **Dry-run the pipeline.** `gh workflow run cd.yml --ref master` builds all
   the wheels and the sdist and skips the release job. Download the artifacts,
   install each kind into a clean environment, and check
   `pylibmc.build_info()` prints without warnings and that the tests pass where
   you can run them. Wheels built by a pipeline nobody has run are untested.
7. **Release candidate first for anything non-trivial.** Tag, wait for `cd.yml`,
   check the draft or release it produced, and let affected users try it
   (`pip install --pre pylibmc`), pointing at the issues they filed.
8. **Publish to PyPI.** The maintainer does this by hand, with their own
   credentials, from the artifacts of the release (`cd.yml` does not upload to
   PyPI, by choice). Agents never upload. Uploads cannot be taken back: the
   files on PyPI for a version are final, so check the artifacts first.
9. **Update the published docs.** The documentation lives at
   `https://sendapatch.se/projects/pylibmc/` (the URL in `README.rst` and
   `setup.py`). The maintainer publishes it by hand; how the files get onto
   that site is not recorded in this repository. Build them from an installed
   build of the release, because `docs/conf.py` imports the extension and
   refuses to run without `PYLIBMC_DIR`:
   ```sh
   pip install sphinx
   PYLIBMC_DIR=$(python -c "import _pylibmc, os; print(os.path.dirname(_pylibmc.__file__))") \
     python -m sphinx -b html docs /tmp/pylibmc-docs
   ```
   It uses the `sap` theme from `docs/_themes`. Today this prints one
   harmless warning (`html_static_path entry '_static' does not exist`). Check
   that the new change log entry and the install page (supported Pythons and
   libmemcached) render, and that the page's version reads the release you are
   cutting, before it goes live.
10. **After the release.** Install the published version in clean environments on
   macOS and Linux and run a smoke test. Comment on and close the issues it
   fixes (thanking the reporters). Move `pylibmc-version.h` to the next
   `-dev`. Delete merged branches. Answer any open maintenance thread with what
   shipped.

## Working in parallel, with helpers and subagents

- Use a separate `git worktree` per task. A branch can be checked out in only
  one worktree.
- Concurrent test runs must not share port 11211. Take a lock around each
  suite run with an atomic `mkdir` and release it in a trap:
  ```sh
  LOCK=/some/shared/dir/memcached-11211.lock
  until mkdir "$LOCK" 2>/dev/null; do sleep 3; done
  ( trap 'kill $MPID 2>/dev/null; wait $MPID 2>/dev/null; rmdir "$LOCK"' EXIT
    memcached -p 11211 -l 127.0.0.1 & MPID=$!
    until nc -z 127.0.0.1 11211; do sleep 0.3; done
    cd /tmp && python -m pytest ... )
  ```
- A helper's report is a claim, not a result. Re-check what you are about to
  relay: commit contents, checksums, CI status, and especially what a green
  result actually ran.
- Ask before outward-facing, hard-to-undo actions: pushing, opening or closing
  PRs and issues, commenting, changing repository settings, tagging, uploading.
  Approval for one of them is not approval for the next.
- Don't write secrets, tokens or personal data into commits, PRs or this file.

## Known gaps

Keep this list short and delete items when they are fixed.

- `tox.ini` still lists the old interpreter set.
- The pipeline does not yet install each wheel and run the test suite against
  it (the intended smoke test, with memcached started in the build container);
  until it does, wheels are untested artifacts.
