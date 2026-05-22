import math
from dataclasses import dataclass
from enum import Enum

import matplotlib.pyplot as plt

w = [
    0.212,  # w0
    1.2931,  # w1
    2.3065,  # w2
    8.2956,  # w3
    6.4133,  # w4
    0.8334,  # w5
    3.0194,  # w6
    0.001,  # w7
    1.8722,  # w8
    0.1666,  # w9
    0.796,  # w10
    1.4835,  # w11
    0.0614,  # w12
    0.2629,  # w13
    1.6483,  # w14
    0.6014,  # w15
    1.8729,  # w16
    0.5425,  # w17
    0.0912,  # w18
    0.0658,  # w19
    0.1542,  # w20
]


class Grade(Enum):
    """
    Forgot is counted as fail to recall the memory.
    Others are counted as success.
    """

    Forgot = 1
    Hard = 2
    Good = 3
    Easy = 4


def retrievability(t: float, s: float) -> float:
    """
    Calculate the retrievability of a card,
    given the current time [0, +inf) and the stability.
    """
    factor = 0.9 ** (-1 / w[20]) - 1
    return (1 + factor * t / s) ** -w[20]


def interval(s: float, dr: float) -> float:
    """
    Calculate the interval of a card,
    given the desired retention and the stability.
    """
    factor = 0.9 ** (-1 / w[20]) - 1
    return s / factor * (dr ** (-1 / w[20]) - 1)


# ------ Updating Stability ---------
def stability_0(g: Grade) -> float:
    return w[g.value - 1]


def stability_success(g: Grade, s: float, d: float, r: float) -> float:
    # only accept successful Grade, which are either Hard, Good, Easy
    # memory stability cannot decrease if the review was successful.
    f_d = 11 - d  # d is difficulty
    f_s = s ** (-w[9])  # s is stability
    f_r = math.exp(w[10] * (1 - r)) - 1  # r is retrievability

    scaler = math.exp(w[8])
    if g == Grade.Hard:
        scaler *= w[15]
    if g == Grade.Easy:
        scaler *= w[16]

    s_inc = 1 + scaler * f_d * f_s * f_r
    s_new = s * s_inc
    return s_new


def stability_fail(s: float, d: float, r: float) -> float:
    # only use with failure Grade, which is Forgot
    f_d = d ** (-w[12])  # d is difficulty
    f_s = (s + 1) ** w[13] - 1  # s is stability
    f_r = math.exp(w[14] * (1 - r))  # r is retrievability
    scaler = w[11]

    s_new = min(scaler * f_d * f_s * f_r, s)
    return s_new


def stability_short(g: Grade, s: float) -> float:
    # used for same-day reviews
    # short-term memory
    # Good and Easy cannot decrease S, Hard and Again can.
    # This is different from the success formula, where Hard cannot decrease S.
    return s * math.exp(w[17] * (g.value - 3 + w[18])) * s ** (-w[19])


def stability(g: Grade, s: float, d: float, r: float):
    if g == Grade.Forgot:
        return stability_fail(s, d, r)
    return stability_success(g, s, d, r)


# ------ Updating Difficulty ---------
# Difficulty has no precise definition and is just a crude heuristic.
# Updating difficulty basically works like this:
# Again = add a lot
# Hard = add a little bit
# Good = nothing
# Easy = subtract a little bit


def clamp_d(d: float) -> float:
    return max(1, min(10, d))


def difficulty_0(g: Grade) -> float:
    return clamp_d(w[4] - math.exp(w[5] * g.value - 1) + 1)


def difficulty(g: Grade, d: float) -> float:
    # calculate the change in difficulty that only depends on the grade
    d_delta = -w[6] * (g.value - 3)

    # as difficulty approaches 10 (maximum value),
    # each update gets smaller and smaller.
    d_prime = d + d_delta * (10 - d) / 9

    # the current value of D is slightly reverted back to
    # the default value that corresponds to the Easy button
    return clamp_d(w[7] * difficulty_0(Grade.Easy) + (1 - w[7]) * d_prime)


# --------- Simulation ---------


@dataclass
class Step:
    """
    The state of a memory

    Attributes:
        t (float): The current time
        s (float): The stability [0, +inf). Time in days for retrievability \
            decreases to the desired retention (often 0.9).
        d (float): How hard it is to increase the stability [1, 10].
        i (float): Next interval.
    """

    t: float
    s: float
    d: float
    i: float


def sim(grades: list[Grade]) -> list[Step]:
    steps = []

    # initial state
    t = 0
    desired_retention = 0.9

    # initial review
    first_grade = grades.pop(0)

    s = stability_0(first_grade)
    d = difficulty_0(first_grade)

    i = interval(s, desired_retention)
    steps.append(Step(t, s, d, i))
    print(steps[-1])
    # n-th review
    for g in grades:
        r = retrievability(i, s)  # used to calculate loss

        # next memory state from the previous state
        s = stability(g, s, d, r)
        d = difficulty(g, d)

        # next 'perfect' review time
        i = interval(s, desired_retention)

        t += i
        steps.append(Step(t, s, d, i))
        print(steps[-1])
    return steps


def plot_simulations(inputs):
    for seq in inputs:
        grades = [Grade(float(n)) for n in seq]
        steps = sim(grades)

        t_values = [step.t for step in steps]
        s_values = [step.s for step in steps]

        plt.plot(t_values, s_values, marker="o", label=seq)

    plt.xlabel("t (time)")
    plt.ylabel("s (stability)")
    plt.title("Stability over Time")
    plt.legend()
    plt.grid(True)

    plt.show()


if __name__ == "__main__":
    inputs = ["1214", "1322"]
    plot_simulations(inputs)
