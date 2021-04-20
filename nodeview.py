#!/usr/bin/env python3
import logging
import re
from typing import Iterator, NamedTuple, Optional, Tuple

from blessed import Terminal

from style import DrawableNode, Style
from utils import clamp, debug_time

logger = logging.getLogger(__name__)


class LineSpan(NamedTuple):
    """A span of lines in the tree view (inclusive)."""

    first: int
    last: int


class NodeView:
    """Manage the main view of the tree of nodes."""

    context: int = 1  # how many context lines around the focused line?

    def __init__(
        self,
        root: DrawableNode,
        term: Terminal,
        width: int,
        height: int,
        style: Style,
        search: str = "",
    ):
        self.root = root
        self.term = term
        self.width = width
        self.height = height
        self._style = style
        self._search = search

        # Main state variables
        self.lines = []  # list of RenderedLine objects, see .rerender_all()
        self.focus = 0  # currently focused/selected index in .lines
        self.visible = LineSpan(0, self.height - 1)  # span of current viewport
        self.need_redraw = True  # must redraw current viewport

    @property
    def style(self) -> Style:
        return self._style

    @style.setter
    def style(self, value: Style) -> None:
        self._style = value
        self._style.resize(self.width, self.height)
        self._render()

    @property
    def search(self) -> str:
        return self._search

    @search.setter
    def search(self, value: str) -> None:
        if value == getattr(self, "_search", None):
            return
        self._search = value
        self.need_redraw = True  # self._render()

    def _matches(self, i: int) -> bool:
        """Return True iff self.lines[i] matches self.search."""
        line = self.term.strip_seqs(self.lines[i].line)
        return self.search and self.search in line

    def current_node(self) -> DrawableNode:
        """Return the currently selected/focused node."""
        return self.lines[self.focus].node

    def current_position(self) -> Tuple[int, int]:
        """Return (focused line, total lines)."""
        return self.focus + 1, len(self.lines)

    @debug_time
    def _render(self, node=None, first=0, last=None):
        node = self.root if node is None else node
        last = len(self.lines) if last is None else last
        new_lines = list(node.render(self.style))
        # new_lines = [
        #     RenderedLine(self.highlight_search(line), n)
        #     for line, n in node.render(self.style)
        # ]
        self.lines[first : last + 1] = new_lines
        self.adjust_viewport()
        return LineSpan(first, first + len(new_lines) - 1)

    def adjust_viewport(self) -> None:
        """Scroll the viewport to make sure the focused line is visible."""
        first = self.visible.first

        if self.focus < first + self.context:  # scroll viewport up
            first = self.focus - self.context
        elif self.focus > first + self.height - self.context:  # scroll down
            first = self.focus + self.context - self.height
        # Keep viewport within rendered lines
        first = max(
            0, min(len(self.lines) - 1, first + self.height) - self.height
        )

        self.visible = LineSpan(first, first + self.height)
        self.need_redraw = True

    def node_span(
        self, start: Optional[int] = None, node: Optional[DrawableNode] = None
    ) -> LineSpan:
        """Return (first, last) span of lines for the given node.

        If not given, 'node' is found at self.lines[start] ('start' defaults
        to self.focus if not given).

        Find all lines adjacent to 'start' that represent this node or any of
        its children. Return (first, last) indexes (inclusive) of this span of
        adjacent lines.

        Begin at self.lines[start] and walk in both direction until we find the
        first lines that are not associated with this node or its children.

        E.g. if 'node' has no children, and is only represented by a single
        line, then return (start, start). If 'node' is the root node, return
        (0, len(self.lines) - 1).
        """

        start = self.focus if start is None else start
        node = self.lines[start].node if node is None else node

        def inside(child):
            return node in list(child.ancestors(include_self=True))

        assert inside(self.lines[start].node)
        first = start
        while first > 0 and inside(self.lines[first - 1].node):
            first -= 1
        last = start
        while last < len(self.lines) - 1 and inside(self.lines[last + 1].node):
            last += 1
        return LineSpan(first, last)

    @debug_time
    def rerender(self, start: Optional[int] = None) -> LineSpan:
        """Redraw the node (w/children, if applicable) at self.lines[start].

        Look up the node at self.lines[start] ('start' defaults to self.focus
        if not given) and regenerate its lines (incl. children if applicable).
        Replace self.lines[start] and all surrounding lines associated with
        the node (see .node_span() for more details) with the regenerated
        lines.

        Return the new (first, last) line span for the current node.
        """
        start = self.focus if start is None else start
        current = self.lines[start].node
        first, last = self.node_span(start)  # find related old lines
        return self._render(current, first, last)

    # Actions triggered from input

    def set_focus(self, line: int) -> None:
        """Move focus to the given index in self.lines."""
        self.focus = clamp(line, 0, len(self.lines) - 1)
        self.adjust_viewport()

    def move_focus(self, relative: int) -> None:
        """Move focus up (negative) or down (positive) by the given #lines."""
        return self.set_focus(self.focus + relative)

    def jump_node(self, *, forwards: bool = False) -> None:
        """Move focus to the first/last line of the current (or parent) node.

        Jump to the first line representing the current node. If already at the
        first line, jump to the first line of the parent node. If 'forwards' is
        True, jump to the last line representing the current node (or parent
        node).
        """
        first, last = self.node_span()
        target = last if forwards else first
        current = self.lines[self.focus].node
        while self.focus == target:  # jump to parent instead
            parent = current.parent
            if parent is None:
                break
            first, last = self.node_span(self.focus, parent)
            target = last if forwards else first
            current = parent
        self.set_focus(target)

    def jump_match(self, *, forwards: bool = False) -> None:
        """Move focus to the previous/next match for .search."""
        if forwards:
            indices = range(self.focus + 1, len(self.lines))
        else:
            indices = range(self.focus - 1, -1, -1)
        for i in indices:
            if self._matches(i):
                self.set_focus(i)
                return

    def collapse_current(self) -> None:
        """Collapse the current node.

        Redraw the part of the tree related to the current node. Put focus on
        (the now single line representing) the current node.
        """
        current = self.lines[self.focus].node
        if current.collapsed:
            return  # already collapsed
        current.collapsed = True

        new_focus = self.rerender(self.focus).first
        self.set_focus(new_focus)

    def collapse_other(self) -> None:
        """Collapse all nodes not on the path to the current node.

        Do not affect the children of the current node.
        Put focus on (the first line of) the current node.
        """
        current = self.lines[self.focus].node
        path = list(current.ancestors(include_self=True))
        for node in self.root.dfwalk():
            if current in list(node.ancestors()):
                continue  # don't affect children
            if node not in path:
                node.collapsed = True  # collapse unrelated nodes

        self.rerender(0)  # redraw everything

        # Re-focus current node
        for i, (_, n) in enumerate(self.lines):
            if n is current:
                self.set_focus(i)
                break

    def collapse_all(self) -> None:
        """Collapse all nodes. Put focus on the first/only line."""
        for node in self.root.dfwalk():
            node.collapsed = True
        new_focus = self.rerender(0).first  # redraw everything
        self.set_focus(new_focus)

    def expand_current(self) -> None:
        """Expand the current node.

        Redraw the part of the tree related to the current node. Put focus on
        the first line representing the current node.
        """
        current = self.lines[self.focus].node
        if not current.collapsed:
            return  # already expanded
        current.collapsed = False

        new_focus = self.rerender(self.focus).first
        self.set_focus(new_focus)

    def expand_below(self) -> None:
        """Expand this node and all its descendants.

        Do not affect unrelated nodes.
        Put focus on (the first line of) the current node.
        """
        current = self.lines[self.focus].node
        for node in current.dfwalk():
            node.collapsed = False  # expand descendants

        new_focus = self.rerender(self.focus).first
        self.set_focus(new_focus)

    def expand_all(self) -> None:
        """Expand all nodes.

        Put focus back onto (the first line of) the current node.
        """
        current = self.lines[self.focus].node
        for node in self.root.dfwalk():
            node.collapsed = False
        self.rerender(0)  # redraw everything

        # Re-focus current node
        for i, (_, n) in enumerate(self.lines):
            if n is current:
                self.set_focus(i)
                break

    @debug_time
    def rerender_all(self) -> None:
        """Force a full rerender of all visible nodes."""
        self.root.invalidate(recurse=True)
        self._render()

    @debug_time
    def resize(self, new_width: int, new_height: int) -> None:
        """Resize this tree view to the given dimensions."""
        self.width, self.height = new_width, new_height
        self.style.resize(new_width, new_height)
        self.rerender_all()

    def _highlight_matches(self, line: str) -> str:
        """Apply search highlight to the given rendered line.

        Return 'line' with its original terminal escapes, as well as with
        'self.search' styled with black text on yellow background.
        """
        # This is largely an exercise in proper handling of terminal escapes.
        # We must search as if the terminal escapes are not there, but then
        # prepare the result by combining the existing terminal escapes with
        # new ones (from the search highlighting).
        haystack = self.term.strip_seqs(line)
        assert self.term.length(line) == len(haystack)  # sanity
        needle = self.search

        def term_escapes_before(index):
            """Return terminal escapes that occur before 'index' in line."""
            letters = []
            escapes = []
            for fragment in self.term.split_seqs(line):
                fraglen = self.term.length(fragment)
                assert fraglen in [0, 1]
                [escapes, letters][fraglen].append(fragment)
                if len(letters) > index:
                    break
            return "".join(escapes)

        def highlight_needle(match):
            pre_escapes = term_escapes_before(match.end())
            substr = match.string[match.start() : match.end()]
            return self.term.black_on_bright_yellow(substr) + pre_escapes

        def combine_escapes(line1: str, line2: str) -> Iterator[str]:
            assert self.term.strip_seqs(line1) == self.term.strip_seqs(line2)
            seq1 = self.term.split_seqs(line1)
            seq2 = self.term.split_seqs(line2)
            while seq1 and seq2:
                if self.term.length(seq1[0]) == 0:  # term escape in line1
                    yield seq1.pop(0)
                elif self.term.length(seq2[0]) == 0:  # term escape in line2
                    yield seq2.pop(0)
                else:  # letter in both strings
                    assert seq1[0] == seq2[0]
                    yield seq1.pop(0)
                    seq2.pop(0)
            # Yield remainder of whichever string has escapes left in it
            yield from seq1
            yield from seq2

        highlighted = re.sub(needle, highlight_needle, haystack)
        # Re-combine original terminal escapes from line with the highlights
        return "".join(combine_escapes(line, highlighted))

    @debug_time
    def draw(self):
        """Yield the currently visible lines in this tree view."""
        first, last = self.visible
        ret = []
        for i, (line, _) in enumerate(self.lines[first : last + 1], first):
            if self.search and self._matches(i):
                line = self._highlight_matches(line)
            if i == self.focus:
                line = self.term.on_gray20(self.term.ljust(line))
            ret.append(line)
        self.need_redraw = False
        return ret
