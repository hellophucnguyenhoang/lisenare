from enum import Enum


class Status(str, Enum):
    pending = "a"
    paying = "b"
    complete = "c"


my_enum = Status.pending
print(my_enum)  # Status.pending
print(my_enum.name)  # pending
print(my_enum.value)  # a
print(str(my_enum))  # Status.pending
print(my_enum == Status.pending)  # True
print(Status("a"))  # Status.pending
print(Status["pending"])  # Status.pending
