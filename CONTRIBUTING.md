# Contributing to HY-TUTOR

Thanks for being here. HY-TUTOR is a community project, and contributions
of any size are welcome — bug reports, typo fixes, new features, docs
improvements, or just opinions.

---

## Quick rules (TL;DR)

1. **All commits must be DCO-signed-off** with `git commit -s` (see below).
   This is a hard requirement, enforced by a GitHub bot. PRs without
   DCO sign-off cannot be merged.
2. **By DCO-signing, you accept the Inbound=Outbound clause** in this
   file — your contribution may be relicensed by the maintainer under
   any terms, current or future.
3. **Be cool, don't claim credit for others' work**, and follow the
   project's existing style.
4. **Open an issue first** for anything beyond a small bugfix, so we can
   agree on direction before you spend time on a PR.

If you have questions, [open an issue](https://github.com/AdityaK181225/HY-TUTOR/issues)
on GitHub. Please **prefer GitHub issues over email** for project
discussion.

---

## Table of contents

- [Code of conduct](#code-of-conduct)
- [How to report a bug](#how-to-report-a-bug)
- [How to suggest a feature](#how-to-suggest-a-feature)
- [How to submit a pull request](#how-to-submit-a-pull-request)
- [DCO sign-off (required)](#dco-sign-off-required)
- [Inbound=Outbound clause](#inboundoutbound-clause)
- [Honest limitations](#honest-limitations)
- [Coding style](#coding-style)
- [Reporting security issues](#reporting-security-issues)
- [License reminder](#license-reminder)

---

## Code of conduct

Be respectful, be patient, and assume good faith. The maintainer is a
student stepping back from the project, so responses may be slow or
absent — that's not personal.

---

## How to report a bug

1. Search [existing issues](https://github.com/AdityaK181225/HY-TUTOR/issues?q=is%3Aissue)
   first to make sure it hasn't been reported.
2. If not, open a new issue and include:
   - **What you did** (the exact steps)
   - **What you expected to happen**
   - **What actually happened** (error messages, screenshots)
   - **Your environment** (OS, Python version, `pip freeze` if relevant)
3. Label it as a bug if you can.

---

## How to suggest a feature

1. Open an issue with the `enhancement` label.
2. Describe the problem you're trying to solve (not just the solution
   you have in mind).
3. Wait for a maintainer or community member to weigh in before
   starting work.

---

## How to submit a pull request

1. **Open an issue first** for non-trivial changes.
2. Fork the repo, create a branch, make your changes.
3. **DCO sign-off** every commit (see below). The DCO bot will block
   your PR if you forget.
4. Make sure your branch is up to date with `main`.
5. Open the PR and fill in the [PR template](.github/PULL_REQUEST_TEMPLATE.md).
6. Wait for review. Be patient — the maintainer may not respond
   quickly. Other community members can also review.

---

## DCO sign-off (required)

Every commit in this project must be signed off with the **Developer
Certificate of Origin 1.1 (DCO)**. The full DCO text is at
<https://developercertificate.org/>. In short, by signing off you
certify that:

> (a) The contribution was created in whole or in part by me and I
>     have the right to submit it under the open source license
>     indicated in the file; or
>
> (b) The contribution is based upon previous work that, to the best
>     of my knowledge, is covered under an appropriate open source
>     license and I have the right under that license to submit that
>     work with modifications, whether created in whole or in part
>     by me, under the same open source license (unless I am
>     permitted to submit under a different license), as indicated
>     in the file; or
>
> (c) The contribution was provided directly to me by some other
>     person who certified (a), (b) or (c) and I have not modified
>     it.

### How to DCO sign-off

Add a `Signed-off-by:` line to your commit message:

```bash
git commit -s -m "Your commit message

Signed-off-by: Your Name <your.email@example.com>
```

The `-s` (or `--signoff`) flag automatically appends the right line
using your `git config user.name` and `user.email`. **Make sure those
are set to your real name and a real email** — they end up in the
project's permanent history.

If you forget `-s`, you can amend the most recent commit:

```bash
git commit -s --amend
```

Or amend older commits:

```bash
git rebase --exec 'git commit --amend --no-edit -s' origin/main
```

### What happens if you forget

A GitHub bot (Probot DCO) checks every PR. If any commit in the PR
lacks a `Signed-off-by` line, the bot posts a comment and the PR's
status check fails. You can fix it by amending and pushing again —
the bot will re-check automatically.

---

## Inbound=Outbound clause

By DCO-signing any commit in this project, you additionally agree to
the following **Inbound=Outbound** clause:

> By signing off on a commit, you confirm two things:
>
> 1. You wrote the code or have the right to submit it (the standard
>    DCO certification above); and
> 2. You grant the project maintainer (`AdityaK181225`) the right to
>    use, modify, and **relicense** that contribution under any
>    license — current or future — including but not limited to the
>    PolyForm Noncommercial License 1.0.0 (this project's current
>    license), a separate Commercial License, the AGPL-3.0, the
>    MIT License, or any other open-source or proprietary license.
>    This is a one-time, irrevocable, worldwide grant for that
>    specific contribution.

In plain English: your contribution stays attributed to you, and you
keep the right to use your own code however you want — but the
maintainer gets the right to put it in a different license as part of
the project (e.g., if a future commercial licensee needs a different
license for the whole codebase).

This clause is what lets the project accept community contributions
**without** requiring a separate signed CLA. The DCO sign-off captures
your consent at the moment of commit, in a way that's machine-verifiable.

---

## Honest limitations

The Inbound=Outbound clause above is **not a substitute for a formal
Contributor License Agreement (CLA)**. The DCO is a provenance
mechanism — it certifies you have the right to submit the code — but
the relicensing right relies on the clause being enforceable in your
jurisdiction. This is the same approach used by the Linux kernel,
Kubernetes, and many other large open-source projects before they
adopted formal CLAs.

In practice:
- The DCO + this clause has been the industry standard for years.
- For high-value relicensing (e.g., a real commercial deal), the
  maintainer may ask for additional confirmation from individual
  contributors, in good faith.
- If a contributor ever disputes the relicensing right, the project
  will work with them to resolve it — usually by removing or
  rewriting the disputed contribution, not by litigating.

If you have specific concerns about the Inbound=Outbound clause, please
raise them in your PR or in a GitHub issue before contributing. We'd
rather discuss than have surprises later.

---

## Coding style

- **Python**: PEP 8, with type hints encouraged (the project uses
  `from __future__ import annotations` in newer files).
- **Imports**: standard library, then third-party, then local —
  one blank line between groups.
- **Line length**: ~100 characters (configured in `.editorconfig`).
- **Docstrings**: only when the function's purpose isn't obvious from
  its name. One-line `"""..."""` for trivial helpers; multi-line for
  non-obvious behavior.
- **Commits**: small, focused, with clear messages. The
  `Signed-off-by` line is mandatory (see above).
- **Streamlit UI**: keep changes to `interface/` minimal unless
  requested. The 5 settings tabs (AI, Usage, Appearance, Files,
  Behavior) and the About tab are large and well-tested — please
  don't refactor them without discussion.
- **`core_pipeline/`**: please open an issue before modifying. The
  pipeline is the heart of the project; changes there can break
  user data.

---

## Reporting security issues

**Please do not open a public issue for security vulnerabilities.**

Open a private security advisory instead:
<https://github.com/AdityaK181225/HY-TUTOR/security/advisories/new>

If that's not possible (e.g., you don't have a GitHub account), you
can reach the maintainer at the Gmail address listed on the
maintainer's GitHub profile. **Please mark the subject line with
"SECURITY" so it's noticed promptly.**

---

## License reminder

By contributing to HY-TUTOR, you agree that:

- Your contribution is provided under the same license as the project
  (PolyForm Noncommercial 1.0.0, see [LICENSE](LICENSE)).
- You DCO-sign-off on every commit.
- You accept the Inbound=Outbound clause in this file.

If any of that is a problem, please raise it in an issue before you
spend time on a PR. We'd rather talk it through than have surprises
later.

Thanks for reading this far. Happy hacking! 🛠️
