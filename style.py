from collections import ChainMap
import json
from typing import Iterator, List, NamedTuple, Optional, Tuple

from node import Node


# How to "render" the Node tree into something that can be (re)drawn quickly?
# We have a tree of Node objects, and want to render them according to a
# particular Style instance. Our objectives are:
#   - To quickly draw the nodes visible in the current viewport
#   - To expand/collapse nodes without a full re-render
#   - To search/highlight/filter nodes without a full re-render
#   - To quickly deduce which nodes correspond to which lines in the viewport
# Therefore we want to annotate each Node object with:
#   - its "compact" representation as a single line (of unlimited length).
#       - when a node is "collapsed", this is the representation that will
#         be used, and _all_ of the node's children will be skipped/hidden.
#   - its "full" (aka. "expanded") representation:
#       - a list of lines to be shown before its children
#       - a list of lines to be shown after its children


class RenderedLine(NamedTuple):
    """A rendered line in the node view, with an associated node."""

    line: str
    node: "DrawableNode"


class DrawableNode(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.collapsed: bool = False
        self.compact: Optional[str] = None
        self.full: Optional[Tuple[List[str], List[str]]] = None

    def invalidate(self, recurse=False) -> None:
        self.compact = None
        self.full = None
        if recurse:
            for child in self.children:
                child.invalidate(recurse)

    def render(self, style: "Style") -> Iterator[RenderedLine]:
        if self.collapsed:
            if self.compact is None:
                self.compact = style.compact(self)
                assert "\n" not in self.compact
            yield RenderedLine(self.compact, self)
        else:
            if self.full is None:
                self.full = style.full(self)
                assert all("\n" not in line for p in self.full for line in p)
            pre, post = self.full
            yield from [RenderedLine(line, self) for line in pre]
            for child in self.children:
                yield from child.render(style)
            yield from [RenderedLine(line, self) for line in post]


class Style:
    """API for styling the GUI representation of a node tree.

    This is used to pre-render the compact + full representations of each
    DrawableNode instance in a tree of such nodes. The rendering is done
    on-demand from DrawableNode.render().
    """

    def __init__(self, **kwargs):
        pass

    def resize(self, new_width, new_height):
        """This is called when the terminal size changes."""
        pass

    def compact(self, node: DrawableNode) -> str:
        """Return the compact representation for the given node."""
        raise NotImplementedError

    def full(self, node: DrawableNode) -> Tuple[List[str], List[str]]:
        """Return the full representation for the given node.

        Return a (pre_lines, post_lines) pair of string lists holding the
        lines to display preceding the node's children (if any), and the lines
        to display following the node's children.
        """
        raise NotImplementedError


class CodeLikeStyle(Style):
    indent = " " * 4
    key_value_sep = ": "
    item_terminator = ","
    item_terminator_after_last = False

    # Map node.kind -> (empty_brackets, open_bracket, close_bracket)
    brackets = {
        None: ("{kind.__name__}()", "{kind.__name__}(", ")"),  # default
    }

    def get_brackets(self, kind):
        return self.brackets.get(kind, self.brackets[None])

    def empty(self, node):
        return self.get_brackets(node.kind)[0].format(kind=node.kind)

    def open(self, node):
        return self.get_brackets(node.kind)[1].format(kind=node.kind)

    def close(self, node):
        return self.get_brackets(node.kind)[2].format(kind=node.kind)

    def repr(self, value):
        raise NotImplementedError

    def format_key(self, node):
        return self.repr(node.key)

    def format_value(self, node):
        return self.repr(node.value)

    def combine_key_value(self, formatted_key, formatted_value):
        return formatted_key + self.key_value_sep + formatted_value

    def prefix(self, node):
        return self.indent * node.level

    def suffix(self, node):
        if not node.is_child:
            return ""
        elif node.is_last_child and not self.item_terminator_after_last:
            return ""
        else:
            return self.item_terminator

    def compact(self, node):
        s = self.format_value(node)
        if node.has_key:
            s = self.combine_key_value(self.format_key(node), s)
        return self.prefix(node) + s + self.suffix(node)

    def full(self, node):
        post_line = None
        if node.is_leaf:
            pre_line = self.format_value(node)
        elif node.children:  # internal node (non-empty)
            pre_line = self.open(node)
            post_line = self.close(node)
        else:  # internal node (empty)
            pre_line = self.empty(node)

        if node.has_key:
            pre_line = self.combine_key_value(self.format_key(node), pre_line)

        if post_line is None:
            pre_line = self.prefix(node) + pre_line + self.suffix(node)
        else:
            pre_line = self.prefix(node) + pre_line
            post_line = self.prefix(node) + post_line + self.suffix(node)

        return [pre_line], ([] if post_line is None else [post_line])


class PythonStyle(CodeLikeStyle):
    item_terminator_after_last = True
    brackets = ChainMap(
        {
            dict: ("{{}}", "{{", "}}"),
            list: ("[]", "[", "]"),
            tuple: ("()", "(", ")"),
            set: ("set()", "{{", "}}"),
        },
        CodeLikeStyle.brackets,
    )

    def repr(self, value):
        return repr(value)


class JSONStyle(CodeLikeStyle):
    indent = " " * 2
    brackets = ChainMap(
        {
            dict: ("{{}}", "{{", "}}"),
            list: ("[]", "[", "]"),
        },
        CodeLikeStyle.brackets,
    )

    def repr(self, value):
        return json.dumps(value)


class SyntaxColor(CodeLikeStyle):
    Schemes = {  # {scheme_name: {node.kind: color_name_or_rgb_tuple}}
        "jq": {  # from the `jq` commandline JSON processor
            "indent": "bright_white",
            "brackets": "bright_white",  # empty/open/close brackets
            "key_value_sep": "bright_white",
            "terminator": "bright_white",
            "key": "bright_blue",  # dict keys
            str: "green",
            type(None): "bright_black",
            None: "white",  # default
        },
        "Dark+": {  # from the Dark+ VSCode theme
            "indent": (212, 212, 212),
            "brackets": (212, 212, 212),  # empty/open/close brackets
            "key_value_sep": (212, 212, 212),
            "terminator": (212, 212, 212),
            "key": (156, 220, 254),  # dict keys
            str: (206, 145, 120),
            type(None): (86, 156, 214),
            bool: (86, 156, 214),
            int: (181, 206, 168),
            float: (181, 206, 168),
            None: (212, 212, 212),  # default
        },
    }

    def __init__(self, **kwargs):
        self.term = kwargs["term"]
        self.colors = self._prepare_scheme(kwargs.get("scheme", "Dark+"))
        super().__init__(**kwargs)
        self.indent = self._color("indent")(self.indent)
        self.key_value_sep = self._color("key_value_sep")(self.key_value_sep)
        self.item_terminator = self._color("terminator")(self.item_terminator)

    def _prepare_scheme(self, scheme):
        def color_func(color):
            if isinstance(color, str):  # color name
                return self.term.formatter(color)
            else:  # (r,g,b) tuple
                return self.term.color(self.term.rgb_downconvert(*color))

        return {k: color_func(v) for k, v in self.Schemes[scheme].items()}

    def _color(self, kind):
        return self.colors.get(kind, self.colors[None])

    def get_brackets(self, kind):
        color = self._color("brackets")
        return tuple(color(s) for s in super().get_brackets(kind))

    def format_key(self, node):
        return self._color("key")(super().format_key(node))

    def format_value(self, node):
        return self._color(node.kind)(super().format_value(node))


# class TreeStyle(Style):
#     _default_indent = "│ "

#     def format_value(self, node):
#         return repr(node.value)

#     def format_key(self, node):
#         return repr(node.key)

#     def terminator(self, is_last):
#         return ""


# class BoxedStyle(Style):
#     _default_indent = "│ "

#     # Map node.kind -> (empty_brackets, start_bracket, end_bracket)
#     _brackets = {
#         dict: ("╶ empty dict ─────", "┌ dict ─────────", "└───────────────"),
#         list: ("╶ empty list ─────", "┌ list ─────────", "└───────────────"),
#         tuple:("╶ empty tuple ────", "┌ tuple ────────", "└───────────────"),
#         set: ("╶ empty set ──────", "┌ set ──────────", "└───────────────"),
#         # default fallback
#         None: ("╶ empty unknown ──", "┌ unknown ──────", "└───────────────"),
#     }

#     def format_value(self, node):
#         return repr(node.value)

#     def format_key(self, node):
#         return repr(node.key)

#     #    def combine_key_value(self, node, formatted_key, formatted_value):
#     #        return self.format_value(key) + self.kv_sep + formatted_value

#     def terminator(self, is_last):
#         return ""


class TruncateLines(Style):
    def __init__(self, **kwargs):
        self.term = kwargs["term"]
        self.width = self.term.width
        super().__init__(**kwargs)

    def resize(self, new_width, new_height):
        super().resize(new_width, new_height)
        self.width = new_width

    def _trunc_index(self, seqs, target_length):
        length = self.term.length("".join(seqs[:target_length]))
        assert length < target_length
        for i in range(target_length, len(seqs) + 1):
            length += self.term.length(seqs[i])
            if length > target_length:
                return i - 1
        assert False

    def truncate(self, line):
        if self.term.length(line) > self.width:
            seqs = self.term.split_seqs(line)
            i = self._trunc_index(seqs, self.width - 1)
            return "".join(seqs[:i]) + self.term.reverse("̇̇̇…")
        else:
            return line

    def compact(self, node):
        return self.truncate(super().compact(node))

    def full(self, node):
        pre_lines, post_lines = super().full(node)
        return (
            [self.truncate(line) for line in pre_lines],
            [self.truncate(line) for line in post_lines],
        )
