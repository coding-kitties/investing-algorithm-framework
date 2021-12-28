from investing_algorithm_framework.core.models import TimeFrame


class IntervalsQueue:
    """
    Time intervals queue for logical order of time intervals
    """

    def __init__(self, time_frame):
        self.intervals = TimeFrame.from_value(time_frame).intervals
        self.size = len(self.intervals)
        self.front = self.size - 1

    def pop(self):

        if len(self.intervals) == 0:
            return None
        else:
            interval = self.intervals.pop()
            return interval

    def peek(self):
        """
        Method to get the next time interval in the queue without
        popping it from the stack.

        Returns None if the stack size is smaller than 1.
        """

        if len(self.intervals) == 0:
            return None, None

        return self.intervals[self.front]

    def empty(self):
        return len(self.intervals) == 0

    def __str__(self):
        return str(self.intervals)
