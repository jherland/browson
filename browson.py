#!/usr/bin/env python3
from contextlib import suppress
from functools import partial
import json
import logging
import sys

from blessed import Terminal

from node import Node
from style import PythonStyle, JSONStyle, Colorizer, LineWrapper

logger = logging.getLogger("browson")


def render(node, style):
    prefixes = [""]
    suffixes = [""]

    def prefixes_for_children(n, prefix):
        assert n.children()
        return [prefix + style.indent] * len(n.children(()))

    def suffixes_for_children(n):
        children = n.children()
        assert children
        return [
            style.terminator(i == len(children))
            for i, _ in enumerate(children, 1)
        ]

    def previsit(n):
        nonlocal prefixes, suffixes
        prefix = prefixes.pop(0)
        suffix = suffixes.pop(0)
        if n.children():  # internal node
            s = style.open(n)
            # Prepare prefixes and suffixes for children (incl. postvisit)
            prefixes = prefixes_for_children(n, prefix) + [prefix] + prefixes
            suffixes = suffixes_for_children(n) + [suffix] + suffixes
            suffix = ""  # no suffix after "{"", deferred to after matching "}"
        elif n.children() is not None:  # empty internal node
            s = style.empty(n)
        else:  # leaf node
            s = style.format_value(n.value)

        with suppress(KeyError):
            s = style.format_key_value(n.key, s)
        yield style.format_line(prefix, s, suffix, n)

    def postvisit(n):
        if n.children():  # internal node
            prefix = prefixes.pop(0)
            suffix = suffixes.pop(0)
            s = style.close(n)
            yield style.format_line(prefix, s, suffix, n)

    yield from node.dfwalk(previsit, postvisit)


def clamp(val, minimum, maximum):
    assert maximum >= minimum
    return minimum if val < minimum else maximum if val > maximum else val


class UI:
    def __init__(self, term, style):
        self.term = term
        self.style = style
        self._quit = False  # set to True when user wants to quit
        self._status = None  # special status message
        self._timeout = None  # used to wipe error messages
        self._focus = 1  # which node/line is currently focused

        self.lines = []

    def reset_status(self):
        self._status = None
        self._timeout = None

    def move_focus(self, relative):
        self._focus = clamp(self._focus + relative, 1, len(self.lines))

    def quit(self):
        self._quit = True

    def error(self, message):
        self._status = self.term.bright_red(message)
        self._timeout = 3

    def handle_key(self, keystroke):
        logger.debug(f"Got keystroke: {(str(keystroke), keystroke.name)!r}")
        keymap = {
            "k": partial(self.move_focus, -1),
            "j": partial(self.move_focus, 1),
            "KEY_UP": partial(self.move_focus, -1),
            "KEY_DOWN": partial(self.move_focus, 1),
            "KEY_SUP": partial(self.move_focus, -5),
            "KEY_SDOWN": partial(self.move_focus, 5),
            "KEY_PGUP": partial(self.move_focus, -(self.term.height - 3)),
            "KEY_PGDOWN": partial(self.move_focus, self.term.height - 3),
            # TODO:
            # - help window with keymap
            # - navigate to matching bracket/parent/sibling
            # - search
            # - filter
            # - expand/collapse
            # - SPEED (do not rerender everything)!
            "q": self.quit,
            "\x04": self.quit,  # EOF
            None: partial(self.error, f"Unknown key {keystroke!r}!"),
        }
        for key in [str(keystroke), keystroke.name, None]:
            with suppress(KeyError):
                return keymap[key]

    def status(self):
        if self._status is not None:
            return self._status
        else:
            return f"--- ({self._focus}/{len(self.lines)} lines)"

    def run(self, root):
        term = self.term
        interactive = term.is_a_tty
        # if True:
        with term.fullscreen(), term.cbreak(), term.hidden_cursor():
            while not self._quit:
                self.lines = list(render(root, self.style))
                # assert all("\n" not in line for line in lines)
                print(term.home + term.clear, end="")
                for n, line in enumerate(self.lines, 1):
                    if n == self._focus:
                        line = term.reverse(line)
                    print(line)
                if not interactive:
                    break
                print(self.status(), end="", flush=True)
                keystroke = term.inkey(timeout=self._timeout)
                self.reset_status()
                if keystroke:
                    self.handle_key(keystroke)()

        logger.info("Bye!")


class MyStyle(LineWrapper, Colorizer, JSONStyle):
    pass


def main():
    # TODO: argparse
    logging.basicConfig(level=logging.DEBUG, filename="./browson.log")
    logger.info(f"Loading data structure from {sys.argv[1]}...")
    with open(sys.argv[1], "rb") as f:
        data = json.load(f)
    logger.info("Building nodes...")
    node = Node.build(data)

    logger.info("Running app...")
    term = Terminal()
    UI(term, MyStyle(term=term)).run(node)


if __name__ == "__main__":
    main()
