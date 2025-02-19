class PeekableQueue:
    def __init__(self, items=[]):
        self.queue = items
        self.index = 0

    def enqueue(self, item):
        self.queue.append(item)

    def dequeue(self):
        if not self.is_empty():
            return self.queue.pop(0)
        else:
            raise IndexError("Queue is empty")

    def peek(self):
        if not self.is_empty():
            return self.queue[0]
        else:
            raise IndexError("Queue is empty")

    def is_empty(self):
        return len(self.queue) == 0

    def __len__(self):
        return len(self.queue)

    @property
    def size(self):
        return len(self.queue)

    def __iter__(self):
        self.index = 0
        return self

    def __next__(self):
        if self.index < len(self.queue):
            result = self.queue[self.index]
            self.index += 1
            return result
        else:
            self.index = 0  # Reset index for next iteration
            raise StopIteration
