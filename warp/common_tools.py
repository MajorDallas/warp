import errno
import hashlib
import os
import signal
import sys
from functools import wraps
from typing import List, Tuple, Union

from config import CHUNK_SIZE, logger


def getHash(file):
    """
    Returns a sha256 hash for the specified file.
    Eventually sent to server to check for restarts.
    """
    hash = hashlib.sha256()
    # i = 0
    with open(file, "rb") as file:
        # while True:
        while data := file.read(CHUNK_SIZE):
            # data = file.read(CHUNK_SIZE)
            # if not data or (block_count != 0 and i >= block_count):
            # file.close()
            # return hash.hexdigest()
            # i += 1
            hash.update(data)
    return hash.hexdigest()


def fail(msg):
    """
    Simple fail function that prints and logs the error message and then exits.
    """
    logger.error(msg)
    sys.stderr.write(msg)
    sys.exit(1)


# from: http://stackoverflow.com/questions/2281850/timeout-function-if-it-takes-too-long-to-finish


# renamed so as not to conflict with stdlib's TimeoutError.
class ApplicationTimeoutError(Exception):
    pass


# This doesn't appear to be used anywhere...
def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise ApplicationTimeoutError(error_message)

        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wraps(func)(wrapper)

    return decorator


# Credit: Mitch McMabers, https://stackoverflow.com/a/63839503

LabelList = Tuple[str, str, str, str, str, str, str, str, str]

class HumanBytes:
    # fmt: off
    METRIC_LABELS: LabelList = ("B", "kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    BINARY_LABELS: LabelList = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
    PRECISION_OFFSETS: Tuple[float, ...] = (0.5, 0.05, 0.005, 0.0005) # PREDEFINED FOR SPEED.
    PRECISION_FORMATS: Tuple[str, ...] = ("{}{:.0f} {}", "{}{:.1f} {}", "{}{:.2f} {}", "{}{:.3f} {}") # PREDEFINED FOR SPEED.
    # fmt: on

    @staticmethod
    def format(
        num: Union[int, float], metric: bool = False, precision: int = 1
    ) -> str:
        """
        Human-readable formatting of bytes, using binary (powers of 1024)
        or metric (powers of 1000) representation.
        """
        assert isinstance(num, (int, float)), "num must be an int or float"
        assert isinstance(metric, bool), "metric must be a bool"
        assert (
            isinstance(precision, int) and precision >= 0 and precision <= 3
        ), "precision must be an int (range 0-3)"
        unit_labels = (
            HumanBytes.METRIC_LABELS if metric else HumanBytes.BINARY_LABELS
        )
        last_label = unit_labels[-1]
        unit_step = 1000 if metric else 1024
        unit_step_thresh = unit_step - HumanBytes.PRECISION_OFFSETS[precision]

        is_negative = num < 0
        if (
            is_negative
        ):  # Faster than ternary assignment or always running abs().
            num = abs(num)

        for unit in unit_labels:
            if num < unit_step_thresh:
                # VERY IMPORTANT:
                # Only accepts the CURRENT unit if we're BELOW the threshold where
                # float rounding behavior would place us into the NEXT unit: F.ex.
                # when rounding a float to 1 decimal, any number ">= 1023.95" will
                # be rounded to "1024.0". Obviously we don't want ugly output such
                # as "1024.0 KiB", since the proper term for that is "1.0 MiB".
                break
            if unit != last_label:
                # We only shrink the number if we HAVEN'T reached the last unit.
                # NOTE: These looped divisions accumulate floating point rounding
                # errors, but each new division pushes the rounding errors further
                # and further down in the decimals, so it doesn't matter at all.
                num /= unit_step

        return HumanBytes.PRECISION_FORMATS[precision].format(
            "-" if is_negative else "", num, unit  # type: ignore
        )
