<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# Frozen receive experiments

These are the exact source snapshots used for the local prototype validation
and the receive experiment. They are experimental evidence; the production
bridge may subsequently differ. Each `hpx-comm.cpp` is a regular file, including
the pooled source that was originally exposed through a local symlink.

| Snapshot | SHA-256 of `hpx-comm.cpp` | Candidate-relative patch |
| --- | --- | --- |
| [Direct receive](direct_receive/hpx-comm.cpp) | `477f1243b68a303e370d97913279f9b312ed66c8a54811392083b9b6faec1590` | [direct_receive.patch](direct_receive/direct_receive.patch) |
| [Pooled receive](pooled_receive/hpx-comm.cpp) | `57945a07f87200293e8967c7dd5aed81b869f5e1b257692f297dbac99f62634c` | [pooled_receive.patch](pooled_receive/pooled_receive.patch) |

Both patches apply to their included `base-hpx-comm.cpp`, whose SHA-256 is
`4d605aeb52a995215296613d101a2ab0ee236fd8fbbfc479f66f766121b8d564`.
This is the serialize-buffer candidate working-tree snapshot based on Git
commit `e702e441d1914cd6e384a461fe8dd73b95e928ae`; it includes changes beyond
that commit. The patches are not patches against an assumed current HEAD.
Applying each patch to its included base was checked to reproduce the frozen
prototype byte for byte; see [PACKAGING_CHECKS.json](PACKAGING_CHECKS.json).

The original design notes are retained unchanged as
[direct PREPARATION.md](direct_receive/PREPARATION.md) and
[pooled PREPARATION.md](pooled_receive/PREPARATION.md), together with their
original provenance JSON. Statements there such as “not compiled or run” record
the preparation stage. The later completed local evidence is in
[receive_validation](../receive_validation/README.md). The pooled preparation
notes refer to the original `hpx/hpx-comm.cpp` location; its contents are now
stored directly as `pooled_receive/hpx-comm.cpp` in this package.

[SOURCE_MAP.json](SOURCE_MAP.json) maps every original copied file to its
published path and hash. From this directory, `sha256sum -c SHA256SUMS` verifies
the package. No object files, archives, executables, or symlinks are included.

The prototype code, patches, notes, and this README are licensed under the GNU
General Public License, version 2 or (at your option) any later version. Original
copyright and license notices are preserved. See [COPYING](../../../../COPYING).
