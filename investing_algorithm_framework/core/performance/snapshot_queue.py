class SnapShotQueue:
    """
    Snapshot queue for logical order of snapshots. This data structure is
    useful to calculate the active time frame of a specific snapshot.

    e.g. snapshot is active from start time (snapshot.created_at) until
    end time (snapshot_peek.created_at)
    """

    def __init__(self, snapshots):
        self.queue = []

        for snapshot in snapshots:
            self.queue.append(snapshot)

        self.size = len(snapshots)
        self.front = self.size - 1

    def pop(self):

        if len(self.queue) == 0:
            return None
        else:
            self.size -= 1
            self.front -= 1
            # Get the first item of the queue
            return self.queue.pop()

    def peek(self):
        """
        Method to get the next snapshot in the queue without
        popping it from the stack.

        Returns None if the stack size is smaller than 1.
        """

        if len(self.queue) == 0:
            return None

        return self.queue[self.front]

    def empty(self):
        return len(self.queue) == 0

    def __str__(self):
        return str(self.queue)
