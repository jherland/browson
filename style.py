from contextlib import suppress
import json


class Style:
    _default_indent = NotImplemented

    # Map node.kind -> (empty_brackets, start_bracket, end_bracket)
    _brackets = NotImplemented

    def __init__(self, **kwargs):
        if "indent" in kwargs:
            self.indent = kwargs["indent"]
        else:
            self.indent = self._default_indent
        self.kv_sep = ": "

    def brackets(self, node):
        return self._brackets.get(node.kind, self._brackets[None])

    def empty(self, node):
        return self.brackets(node)[0]

    def open(self, node):
        return self.brackets(node)[1]

    def close(self, node):
        return self.brackets(node)[2]

    def format_value(self, node):
        raise NotImplementedError

    def format_key(self, node):
        raise NotImplementedError

    def combine_key_value(self, node, formatted_key, formatted_value):
        return formatted_key + self.kv_sep + formatted_value

    def terminator(self, is_last):
        raise NotImplementedError

    def format_line(self, prefix, text, suffix, node):
        return prefix + text + suffix


class PythonStyle(Style):
    _default_indent = " " * 4

    # Map node.kind -> (empty_brackets, start_bracket, end_bracket)
    _brackets = {
        dict: ("{}", "{", "}"),
        list: ("[]", "[", "]"),
        tuple: ("()", "(", ")"),
        set: ("set()", "{", "}"),
        None: ("??", "<", ">"),  # default fallback
    }

    def format_value(self, node):
        return repr(node.value)

    def format_key(self, node):
        return repr(node.key)

    def terminator(self, is_last):
        return ","


class JSONStyle(Style):
    _default_indent = " " * 2

    # Map node.kind -> (empty_brackets, start_bracket, end_bracket)
    _brackets = {
        dict: ("{}", "{", "}"),
        list: ("[]", "[", "]"),
        None: ("??", "<", ">"),  # default fallback
    }

    def format_value(self, node):
        return json.dumps(node.value)

    def format_key(self, node):
        return json.dumps(node.key)

    def terminator(self, is_last):
        return "" if is_last else ","


class Colorizer(Style):
    Schemes = {  # {scheme_name: {node.kind: color_name_or_rgb_tuple}}
        "jq": {  # from the `jq` commandline JSON processor
            "indent": "bright_white",
            "brackets": "bright_white",  # empty/open/close brackets
            "kv_sep": "bright_white",
            "terminator": "bright_white",
            "key": "bright_blue",  # dict keys
            str: "green",
            type(None): "bright_black",
            None: "white",  # default
        },
        "Dark+": {  # from the Dark+ VSCode theme
            "indent": (212, 212, 212),
            "brackets": (212, 212, 212),  # empty/open/close brackets
            "kv_sep": (212, 212, 212),
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
        self.kv_sep = self._color("kv_sep")(self.kv_sep)

    def _prepare_scheme(self, scheme):
        def color_func(color):
            if isinstance(color, str):  # color name
                return self.term.formatter(color)
            else:  # (r,g,b) tuple
                return self.term.color(self.term.rgb_downconvert(*color))

        return {k: color_func(v) for k, v in self.Schemes[scheme].items()}

    def _color(self, kind):
        return self.colors.get(kind, self.colors[None])

    def brackets(self, node):
        color = self._color("brackets")
        return tuple(color(s) for s in super().brackets(node))

    def format_value(self, node):
        return self._color(node.kind)(super().format_value(node))

    def format_key(self, node):
        return self._color("key")(super().format_key(node))

    def terminator(self, is_last):
        return self._color("terminator")(super().terminator(is_last))


class LineWrapper(Style):
    def __init__(self, **kwargs):
        self.term = kwargs["term"]
        self.enabled = kwargs.get("enabled", self.term.does_styling)
        self.wrap = kwargs.get("wrap", False)  # default to truncated lines
        super().__init__(**kwargs)

    def format_line(self, prefix, text, suffix, node):
        ret = super().format_line(prefix, text, suffix, node)
        width = self.term.width
        if self.term.length(ret) > width and self.enabled:
            if self.wrap:
                with suppress(KeyError):
                    prefix += " " * self.term.length(
                        self.combine_key_value(node, self.format_key(node), "")
                    )
                lines = self.term.wrap(ret, subsequent_indent=prefix)
                ret = "\n".join(lines)
            else:  # truncate
                lines = self.term.wrap(ret, width=self.term.width - 1)
                ret = lines[0] + self.term.reverse("̇̇̇…")
        return ret
