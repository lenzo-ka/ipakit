"""What the CLI does when it could not read all of its input.

The library's policy is settled and documented in ``docs/ties.md``: a
character the inventory does not register cannot be a segment, so the
read drops it, and **says so** with a warning. That policy is deliberate
-- ``distance`` legitimately wants a number for out-of-vocabulary input
-- and nothing here changes it. What it does not settle is what the
*command line* should do about it, and the answer had been: nothing.

::

    $ ipakit rules apply -r 't -> ʔ / _ #' 'k@t'
    UserWarning: dropped 1 unregistered symbol(s) ['@'] ...
    kʔ
    $ echo $?
    0

The derivation is of ``kt``, not of what was typed, and the CLI called it
a success. Audibility is not the gap -- the warning is audible to a human
at a terminal. The gap is that **a warning is not a value**: a build step,
a Makefile, a `set -e` script or anything else consuming ``ipakit`` sees
only stdout and the exit status, and in both of those the loss is
invisible. So the answer belongs in the exit status, which is the one
channel every caller already reads.

Three things follow, and they are the whole policy.

**One status for the whole CLI, not a flag on one group.** Every
subcommand that reads IPA soft-reads it -- ``features``, ``describe``,
``convert tokenize``, all four ``rules`` commands, and three of the five
``distance`` commands -- so the answer is applied once, at the dispatcher,
to whatever the command was. Bolting ``--strict`` onto ``rules`` would
have left the same hole in ``distance word``, which is the one that
prints a confident four-decimal number computed from a truncated word.

**The status is its own, not an error.** The command ran, and its output
is what the library computed from what it could read; calling that a
failure (1) would conflate it with a malformed rule. :data:`LOSSY` is
distinct from both 0 and 1, so ``rc != 0`` fails a build while ``rc == 3``
remains available to a caller who wants exactly this.

**The report is the CLI's, not the interpreter's.** Python's default
handler writes the absolute path of the installed ``features.py``, a line
number and the source line -- three things that vary by install and none
of which name the input. The message is reprinted here on one line, and
identical messages are folded with a count, because the default warning
registry deduplicates by *source location*: piping three malformed lines
into ``rules apply`` used to report the first and stay silent about the
other two, so "audible" was not even true per form.

``--lax`` opts back into the old status. It is offered rather than
assumed because ``docs/ties.md`` blesses the lossy read for measurement,
and a lane that owns the CLI should not overrule a documented library
convention -- only make its consequences visible by default.
"""

from __future__ import annotations

import sys
import warnings
from collections.abc import Iterable
from pathlib import Path

from ..distance_model import UnusableReferenceWarning

#: Exit status for a run that produced output from input it could not read
#: in full. Distinct from 0 (clean), 1 (the command failed) and argparse's
#: 2 (the command line was not understood).
LOSSY = 3

#: Exit status for a run whose answer is degraded because its reference
#: inventory cannot provide usable percentile positions. ``--lax`` does not
#: suppress this status: that flag accepts input loss, and no input was lost.
DEGRADED = 4

#: Unclassified user warnings raised from inside this directory report input.
_PACKAGE = Path(__file__).resolve().parent.parent


def _fold(caught: Iterable[warnings.WarningMessage]) -> list[str]:
    """Fold repeated warning messages while preserving their first order."""
    counts: dict[str, int] = {}
    for entry in caught:
        text = str(entry.message)
        counts[text] = counts.get(text, 0) + 1
    return [
        text if count == 1 else f"{text} [{count} times]"
        for text, count in counts.items()
    ]


def input_reports(caught: Iterable[warnings.WarningMessage]) -> list[str]:
    """The messages saying part of the input did not survive the read.

    The test is the *shape* of the report rather than a list of today's
    messages: except for explicitly typed non-input warnings, a
    ``UserWarning`` raised from inside ipakit is the library telling its
    caller that something it was handed could not be carried. All four such
    sites are that -- an unregistered symbol, an unbound tie, a stress mark
    that reached no unit, a phoneset member outside the distance matrix --
    and a fifth would be caught without this function being touched.

    Anything raised from outside the package says nothing about the
    input and must not move the exit status: a ``DeprecationWarning``
    from the interpreter is not the caller's transcription being wrong.

    Repeats are folded, because one loss reported once is the useful
    line and a thousand-form pipeline should not print a thousand of
    them; the count is kept, since "this happened 900 times" is the
    part a reader acts on.
    """
    reports = []
    for entry in caught:
        if not issubclass(entry.category, UserWarning):
            continue
        if issubclass(entry.category, UnusableReferenceWarning):
            continue
        try:
            inside = Path(entry.filename).resolve().is_relative_to(_PACKAGE)
        except (OSError, ValueError):  # pragma: no cover - unparseable path
            inside = False
        if not inside:
            continue
        reports.append(entry)
    return _fold(reports)


def degraded_reports(caught: Iterable[warnings.WarningMessage]) -> list[str]:
    """Messages saying an answer's reference cannot support usable positions."""
    return _fold(
        entry
        for entry in caught
        if issubclass(entry.category, UnusableReferenceWarning)
    )


def report(caught: Iterable[warnings.WarningMessage], status: int, lax: bool) -> int:
    """Print policy warnings and give the run its most specific status.

    A status the command already set is left alone: a command that failed
    has said something more specific than "the input was lossy", and
    :data:`LOSSY` must not overwrite it.

    Input loss takes precedence when both conditions occur, because status 3
    must continue to mean that something was dropped. ``--lax`` suppresses
    only that promotion; it never suppresses :data:`DEGRADED`, which describes
    the answer's unusable reference rather than an accepted lossy read.
    """
    caught = list(caught)
    input_messages = input_reports(caught)
    degraded_messages = degraded_reports(caught)
    for message in [*input_messages, *degraded_messages]:
        print(f"ipakit: warning: {message}", file=sys.stderr)
    if status != 0:
        return status
    if input_messages and not lax:
        print(
            f"ipakit: input was not read in full; exiting {LOSSY}. "
            "Rerun as 'ipakit --lax ...' to accept the lossy read and exit 0.",
            file=sys.stderr,
        )
        return LOSSY
    if degraded_messages:
        print(
            f"ipakit: answer is degraded because the reference is unusable; "
            f"exiting {DEGRADED}.",
            file=sys.stderr,
        )
        return DEGRADED
    return status
