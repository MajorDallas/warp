from __future__ import division

import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable, Generic, Tuple, TypeVar, Union

from blessings import Terminal

from common_tools import HumanBytes

SLEEP_TIME = 0.1

T = TypeVar("T")


class WarpInterface(object):
    def __init__(self):
        self.screen = Screen()

        self.progress_bar = ProgressComponent()
        self.screen.add_component(self.progress_bar, to_bottom=True)

        self.status_line = Line()
        self.files_sent_indicator = CounterComponent(format="Sent {} files. ")
        self.files_processed_indicator = CounterComponent(
            format="Processed {} files."
        )
        self.status_line.add_component(self.files_sent_indicator)
        self.status_line.add_component(self.files_processed_indicator)
        self.screen.add_line(self.status_line, to_bottom=True)

    def log_message(self, message):
        self.screen.add_component(Component(message))
        self.redraw()

    def redraw(self):
        self.screen.redraw()

    def exit(self):
        self.screen.exit()


class Screen(object):
    def __init__(self):
        self.term = Terminal()
        self.top_lines = {}
        self.bottom_lines = {}
        self.next_line_top = 0
        self.next_line_bottom = 1

        print(self.term.enter_fullscreen())

    def redraw(self):
        print(self.term.clear())

        for n, line in self.top_lines.items():
            with self.term.location(0, n):
                for component in line:
                    print(str(component)),

        for n, line in self.bottom_lines.items():
            with self.term.location(0, self.term.height - n):
                for component in line:
                    print(str(component)),

        sys.stdout.flush()

    def add_line(self, line, to_bottom=False):
        if to_bottom is False:
            self.top_lines[self.next_line_top] = line
            self.next_line_top += 1
        else:
            self.bottom_lines[self.next_line_bottom] = line
            self.next_line_bottom += 1

    def add_component(self, component, to_bottom=False):
        if to_bottom is False:
            self.top_lines[self.next_line_top] = Line(comp=component)
            self.next_line_top += 1
        else:
            self.bottom_lines[self.next_line_bottom] = Line(comp=component)
            self.next_line_bottom += 1

    def exit(self):
        print(self.term.clear())
        print(self.term.exit_fullscreen())


class Line(object):
    def __init__(self, comp=None):
        self.components = []

        if comp is not None:
            self.components.append(comp)

    def add_component(self, component):
        self.components.append(component)

    def __iter__(self):
        for each in self.components:
            yield each


class Component(Generic[T]):
    value: T

    def __init__(self, value=""):
        self.value = value
        self.active = True

    def set_label(self, value):
        self.value = value

    def updateCallback(self):
        pass

    def set_update(self, func: Callable[[], T]):
        def update():
            while self.active:
                try:
                    self.value = func()
                    self.updateCallback()
                except Exception:
                    break
                time.sleep(SLEEP_TIME)

        thread = threading.Thread(target=update)
        thread.setDaemon(True)
        thread.start()

    def __str__(self):
        return self.value


class CounterComponent(Component[int]):
    def __init__(self, format="{}"):
        self.value = 0
        self.format = format
        self.active = True

    def increment(self):
        self.value += 1

    def __str__(self):
        return self.format.format(self.value)


@dataclass
class LastProgress:
    last: int = 0
    current: int = 0

    def __getitem__(self, i: int) -> int:
        return self.last if i == 0 else self.current


class ProgressComponent(Component[Tuple[int, int, bool]]):
    units = ("bytes", "KB", "MB", "GB", "TB")

    def __init__(
        self,
        label="Progress",
        fill_char="#",
        empty_char=" ",
        expected_size: int = 0,
        progress: int = 0,
    ):
        super(ProgressComponent, self).__init__(label)
        self.expected_size = expected_size
        self.fill_char = fill_char
        self.progress = progress
        self.empty_char = empty_char
        self.term = Terminal()
        self.label = label
        self.lastProgress = LastProgress(0, 0)
        self.lastUpdated = time.time()
        self.timeDiff = 0
        self.value = (expected_size, progress, False)

    def updateCallback(self):
        """Update lastProgress, lastUpdated, and timeDiff if progress is greater
        than lastProgress.current and time has elapsed.

        self.progress is NOT updated here, but in __str__. Its updated value
        comes from self.value[1], which is set in a thread started by
        set_update.
        """
        if (
            self.progress > self.lastProgress.current
            and time.time() != self.lastUpdated
        ):
            self.lastProgress.last = self.lastProgress.current
            self.lastProgress.current = self.progress
            self.timeDiff = (new_time := time.time()) - self.lastUpdated
            self.lastUpdated = new_time

    def __str__(self):
        # self.value is updated in the update closure created by set_update and
        # offloaded to a thread.
        self.progress = self.value[1]
        self.expected_size = self.value[0]
        if self.value[2] and self.progress == self.expected_size:
            self.fill_char = "V"
        if self.timeDiff != 0:
            # speed is currently in bytes per second
            speed = (
                self.lastProgress[1] - self.lastProgress[0]
            ) / self.timeDiff
        else:
            speed = 0
        progress = (
            "{} / {}  {}/s".format(
                HumanBytes.format(self.progress, True, 3),
                HumanBytes.format(self.expected_size, True, 3),
                HumanBytes.format(speed, True, 3),
            )
        )
        width = self.term.width - len(self.label) - 5 - len(progress)
        if self.expected_size != 0:
            p = self.progress * width // self.expected_size
        else:
            p = 0
        if self.lastProgress.current < self.progress:
            self.lastProgress.current = self.progress
            # Screen.redraw() prints this Component every 0.1s.
            # The value attr gets updated in a thread via the `update` closure
            # defined in Component.set_update, also every 0.1s.
            # updateCallback is called mere nanoseconds after self.value is
            # updated by the set_update thread.
            # I'm honestly not sure there's any point to advancing lastProgress
            # by a few nanoseconds, but I wasn't there nine years ago to ask
            # Noah what his rationale was; alls I can do is fix the `list < int`
            # bug that was here before.
        return "{}: [{}{}] {}".format(
            self.label,
            self.fill_char * p,
            self.empty_char * (width - p),
            progress,
        )
