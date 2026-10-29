"""Tally helpers for the render queue."""


def total(items):
    running = 0
    for item in items:
        running += item
    return running


def mean(items):
    return total(items) / len(items)
