import unittest 
import random
from autodraft.mcts import Node, run_mcts
from autodraft.draft import Draft, RoleReward


class Config:

    def __init__(self):
        self.root_exploration_fraction = 0.25
        self.root_dirichlet_alpha = 0.8
        self.num_simulations = 1
        # UCB formula
        self.pb_c_base = 19652
        self.pb_c_init = 1.25


class TestMCTS(unittest.TestCase):

    def test_add_exploration_noise(self):
        config = Config()
        # Initialise a parent node with random priors.
        parent = Node(None, None)
        priors = [random.random() for _ in range(10)]
        priors = [prior / sum(priors) for prior in priors]
        for action, prior in enumerate(priors):
            parent.children[action] = Node(prior, None)
        # Assert we have different priors that still sum to 1
        # after adding noise.
        parent.add_exploration_noise(config)
        post_priors = [node.prior for node in parent.children.values()]
        self.assertNotEqual(priors, post_priors)
        self.assertAlmostEqual(sum(post_priors), 1, delta=0.01)

    def test_first_child_updated_correctly(self):
        config = Config()
        # Only one valid hero in draft, so we know what will get 
        # selected first.
        rewards = {'role': [RoleReward(0, 0, 0, 0)], 'synergy': [], 'counter': []}
        draft = Draft(rewards=rewards)
        # After selecting first child, the network will go to expand
        # it and return a value of 2. As one action has been selected
        # this should be a value of 2 for team B. So our child should
        # have a value of -2.
        def network(x): return [1], 2
        root = run_mcts(config, draft, network)
        child = root.children[0]
        self.assertEqual(child.value, -2)
        self.assertEqual(child.value_sum, -2)
        self.assertEqual(child.visit_count, 1)

    def test_correct_values_when_team_picks_twice(self):
        config = Config()
        config.num_simulations = 3
        # I set up a draft with three valid champs and force A to pick
        # champ 0. I also have the network give a much higher prior to
        # champ 1 so I know the order of children selected in tree
        # will be 0, 1, 2.
        rewards = {'role': [], 'synergy': [], 'counter': []}
        RR = RoleReward
        rewards['role'] = [RR(0, 0, 0, 0), RR(1, 1, 0, 0), RR(2, 2, 0, 0)]
        A_roles = {'open': {0}, 'partial': []}
        draft = Draft(history=[-1]*4, rewards=rewards, A_roles=A_roles)
        # Keeping track of values assigned by NN at each position.
        values = []
        def network(x):
            policy = [0, 10, 0]
            value = random.random()
            values.append(value)
            return policy, value
        root = run_mcts(config, draft, network)
        A_child = root.children[0]
        B_child_1 = A_child.children[1]
        B_child_2 = B_child_1.children[2]
        self.assertEqual(A_child.value_sum, - values[1] - values[2] + values[3])
        self.assertEqual(B_child_1.value_sum, values[2] - values[3])
        self.assertEqual(B_child_2.value_sum, - values[3])

    def test_terminal_value_in_mcts(self):
        config = Config()
        config.num_simulations = 5
        # This provides A with champs 0..4 and B with champs 5..8
        history = [-1, -1, -1, -1, 0, 5, 6, 1, 2, 7, 8, 3, 4]
        # Copying and pasting rewards from test_draft.py that results
        # in a terminal value of -3. 
        rewards = {'role': [], 'synergy': [], 'counter': []}
        RR = RoleReward
        rewards['role'] += [RR(0, 0, 1, 9), RR(0, 1, 9, 9), RR(0, 2, 7, 9),
                            RR(0, 3, 3, 9), RR(1, 1, 1, 9), RR(1, 2, 1, 9),
                            RR(2, 1, 1, 9), RR(2, 2, 1, 9), RR(3, 0, 4, 9),
                            RR(3, 1, 9, 9), RR(3, 3, 5, 9), RR(4, 0, 9, 9),
                            RR(4, 3, 9, 9), RR(4, 4, 2, 9)
                            ]
        rewards['role'] += [RR(5, 0, 2, 1), RR(6, 1, 2, 4), RR(6, 2, 9, 1),
                            RR(7, 3, 1, 2), RR(8, 4, 2, 3), RR(9, 4, 2, 5),
                            RR(9, 1, 2, 2), RR(8, 2, 5, 2)
                            ]
        # We run mcts when there is only one pick left. After selecting
        # the child, mcts should use terminal value instead of the
        # network each time.
        draft = Draft(history=history, rewards=rewards)
        def network(x): return list(range(10)), 1
        root = run_mcts(config, draft, network)
        child = root.children[9]
        # B has final pick so it should have an average value of 3.
        self.assertEqual(child.value, 3)


if __name__ == '__main__':
    unittest.main()
