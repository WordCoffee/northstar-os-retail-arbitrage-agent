"""Tiny arithmetic helpers used by the billing report."""


def add(a, b):
    return a + b


def subtract(a, b):
    return add(a, -b)


def total(values):
    running = 0
    for value in values:
        running = add(running, value)
    return running
