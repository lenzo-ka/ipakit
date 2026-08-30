"""Tract commands - draw the mid-sagittal figure, and list the heads.

The renderer is ``ipakit.tract_svg``, and this is the same call from a
shell rather than a second way to draw. Both go through
:func:`ipakit.tract_svg.drawing`, so the picture a student gets from
``ipakit tract draw t`` and the picture ``make figures`` checks in are the
same bytes -- ``tests/test_tract_figures.py`` asserts exactly that.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .base import IPA, Command, CommandGroup, add_format_arg, add_output_arg


class DrawCommand(Command):
    """Draw one phone's mid-sagittal tract figure.

    The figure is a projection of the declared geometry, not a
    measurement. A posture is a place along the tract and a degree of
    closure; what the sagittal plane cannot hold is annotated with the
    reason rather than drawn as anatomy. See docs/tract-figures.md.

    With no phone, the reference drawing is produced: every landmark the
    head declares, at its rest posture.

    Examples:
        ipakit tract draw t                # SVG on stdout
        ipakit tract draw t -o t.svg       # the bytes `make figures` writes
        ipakit tract draw "tʰ" -o th.svg   # a marked unit draws too
        ipakit tract draw -o rest.svg      # the reference drawing
        ipakit tract draw i --head child -o i.svg
        ipakit tract draw i --page -o i.html     # the figure in a read-along page
        ipakit tract draw --page -o tract.html   # and, for the reference, the
                                                 # aperture profile and its
                                                 # provenance table
    """

    name = "draw"
    aliases = []
    help = "Draw a phone's mid-sagittal tract figure (SVG, or a page)"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "phone", nargs="?", help="IPA unit to draw (omit for the reference)"
        )
        parser.add_argument(
            "--head", help="Head shape to draw on (default: the declared default)"
        )
        parser.add_argument(
            "--page",
            action="store_true",
            help=(
                "Emit a standalone HTML page around the figure; the reference "
                "drawing also gets the aperture profile and its provenance"
            ),
        )
        parser.add_argument(
            "--no-caption",
            action="store_true",
            help="Leave the phone, its description and its features off the figure",
        )
        add_output_arg(parser)

    def run(self) -> int:
        from ..tract import head as head_shape
        from ..tract import heads
        from ..tract_svg import drawing, render, render_page

        available = heads()
        name = self.args.head or head_shape().name
        if name not in available:
            return self.error(f"no head {name!r}; have {', '.join(sorted(available))}")

        drawn = drawing(name, self.args.phone)
        assemble = render_page if self.args.page else render
        text = assemble(drawn, caption=not self.args.no_caption)

        # Written as bytes rather than through ``self.print``: a figure is
        # compared byte for byte against docs/figures, and a trailing
        # newline that only appears when -o is given is exactly the kind of
        # divergence between two ways of drawing that this repo has paid
        # for before. On stdout a newline is a courtesy to the shell.
        if self.output_path:
            Path(self.output_path).write_text(text, encoding="utf-8")
        else:
            self.print(text)
        return 0


class HeadsCommand(Command):
    """List the declared head shapes.

    A head is a rendering geometry only: phones live in a normalized,
    head-independent tract space, so which head you draw on cannot move a
    distance. The properties a drawing has to satisfy are checked on every
    head; the checked-in figures draw one of them.

    Examples:
        ipakit tract heads
        ipakit tract heads -f json
    """

    name = "heads"
    aliases = []
    help = "List the declared head shapes"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_format_arg(parser)
        add_output_arg(parser)

    def run(self) -> int:
        from ..tract import head as head_shape
        from ..tract import heads

        default = head_shape().name
        shapes = sorted(heads().items())
        if self.format == "json":
            self.output_json(
                [
                    {
                        "name": name,
                        "default": name == default,
                        "length_cm": shape.length_cm,
                        "desc": shape.desc,
                    }
                    for name, shape in shapes
                ]
            )
        else:
            self.output_table(
                [
                    [
                        name + (" *" if name == default else ""),
                        "—" if shape.length_cm is None else f"{shape.length_cm:.1f}",
                        shape.desc or "",
                    ]
                    for name, shape in shapes
                ],
                headers=["head", "length cm", "description"],
            )
        return 0


class TractGroup(CommandGroup):
    """The declared vocal tract, drawn.

    Subcommands:
        draw     Draw a phone's mid-sagittal figure
        heads    List the declared head shapes

    Examples:
        ipakit tract draw t -o t.svg       # one phone
        ipakit tract draw -o rest.svg      # the reference drawing
        ipakit tract heads                 # what can be drawn on
    """

    name = "tract"
    aliases = ["t"]
    help = "Draw the mid-sagittal tract (draw, heads)"
    commands = [DrawCommand, HeadsCommand]
