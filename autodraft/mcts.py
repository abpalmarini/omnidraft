# Implementation of the Monte Carlo Tree Search used by AlphaZero:
# https://www.nature.com/articles/nature24270
# https://science.sciencemag.org/content/362/6419/1140


import math
import numpy as np


# A node in the MCTS represents a state-action pair. The to_select
# attribute refers to the team that could select the action the 
# node is representing.
class Node:

    def __init__(self, prior, to_select):
        self.visit_count = 0
        self.value_sum = 0
        self.value = 0
        self.prior = prior
        self.to_select = to_select
        self.children = {}

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
        expand_and_evaluate(root, draft, network)
    root.add_exploration_noise(config)

    for _ in range(config.num_simulations):
        simulator_draft = draft.clone()
        node = root
        search_path = [node]
        while node.expanded():
            action, node = select_child(config, node)
            simulator_draft.apply(action)
            search_path.append(node)
        # TODO
        # * evaluate node (taking into account it could be terminal)
        # * backup value


# As explained in the AlphaZero paper; we select an action in the tree
# based on the combination of having a high action-value, high prior
# probability and low visit count. The exploration rate will grow
# slowly with parent visits, giving a higher weight to children with a
# low visit count. However, the more a parent is visited the less
# impactful having a low visit count will be--with the search favouring
# children who have accumulated high action-values.
def select_child(config, parent):
    exploration_rate = math.log((1 + parent.visit_count + config.pb_c_base)
                                / config.pb_c_base) + config.pb_c_init
    sqrt_parent_visit = math.sqrt(parent.visit_count)

    def ucb_score(child):
        visit_ratio = sqrt_parent_visit / (1 + child.visit_count)
        return exploration_rate * child.prior * visit_ratio

    _, action, child = max((child.value + ucb_score(child), action, child)
                           for action, child in parent.children.items())
    return action, child

# To expand a node we have the NN evaluate the current state. The
# network outputs move probabilities based on what it initially
# believes is best. A child node is created for each legal action and
# inititalised with the network's prior belief for selecting it. The
# network also outputs a value indicating how much reward it believes
# it can get from the current state. This value is returned so it can
# be backed up the tree.
def expand_and_evaluate(node, draft, network):
    policy_logits, value = network(draft.make_nn_input(-1), True)
    policy = {a: math.exp(policy_logits[a]) for a in draft.legal_actions()}
    policy_sum = sum(policy.values())
    to_select = draft.to_select()
    for action, p in policy.items():
        node.children[action] = Node(p / policy_sum, to_select)
    return value
