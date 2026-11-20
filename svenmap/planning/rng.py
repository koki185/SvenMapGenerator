"""Независимые детерминированные потоки случайности.

Изменение декора не должно менять топологию, поэтому каждый подсистем
получает свой RNG, выведенный из master seed.
"""

import random


def make_rng(seed: int, subsystem: str) -> random.Random:
    return random.Random("{}:{}".format(int(seed), subsystem))
