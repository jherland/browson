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

    def format_value(self, value):
        raise NotImplementedError

    def format_key_value(self, key, formatted_value):
        return self.format_value(key) + self.kv_sep + formatted_value

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

    def indent(self, level):
        return "    " * level

    def format_value(self, value):
        return repr(value)

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

    def indent(self, level):
        return "  " * level

    def format_value(self, value):
        return json.dumps(value)

    def terminator(self, is_last):
        return "" if is_last else ","


class Colorizer(Style):
    def __init__(self, **kwargs):
        self.term = kwargs["term"]
        self.colors = {  # map node.kind -> self.term method
            "key": self.term.bright_blue,  # dict keys
            "brackets": self.term.bright_white,  # empty/open/close brackets
            "kv_sep": self.term.bright_white,
            "terminator": self.term.bright_white,
            str: self.term.green,
            type(None): self.term.bright_black,
            None: self.term.white,  # default
        }
        super().__init__(**kwargs)
        self.kv_sep = self._color("kv_sep")(self.kv_sep)

    def _color(self, kind):
        return self.colors.get(kind, self.colors[None])

    def brackets(self, node):
        color = self._color("brackets")
        return tuple(color(s) for s in super().brackets(node))

    def format_value(self, value):
        return self._color(type(value))(super().format_value(value))

    def format_key_value(self, key, formatted_value):
        return (
            self._color("key")(super().format_value(key))
            + self.kv_sep
            + formatted_value
        )

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
                        self.format_key_value(node.key, "")
                    )
                lines = self.term.wrap(ret, subsequent_indent=prefix)
                ret = "\n".join(lines)
            else:  # truncate
                lines = self.term.wrap(ret, width=self.term.width - 1)
                ret = lines[0] + self.term.reverse("̇̇̇…")
        return ret
