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

    def __init__(self, root, term, style_class):
        self.root = root
        self.term = term
        self.style_class = style_class

        # Main UI state variables
        self.lines = []  # from self.render()
        self.nodes = []  # Node objects corresponding to self.lines
        self.focus = 0  # currently focused/selected index in .lines/.nodes
        self.viewport = (0, 0)  # line span currently visible

        # Misc. state/communication variables
        self._need_render = True  # must rerender all lines from scratch
        self._need_draw = True  # must redraw current viewport
        self._quit = False  # time to quit
        self._status = None  # custom status line
        self._timeout = None  # used to reset status line

    # Actions triggered from input

    def set_focus(self, line):
        self.focus = clamp(line, 0, len(self.lines) - 1)
        self.adjust_viewport()

    def move_focus(self, relative):
        return self.set_focus(self.focus + relative)

    def collapse(self):
        node = self.nodes[self.focus]
        if node.collapsed:
            return  # already collapsed
        node.collapsed = True
        nodelines = [i for i, n in enumerate(self.nodes) if n is node]
        start, end = nodelines[0], nodelines[-1]
        lines, nodes = map(list, zip(*style.draw_nodes(node)))
        self.nodes[start : end + 1] = nodes
        self.lines[start : end + 1] = lines
        self.focus = start
        self.adjust_viewport()

    def expand(self):
        node = self.nodes[self.focus]
        if not node.collapsed:
            return  # already expanded
        node.collapsed = False
        lines, nodes = map(list, zip(*style.draw_nodes(node)))
        self.nodes[self.focus : self.focus + 1] = nodes
        self.lines[self.focus : self.focus + 1] = lines
        self.adjust_viewport()

    def on_resize(self):
        self._need_render = True
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
            "KEY_HOME": partial(self.set_focus, 0),
            "KEY_END": partial(self.set_focus, len(self.lines) - 1),
            # collapse/expand
            "KEY_LEFT": self.collapse,
            "KEY_RIGHT": self.expand,
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

    def reset_status(self):
        self._status = None
        self._timeout = None
        self.draw_status()

    def adjust_viewport(self):
        height = self.term.height - 2
        start, _ = self.viewport

        if self.focus < start:  # scroll viewport up
            start = self.focus - self.context_lines
        elif self.focus > start + height:  # scroll viewport down
            start = self.focus + self.context_lines - height
        # Keep viewport within rendered lines
        start = max(0, min(len(self.lines) - 1, start + height) - height)

        self.viewport = (start, start + height)
        self._need_draw = True

    def status(self):
        if self._status is None:  # use default
            node = self.nodes[self.focus]
            return self.term.ljust(
                f"{node.name} - ({self.focus + 1}/{len(self.lines)} lines) -"
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
        my_style = self.style_class(term=self.term)
        self.lines, self.nodes = map(
            list, zip(*style.render_nodes(self.root, my_style))
        )
        self.adjust_viewport()
        self._need_render = False

    @debug_time
    def draw(self):
        print(self.term.home + self.term.clear, end="")
        start, end = self.viewport
        for n, line in enumerate(self.lines[start : end + 1], start):
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


class MyStyle(style.TruncateLines, style.SyntaxColor, style.JSONStyle):
    pass


# TODO:
# - We need to _pull_ rendered strings on demand. Too expensive to render
#   everything up-front.
# - instead of ._need_draw == True/False, we need a span (or list?) or lines
#   to be redrawn
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
    ui = UI(root, term, MyStyle)
    if term.is_a_tty:
        ui.run()
    else:
        ui.dump()


if __name__ == "__main__":
    main()
