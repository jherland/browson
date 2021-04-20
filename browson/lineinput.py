from contextlib import suppress
from functools import partial
import logging

from blessed import Terminal

logger = logging.getLogger(__name__)


class LineInput:
    def __init__(self, term: Terminal, prompt: str = "> ", value: str = ""):
        self.term = term
        self.prompt = prompt
        self.value = value
        self.done = False

    def draw(self):
        return self.prompt + self.value

    # Input handlers

    def submit(self):
        self.done = True

    def dismiss(self):
        self.done = True

    def backspace(self):
        self.value = self.value[:-1]

    def clear(self):
        self.value = ""

    def add_char(self, keystroke):
        # Ignore multi-byte sequences and control chars
        if keystroke.is_sequence or ord(keystroke) < ord(" "):
            logger.warning(f"Unknown key {keystroke!r}")
        else:
            self.value += str(keystroke)

    # Keyboard input

    def handle_key(self, keystroke):
        logger.debug(f"Got keystroke: {(str(keystroke), keystroke.name)!r}")
        keymap = {
            "KEY_ENTER": self.submit,
            "KEY_ESCAPE": self.dismiss,
            "KEY_BACKSPACE": self.backspace,
            "KEY_DELETE": self.backspace,
            "\x17": self.clear,  # Ctrl+W
            None: partial(self.add_char, keystroke),
        }
        for key in [str(keystroke), keystroke.name, None]:
            with suppress(KeyError):
                return keymap[key]
