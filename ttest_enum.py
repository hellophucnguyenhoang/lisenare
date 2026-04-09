from enum import Enum


class Status(str, Enum):
    pending = "a"
    paying = "b"


a = Status.pending

print(a == Status.pending)
