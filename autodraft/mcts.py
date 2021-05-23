# Implementation of the Monte Carlo Tree Search used by AlphaZero:
# https://www.nature.com/articles/nature24270
# https://science.sciencemag.org/content/362/6419/1140


import math
import numpy as np


# A node in the MCTS represents a state-action pair. The to_select
# attribute refers to the team that could select the action the 
# node refers to.
class Node:

    def __init__(self, prior, to_select):
        self.visit_count = 0
        self.value_sum = 0
        self.prior = prior
        self.to_select = to_select
        self.children = {}

    def value(self):
        if self.visit_count == 0:
            return 0
        return self.value_sum / self.visit_count

    def expanded(self):
        return bool(self.children)

    def add_exploration_noise(self, config):
        actions = self.children.keys()
        alpha = [config.root_dirichlet_alpha] * len(actions)
        dir_noise = np.random.default_rng().dirichlet(alpha)
        frac = config.root_exploration_fraction
        def add_noise(node, noise):
            node.prior = (1 - frac) * node.prior + frac * noise
        for action, noise in zip(actions, dir_noise):
            add_noise(self.children[action], noise)


def run_mcts(config, draft, network, root=None):
    if root is None:
        root = Node(None, None)
        evaluate(root, draft, network)
    if config.root_dirichlet_alpha is not None:
        root.add_exploration_noise(config)


def evaluate(node, draft, network):
    # @Change once I implement NN and know how to handle evaluation
    policy_logits, value = network(draft.make_nn_input(-1), True)
    policy = {a: math.exp(policy_logits[a]) for a in draft.legal_actions()}
    policy_sum = sum(policy.values())
    to_select = draft.to_select()
    for action, p in policy.items():
        node.children[action] = Node(p / policy_sum, to_select)
    return value
