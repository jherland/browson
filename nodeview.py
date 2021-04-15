#!/usr/bin/env python3
import logging
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

    context_lines: int = 1  # how many context lines around the focused line?

    def __init__(
        self, root: DrawableNode, width: int, height: int, style: Style
    ):
        self.root = root
        self.width = width
        self.height = height
        self.style = style

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

    def current_node(self) -> DrawableNode:
        """Return the currently selected/focused node."""
        return self.lines[self.focus].node

    def current_position(self) -> Tuple[int, int]:
        """Return (focused line, total lines)."""
        return self.focus + 1, len(self.lines)

    def adjust_viewport(self) -> None:
        """Scroll the viewport to make sure the focused line is visible."""
        first = self.visible.first

        if self.focus < first:  # scroll viewport up
            first = self.focus - self.context_lines
        elif self.focus > first + self.height:  # scroll viewport down
            first = self.focus + self.context_lines - self.height
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
        new_lines = list(current.render(self.style))  # regenerate new lines
        self.lines[first : last + 1] = new_lines  # replace
        self.need_redraw = True
        return LineSpan(first, first + len(new_lines) - 1)

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
        first line, jump to the first line of the parent node. If 'last' is
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
        self.lines = list(self.root.render(self.style))
        self.adjust_viewport()

    @debug_time
    def resize(self, new_width, new_height) -> None:
        """Resize this tree view to the given dimensions."""
        self.width, self.height = new_width, new_height
        self.style.resize(new_width, new_height)
        self.rerender_all()

    @debug_time
    def draw(self, term: Terminal) -> Iterator[str]:
        """Yield the currently visible lines in this tree view."""

        def highlight(line, variant="on_gray20"):
            return getattr(term, variant)(term.ljust(line))

        first, last = self.visible
        for i, (line, _) in enumerate(self.lines[first : last + 1], first):
            if i == self.focus:
                line = highlight(line)
            yield line
        self.need_redraw = False
