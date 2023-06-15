from __future__ import division

import sys
import threading
import time

from blessings import Terminal

from common_tools import *
from config import *

SLEEP_TIME = 0.1


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

        for n, line in self.top_lines.iteritems():
            with self.term.location(0, n):
                for component in line:
                    print(str(component)),

        for n, line in self.bottom_lines.iteritems():
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


class Component(object):
    def __init__(self, value=""):
        self.value = value
        self.active = True

    def set_label(self, value):
        self.value = value

    def updateCallback(self):
        pass

    def set_update(self, func):
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


class CounterComponent(Component):
    def __init__(self, format="{}"):
        self.value = 0
        self.format = format
        self.active = True

    def increment(self):
        self.value += 1

    def __str__(self):
        return self.format.format(self.value)


class ProgressComponent(Component):
    def __init__(
        self,
        label="Progress",
        fill_char="#",
        empty_char=" ",
        expected_size=0,
        progress=0,
    ):
        super(ProgressComponent, self).__init__(label)
        self.expected_size = expected_size
        self.fill_char = fill_char
        self.progress = progress
        self.empty_char = empty_char
        self.term = Terminal()
        self.label = label
        self.units = ["bytes", "KB", "MB", "GB", "TB"]
        self.lastProgress = [0, 0]
        self.lastUpdated = time.time()
        self.timeDiff = 0

        self.value = (expected_size, progress, False)

    def updateCallback(self):
        if (
            self.progress > self.lastProgress[1]
            and time.time() != self.lastUpdated
        ):
            self.lastProgress[0] = self.lastProgress[1]
            self.lastProgress[1] = self.progress
            self.timeDiff = time.time() - self.lastUpdated
            self.lastUpdated = time.time()

    def printableUnits(self, value):
        i = 0
        for i in range(1, len(self.units) + 1):
            if value // pow(1000, i) == 0:
                break
        i -= 1
        return i

    def __str__(self):
        self.progress = self.value[1]
        self.expected_size = self.value[0]

        if self.value[2] and self.progress == self.expected_size:
            self.fill_char = "V"

        i = self.printableUnits(self.expected_size)
        j = self.printableUnits(self.progress)

        progress = (
            "{0:.3f}".format(self.progress / pow(1000, j))
            + self.units[j]
            + "/"
            + "{0:.3f}".format(self.expected_size / pow(1000, i))
            + self.units[i]
        )
        speed = 0
        if self.timeDiff != 0:
            speed = (
                self.lastProgress[1] - self.lastProgress[0]
            ) / self.timeDiff
        # speed is currently in bytes per second
        k = self.printableUnits(speed)
        progress += (
            " " + "{0:.3f}".format(speed / pow(1000, k)) + self.units[k] + "/s"
        )

        width = self.term.width - len(self.label) - 5 - len(progress)
        if self.expected_size != 0:
            p = self.progress * width // self.expected_size
        else:
            p = 0
        if self.lastProgress < self.progress:
            self.lastProgress = self.progress
        return (
            self.label
            + ": ["
            + self.fill_char * p
            + self.empty_char * (width - p)
            + "]"
            + " "
            + progress
        )
