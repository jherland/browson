#!/usr/bin/env python3
from contextlib import suppress
from functools import partial
import json
import logging
import signal
import sys

from blessed import Terminal

import style
from lineinput import LineInput
from nodeview import NodeView
from utils import debug_time, signal_handler

logger = logging.getLogger("browson")


class ResizeEvent(Exception):
    pass


class UI:
    def __init__(self, root, term, style):
        self.term = term
        self.view = NodeView(root, *self.view_size, style)
        self.input = None

        # Misc. state/communication variables
        self._search = ""  # current search string (empty - no search)
        self._resized = True  # must handle recent window resize
        self._quit = False  # time to quit
        self._status = None  # custom status line
        self._status_color = self.term.normal  # status line color
        self._timeout = None  # used to reset status line

    @property
    def view_size(self):
        return self.term.width, self.term.height - 2

    @property
    def status_y(self):
        return self.term.height - 1

    # Input handlers

    def redraw(self):
        self.view.need_redraw = True

    def quit(self):
        self._quit = True

    def warning(self, message):
        logger.warning(message)
        self._status = message
        self._status_color = self.term.bright_red
        self._timeout = 3
        self.draw_status()

    def search(self):
        self.input = LineInput(self.term, "Search: ", self._search)
        self._status_color = self.term.bright_yellow
        self.draw_status()

    # Keyboard input

    @debug_time
    def handle_key(self, keystroke):
        logger.debug(f"Got keystroke: {(str(keystroke), keystroke.name)!r}")
        keymap = {
            # focus movement
            "k": partial(self.view.move_focus, -1),
            "j": partial(self.view.move_focus, 1),
            "KEY_UP": partial(self.view.move_focus, -1),
            "KEY_DOWN": partial(self.view.move_focus, 1),
            "KEY_SUP": partial(self.view.move_focus, -5),
            "KEY_SDOWN": partial(self.view.move_focus, 5),
            "KEY_PGUP": partial(self.view.move_focus, -(self.view.height)),
            "KEY_PGDOWN": partial(self.view.move_focus, self.view.height),
            "KEY_HOME": partial(self.view.move_focus, -sys.maxsize),
            "KEY_END": partial(self.view.move_focus, +sys.maxsize),
            "[": partial(self.view.jump_node, forwards=False),
            "]": partial(self.view.jump_node, forwards=True),
            # collapse/expand
            "KEY_LEFT": self.view.collapse_current,
            "c": self.view.collapse_other,
            "C": self.view.collapse_all,
            "KEY_RIGHT": self.view.expand_current,
            "x": self.view.expand_below,
            "X": self.view.expand_all,
            # search
            "/": self.search,
            # re-render/re-draw
            "KEY_F5": self.view.rerender_all,
            "\x0c": self.redraw,  # Ctrl+L
            # quitting
            "q": self.quit,
            "\x04": self.quit,  # EOF, Ctrl+D
            None: partial(self.warning, f"Unknown key {keystroke!r}!"),
        }
        for key in [str(keystroke), keystroke.name, None]:
            with suppress(KeyError):
                return keymap[key]

    # Resize handling

    def handle_resize(self):
        self.view.resize(*self.view_size)
        self._resized = False

    def on_resize(self):
        self._resized = True
        raise ResizeEvent()  # trigger exit from keyboard polling

    # Status bar

    def reset_status(self):
        self._status = None
        self._status_color = self.term.normal
        self.input = None
        self._timeout = None
        self.draw_status()

    def status_text(self):
        if self._status is not None:
            return self._status
        else:  # use default
            node = self.view.current_node()
            cur, total = self.view.current_position()
            message = f"{node.name} - ({cur}/{total} lines) -"
        return message

    def draw_status(self):
        pre = self.term.move_xy(0, self.status_y) + self._status_color
        if self.input:  # show line input + cursor
            text = self.input.draw()
            cursor = (self.term.length(text), self.status_y)
            post = self.term.move_xy(*cursor) + self.term.normal_cursor
        else:  # show status text
            text = self.status_text()
            post = self.term.hide_cursor

        line = self.term.reverse(self.term.ljust(text))
        print(pre + line + post, end="", flush=True)

    # Main UI loop

    def run(self):
        with self.term.fullscreen(), self.term.cbreak():
            with signal_handler(signal.SIGWINCH, self.on_resize):
                while not self._quit:  # main loop
                    try:
                        if self._resized:
                            self.handle_resize()
                        if self.view.need_redraw:
                            print(self.term.home + self.term.clear, end="")
                            for line in self.view.draw(self.term):
                                print(line)
                            self.draw_status()
                        keystroke = self.term.inkey(timeout=self._timeout)
                        if keystroke and self.input:  # redirect to line input
                            self.input.handle_key(keystroke)()
                            if self._search != self.input.value:
                                self._search = self.input.value
                                # TODO: self.view.need_redraw = True ???
                            self.draw_status()
                            if self.input.done:
                                self.reset_status()
                        else:
                            self.reset_status()
                            if keystroke:
                                self.handle_key(keystroke)()
                    except ResizeEvent:
                        self._resized = True

        logger.info("Bye!")


class MyStyle(style.TruncateLines, style.SyntaxColor, style.JSONStyle):
    pass


# TODO:
# - We need to _pull_ rendered strings on demand. Too expensive to render
#   everything up-front.
# - help window with keymap
# - search
# - filter
# - expand only nodes that match the current search
# - expand only the focused node (and its parents)


def dump(root, style):
    for line, _ in root.render(style):
        print(line)


def main():
    # TODO: argparse
    logging.basicConfig(
        level=logging.DEBUG,
        filename="./browson.log",
        format="%(asctime)s %(name)s:%(levelname)s %(message)s",
    )

    logger.info(f"Loading data structure from {sys.argv[1]}...")
    with open(sys.argv[1], "rb") as f:
        data = json.load(f)

    logger.info("Building nodes...")
    root = style.DrawableNode.build(data)
    term = Terminal()
    mystyle = MyStyle(term=term)

    if term.is_a_tty:
        logger.info("Running app...")
        ui = UI(root, term, mystyle)
        ui.run()
    else:
        dump(root, mystyle)


if __name__ == "__main__":
    main()
