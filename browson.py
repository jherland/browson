#!/usr/bin/env python3
from contextlib import contextmanager, suppress
from functools import partial, wraps
import json
import logging
import signal
import sys
from time import monotonic as now

from blessed import Terminal

from node import Node
import style

logger = logging.getLogger("browson")


def clamp(val, minimum, maximum):
    assert maximum >= minimum
    return minimum if val < minimum else maximum if val > maximum else val


def debug_time(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            t = now()
            return f(*args, **kwargs)
        finally:
            logger.debug(f"{f.__name__} took {now() - t}s")

    return wrapper


@contextmanager
def signal_handler(signalnum, handler):
    """Install the given signal handler for the duration of this context."""

    def wrapped_handler(signum, frame):
        logger.debug(f"signal handler invoked with {signum}, {frame}")
        handler()

    prev = signal.signal(signalnum, wrapped_handler)
    try:
        yield
    finally:
        signal.signal(signalnum, prev)


class ResizeEvent(Exception):
    pass


class UI:
    context_lines = 1  # how many context lines around the focused line?

    def __init__(self, root, term, style):
        self.root = root
        self.term = term
        self.style = style

        # Main UI state variables
        self.lines = []  # from self.render()
        self.nodes = []  # Node objects corresponding to self.lines
        self.focus = 1  # which line is currently focused (numbered from 1)
        self.viewport = (1, 1)  # line span currently visible

        # Misc. state/communication variables
        self._need_render = True  # must rerender all lines from scratch
        self._need_draw = True  # must redraw current viewport
        self._quit = False  # time to quit
        self._status = None  # custom status line
        self._timeout = None  # used to reset status line

    # Actions triggered from input

    def reset_status(self):
        self._status = None
        self._timeout = None
        self.draw_status()

    def set_focus(self, line):
        self.focus = clamp(line, 1, len(self.lines))
        self.adjust_viewport()

    def move_focus(self, relative):
        return self.set_focus(self.focus + relative)

    def adjust_viewport(self):
        height = self.term.height - 2
        start, _ = self.viewport

        if self.focus < start:  # scroll viewport up
            start = self.focus - self.context_lines
        elif self.focus > start + height:  # scroll viewport down
            start = self.focus + self.context_lines - height
        # Keep viewport within rendered lines
        start = max(1, min(len(self.lines), start + height) - height)

        self.viewport = (start, start + height)
        self._need_draw = True

    def on_resize(self):
        self.adjust_viewport()
        raise ResizeEvent()  # trigger exit from keyboard polling

    def rerender(self):
        self._need_render = True

    def redraw(self):
        self._need_draw = True

    def quit(self):
        self._quit = True

    def warning(self, message):
        logger.warning(message)
        self._status = self.term.bright_red(self.term.center(message))
        self._timeout = 3
        self.draw_status()

    # End of actions

    def handle_key(self, keystroke):
        logger.debug(f"Got keystroke: {(str(keystroke), keystroke.name)!r}")
        keymap = {
            # focus movement
            "k": partial(self.move_focus, -1),
            "j": partial(self.move_focus, 1),
            "KEY_UP": partial(self.move_focus, -1),
            "KEY_DOWN": partial(self.move_focus, 1),
            "KEY_SUP": partial(self.move_focus, -5),
            "KEY_SDOWN": partial(self.move_focus, 5),
            "KEY_PGUP": partial(self.move_focus, -(self.term.height - 3)),
            "KEY_PGDOWN": partial(self.move_focus, self.term.height - 3),
            "KEY_HOME": partial(self.set_focus, 1),
            "KEY_END": partial(self.set_focus, len(self.lines)),
            # re-render/re-draw
            "KEY_F5": self.rerender,
            "\x0c": self.redraw,  # Ctrl+L
            # quitting
            "q": self.quit,
            "\x04": self.quit,  # EOF, Ctrl+D
            None: partial(self.warning, f"Unknown key {keystroke!r}!"),
        }
        for key in [str(keystroke), keystroke.name, None]:
            with suppress(KeyError):
                return keymap[key]

    def status(self):
        if self._status is None:  # use default
            node = self.nodes[self.focus - 1]
            return self.term.ljust(
                f"{node.name} - ({self.focus}/{len(self.lines)} lines) -"
            )
        else:
            return self._status

    def highlight_line(self, line, variant="on_gray20"):
        return getattr(self.term, variant)(self.term.ljust(line))

    def draw_status(self):
        with self.term.location(0, self.term.height - 1):
            print(
                self.highlight_line(self.status(), "reverse"),
                end="",
                flush=True,
            )

    @debug_time
    def render(self):
        self.lines, self.nodes = zip(
            *style.render_nodes(self.root, self.style)
        )
        assert all("\n" not in line for line in self.lines)
        self.adjust_viewport()
        self._need_render = False

    @debug_time
    def draw(self):
        print(self.term.home + self.term.clear, end="")
        start, end = self.viewport
        for n, line in enumerate(self.lines[start - 1 : end], start):
            if n == self.focus:
                line = self.highlight_line(line)
            print(line)
        self.draw_status()
        self._need_draw = False

    def dump(self):
        self.render()
        print("\n".join(self.lines))

    def run(self):
        term = self.term
        with term.fullscreen(), term.cbreak(), term.hidden_cursor():
            with signal_handler(signal.SIGWINCH, self.on_resize):
                while not self._quit:
                    with suppress(ResizeEvent):
                        if self._need_render:
                            self.render()
                        if self._need_draw:
                            self.draw()
                        keystroke = term.inkey(timeout=self._timeout)
                        self.reset_status()
                        if keystroke:
                            self.handle_key(keystroke)()

        logger.info("Bye!")


# TODO: Move this out of the Style hierarchy and into the UI class.
# Line wrapping should be done at draw time, not at render time
class LineWrapper(style.Style):
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


class MyStyle(style.Colorizer, style.JSONStyle):
    pass


# TODO:
# - move UI into separate module
# - decouple line wrapping from styles.
#   - styles are applied at render time
#   - wrapping is applied at draw time
# - render both multiline/nested and oneline/compact node representations
#   - allow actions to switch between multiline and oneline with quick redraw
# - help window with keymap
# - navigate to matching bracket/parent/sibling
# - search
# - filter
# - expand/collapse


def main():
    # TODO: argparse
    logging.basicConfig(level=logging.DEBUG, filename="./browson.log")
    logger.info(f"Loading data structure from {sys.argv[1]}...")
    with open(sys.argv[1], "rb") as f:
        data = json.load(f)
    logger.info("Building nodes...")
    root = Node.build(data)

    logger.info("Running app...")
    term = Terminal()
    ui = UI(root, term, MyStyle(term=term))
    if term.is_a_tty:
        ui.run()
    else:
        ui.dump()


if __name__ == "__main__":
    main()
