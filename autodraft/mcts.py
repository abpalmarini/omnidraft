# Implementation of the Monte Carlo Tree Search used by AlphaZero:
# https://www.nature.com/articles/nature24270
# https://science.sciencemag.org/content/362/6419/1140


class Node:

    def __init__(self, prior):
        self.visit_count = 0
        self.value_sum = 0
        self.prior = prior
        self.to_select = -1
        self.children = {}

    def value(self):
        if self.visit_count == 0:
            return 0
        return self.value_sum / self.visit_count

    def expanded(self):
        return bool(self.children)
