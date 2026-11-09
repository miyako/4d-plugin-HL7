# Manual source-version releases

The default branch is `main` (verified independently with GitHub's repository
API and `git ls-remote --symref origin HEAD`). Both workflows honor the Actions
branch selector; publication is not restricted to the default branch.

1. Run **Bump version**, select the intended branch and patch/minor/major mode.
   The workflow checks out the immutable dispatch `github.sha`, requires a clean
   tree and an exact remote branch match, validates all source versions, and
   commits only the three source metadata files. It does not create tags or
   dispatch Build. An executable pre-push hook checks Git's advertised old SHA,
   the exact target, literal local `HEAD`, a single direct parent equal to the
   selected SHA, and exactly one update. It is checked before work and immediately
   before the non-force, no-follow-tags push. A branch race fails rather than
   rebasing or overwriting another commit.
2. Separately run **Build** on the desired branch. It has zero inputs and checks
   out `github.sha` in every job. Strict source `X.Y.Z` determines `vX.Y.Z`,
   `HL7-X.Y.Z.zip`, and `HL7-X.Y.Z.dmg`. Existing tags or releases (including
   drafts) are errors, never rebuild targets.
3. Build retains Release/x64 MSBuild with v143/Windows SDK 10.0, the
   `windows-binaries` artifact, and Default/universal macOS with deployment target
   11.0, existing resources, signing, verification, both notarizations and DMG
   stapling. Stale bundle and Xcode cache outputs are removed; the exact Windows
   output, both macOS architectures, notary `Accepted` results and staple
   validation are required. No dependency/framework/toolset/resource project
   configuration is changed.

All branches share the constant `release-publication` concurrency group without
cancellation. Early and final checks require remote tag absence and authenticated,
fully validated paginated release lists. Authorization, network, malformed page,
and 404 failures abort. The final check happens only after native build, signing,
verification, notarization and stapling. Publication uses create-only POSTs:
tag ref at the selected SHA, verified remotely, then a new public, non-prerelease
release (empty original notes), then assets uploaded to that new release ID.
No release is reused, edited, deleted, clobbered or retried.

## Authority and source-only repairs

The rename-follow history starts with `5f272c2` (workflow addition) and its
marketing-first/current-fallback header. Commit `e5bf57f` explicitly replaces that
contract: its header promises **both MARKETING_VERSION/CURRENT_PROJECT_VERSION**
and **CFBundleShortVersionString/CFBundleVersion** are written from the same
version. Its commit message likewise promises coordinated validation. That
affirmative header, not its buggy marketing-only implementation or older
fallback history, governs this repository.

At baseline `38533629c48e67fe4b3d1ce48c4cea7f44597ee3`, all six marketing settings
and root `Info.plist` say `1.0.5`; all six current settings remained `1.0.3`.
The source `English.lproj/InfoPlist.strings`, referenced by the project's
InfoPlist.strings variant group and Resources phase, overrides the displayed
short version and info string with `1.0.0`. This migration only repairs those
six current literals and two localized display literals to existing authority
`1.0.5`: **no release increment**. Copyright 2022 and CR line endings remain
unchanged. Root `CFBundleVersion` is absent and stays absent.

The source helper permits supported `$(KEY)`/`${KEY}` references, preserving
them verbatim, but rejects unresolved/cyclic/drifted values, malformed versions,
and duplicate quoted/unquoted keys before writes. Literal coordinated fields
and localized display versions are bumped together. BOM, every individual line
ending, whitespace, modes and unrelated bytes are preserved. Prebuilt bundles,
4D data/schema/counters, manifests, constants and dependencies are excluded.
This is not a generic rule to normalize independent build versions: the
marketing-only Window Button and marketing-first Common String Algorithm
contracts preserve their independent build fields, including equal-valued ones.

Committed reference implementations inspected:

- `miyako/4d-plugin-proxy@4dc9995e5523f86f4d6d4d111f89ad3f81d8fb87`:
  complete source/release helpers, hook and tests.
- `miyako/4d-plugin-system-beep@a4b3e57d3935185c354f99f6751aded2b2038d5a`:
  six-configuration coordinated metadata and Windows/macOS build.
- `miyako/4d-plugin-window-button@3f14facb9aaaaff0e22eeb8e07531163680c3a8a`:
  independent build-version preservation and macOS freshness.
- `miyako/4d-plugin-common-string-algorithm@2606a68201866ec9fcbb38b51462d79215f504ef`:
  marketing-first authority and exact Windows output.

## Partial publication and recovery

Failure after tag creation may leave a tag without a release. Failure after
release creation or an asset upload may leave a public release with incomplete
assets. The workflow reports the partial state and does not roll back or retry:
automatic cleanup risks deleting another actor's data. Inspect the selected
SHA, tag, release ID and assets manually. Resolve partial publication explicitly
under repository policy, or make a separately authorized source bump and publish
a fresh version. Re-running the same version intentionally fails closed.

## Local checks

Run `actionlint` and
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .github/tests -v`.
PowerShell is required to execute the exact Windows-output stub test. The tests
use temporary copies, bare Git remotes, fake authenticated API responses and
native-command stubs. Run the entire suite again in a disposable repository
copy after a source bump; never increment the real checkout to validate tests.
No local check runs native compilation, signing, notarization, 4D, Actions
dispatch, or production tag/release mutations.
