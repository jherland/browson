from collections import ChainMap
from contextlib import suppress
import json
from typing import Iterator, Tuple

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


class Style:
    """API for styling the GUI representation of a Node tree.

    This is used to pre-render the compact + full representations of each
    Node instance in a tree of Nodes. A complete rendering of a Node and its
    children/subtree is performed by passing it to .render(). This will
    annotate the Node object with "compact", "full_pre", and "full_post"
    items (that are used to draw both the compact and full/expanded views of
    this Node) as well as passing all its children nodes to .render as well.
    Thus a complete rendering of the Node tree is performed by passing the
    root Node to the appropriate Style instance.
    """

    def __init__(self, **kwargs):
        pass

    def render(self, node: Node) -> None:
        """Annotate this Node and its children with rendered data."""
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

    def compact(self, node):
        s = self.format_value(node)
        with suppress(KeyError):
            s = self.combine_key_value(self.format_key(node), s)
        return s

    def full(self, node):
        post_lines = []
        if node.children():  # internal node (non-empty)
            pre_line = self.open(node)
            post_lines = [self.close(node)]
        elif "children" in node:  # internal node (empty)
            pre_line = self.empty(node)
        else:  # leaf node
            pre_line = self.format_value(node)

        with suppress(KeyError):
            pre_line = self.combine_key_value(self.format_key(node), pre_line)
        return pre_line, post_lines

    def render(self, node: Node) -> None:
        prefix = self.indent * node["level"]

        in_container = node.get("is_child", False)
        is_last = node.get("is_last_child", False)
        if in_container and (self.item_terminator_after_last or not is_last):
            suffix = self.item_terminator
        else:
            suffix = ""

        pre_line, post_lines = self.full(node)

        # The suffix for this node goes at the end of its last line
        if suffix and post_lines:
            post_lines[-1] += suffix
            suffix = ""

        node["compact"] = prefix + self.compact(node) + suffix
        node["full_pre"] = [prefix + pre_line + suffix]
        node["full_post"] = [prefix + line for line in post_lines]

        for child in node.children(default=[]):
            self.render(child)


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


class Colorizer(CodeLikeStyle):
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
        self.colors = self._prepare_scheme(kwargs.get("scheme", "jq"))
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


def render_nodes(root: Node, style: Style) -> Iterator[Tuple[str, Node]]:
    style.render(root)

    def previsit(node):
        yield from [(line, node) for line in node["full_pre"]]

    def postvisit(node):
        yield from [(line, node) for line in node["full_post"]]

    yield from root.dfwalk(previsit, postvisit)
