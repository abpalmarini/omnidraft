"""
These are NOT tests for work done in the current project, but saying I
am keeping 'draft_az.py' for testing purposes I might as well keep its
own tests as well.
"""

import unittest 

from .draft_az import Draft
from .draft_az import RoleReward as RR
from .draft_az import ComboReward as CR


def open_roles(draft):
    return draft.roles['A']['open']


# Help to quickly create list of role rewards.
def rrs(champ, roles):
    role_rewards = []
    for role in roles:
        role_rewards.append(RR(champ, role, 0, 0))
    return role_rewards


class TestLegalActions(unittest.TestCase):

    def test_legal_actions_first_ban(self):
        rrs_lookup = [
            rrs(0, [0]), rrs(1, [1]), rrs(2, [2]),
            rrs(3, [3]), rrs(4, [])
            ]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(rewards=rewards)
        self.assertEqual(draft.legal_actions(), list(range(4)))

    def test_legal_actions_second_ban(self):
        rrs_lookup = [
            rrs(0, [0]), rrs(1, [1]), rrs(2, [2]), 
            rrs(3, [3]), rrs(4, [])
            ]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(rewards=rewards)
        draft.apply(3)
        self.assertEqual(draft.legal_actions(), list(range(3)))

    def test_legal_actions_first_pick(self):
        rrs_lookup = [
            rrs(0, [0]), rrs(1, [1]), rrs(2, [2]), 
            rrs(3, [3]), rrs(4, [])
            ]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[4]*4, rewards=rewards)
        self.assertEqual(draft.legal_actions(), list(range(4)))

    def test_legal_actions_second_pick(self):
        rrs_lookup = [
            rrs(0, [0]), rrs(1, [1]), rrs(2, [2]), 
            rrs(3, [3]), rrs(4, [])
            ]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[4]*4, rewards=rewards)
        draft.apply(3)
        self.assertEqual(draft.legal_actions(), list(range(3)))

    def test_legal_actions_role_removed(self):
        rrs_lookup = [
            rrs(0, [0]), rrs(1, [1]), rrs(2, [2]),
            rrs(3, [3]), rrs(4, [4]), rrs(5, [0]),
            rrs(6, [])
            ]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[6]*4, rewards=rewards)
        draft.apply(0)
        draft.apply(1)
        draft.apply(2)
        # Team A should not be able to play champ 5 even though it has
        # not been picked.
        self.assertEqual(draft.legal_actions(), [3, 4])
        draft.apply(3)
        draft.apply(4)
        # Champ 5 should now become available to team B though.
        self.assertEqual(draft.legal_actions(), [5])

    def test_rewards_updated_for_adding_new_legal_champ(self):
        # Starting with one reward to ensure new ones are being added
        # and not overwriting.
        rewards = {'role': [RR(0, 0, 0, 0)], 'combo': []}
        draft = Draft(history=[-1, -1, -1, 0], rewards=rewards)
        # Should produce 5 random legal actions as A has 5 open roles.
        legal_actions = draft.legal_actions()
        self.assertEqual(len(legal_actions), 5)
        # Need to check they have been added to the role rewards,
        # rrs_lookup and nn_input.
        self.assertEqual(len(draft.rewards['role']), 1 + 5)
        nn_role_rewards = draft.rewards['nn_input']['role'][2]
        self.assertEqual(len(nn_role_rewards), 1 + 5)
        for i, champ in enumerate(legal_actions):
            reward = draft.rewards['role'][1 + i]
            self.assertEqual(reward.champ, champ)
            self.assertEqual(reward.role, i)
            self.assertEqual(reward.A_value, 0)
            self.assertEqual(reward.B_value, 0)
            self.assertEqual(draft.rewards['rrs_lookup'][champ], [reward])
            # Ensure the nn reward is correctly added.
            self.assertEqual(nn_role_rewards[1 + i][2 + i], 1)
            self.assertEqual(nn_role_rewards[1 + i][2 + 5 + champ], 1)

        # Small check that it also works for team B. After apply all
        # actions, then A will have 2 open roles and B will have 3.
        # So the number of newly produced legal actions should be 3
        # and should be for roles 0, 3 and 4.
        for action in legal_actions:
            draft.apply(action)
        legal_actions = draft.legal_actions()
        self.assertEqual(len(legal_actions), 3)
        new_champs_roles = set()
        for champ in legal_actions:
            reward = draft.rewards['rrs_lookup'][champ][0]
            new_champs_roles.add(reward.role)
        self.assertEqual(new_champs_roles, {0, 3, 4})


class TestOpenRoles(unittest.TestCase):

    def test_single(self):
        rrs_lookup = [rrs(0, [4])]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[-1]*4, rewards=rewards)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(0)
        self.assertEqual(open_roles(draft), {0, 1, 2, 3})

    def test_single_turns_double_to_single(self):
        rrs_lookup = [rrs(0, [0, 1]), rrs(1, [1]), rrs(2, [])]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[-1]*4, rewards=rewards)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        # Skip over team B picks.
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), {2, 3 ,4})

    def test_four_plus_single_turns_double_to_single(self):
        rrs_lookup = [
            rrs(0, [0, 1, 2, 3]), rrs(1, [2, 3]),
            rrs(2, [3]), rrs(3, [])
            ]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[-1]*4, rewards=rewards)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(2)
        self.assertEqual(open_roles(draft), {0, 1, 4})

    def test_double_resolve(self):
        rrs_lookup = [rrs(0, [0, 1]), rrs(1, [0, 1]), rrs(2, [])]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[-1]*4, rewards=rewards)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), {2, 3, 4})

    def test_extra_double_plus_double_resolve(self):
        rrs_lookup = [
            rrs(0, [0, 1]), rrs(1, [2, 3]),
            rrs(2, [2, 3]), rrs(3, [])
            ]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[-1]*4, rewards=rewards)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(2)
        self.assertEqual(open_roles(draft), {0, 1, 4})

    def test_three_way_resolve(self):
        rrs_lookup = [
            rrs(0, [0, 1]), rrs(1, [1, 2]),
            rrs(2, [0, 2]), rrs(3, [])
            ]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[-1]*4, rewards=rewards)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(2)
        # At this point any hero picked in one of these roles would cause crash.
        self.assertEqual(open_roles(draft), {3, 4})

    def test_four_role_plus_three_way_resolve(self):
        rrs_lookup = [
            rrs(0, [0, 1, 2, 3]), rrs(1, [2, 3]),
            rrs(2, [3, 4]), rrs(3, [2, 4]), rrs(4, [])
            ]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[-1]*4, rewards=rewards)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(2)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(3)
        self.assertEqual(open_roles(draft), {0, 1})


class TestTerminalValue(unittest.TestCase):

    def setUp(self):
        self.rewards = {'role': [], 'combo': []}
        # This provides A with champs 0..4 and B with champs 5..9
        self.history = [-1, -1, -1, -1, 0, 5, 6, 1, 2, 7, 8, 3, 4, 9]
        self.team_A = {0, 1, 2, 3, 4}
        self.team_B = {5, 6, 7, 8, 9}

    def test_synergy_value_one_team(self):
        self.rewards['combo'] = [CR({0, 1}, set(), 2, 3), CR({0, 5}, set(), 5, 5),
                                 CR({1, 2, 3}, set(), 1, 5)
                                 ]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._combo_value(self.team_A, self.team_B), 3)

    def test_synergy_value_both_teams(self):
        self.rewards['combo'] = [CR({0, 1}, set(), 2, 3), CR({0, 5}, set(), 5, 5),
                                 CR({5, 6, 7}, set(), 5, 3)
                                 ]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._combo_value(self.team_A, self.team_B), -1)

    def test_counter_value_same_team(self):
        self.rewards['combo'] = [CR({0}, {2}, 5, 5)]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._combo_value(self.team_A, self.team_B), 0)

    def test_counter_value(self):
        self.rewards['combo'] = [CR({0}, {2}, 5, 5), CR({0}, {5}, 2, 3),
                                 CR({8, 9}, {2, 3, 4}, 1, 4)
                                 ]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._combo_value(self.team_A, self.team_B), -2)

    def test_role_value_standard(self):
        self.rewards['role'] = [RR(0, 0, 1, 9), RR(1, 1, 1, 9), RR(2, 2, 1, 9),
                                RR(3, 3, 1, 9), RR(4, 4, 3, 9)
                                ] 
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._team_role_value(self.team_A, True), 7)

    def test_role_value_high_value_not_possible(self):
        self.rewards['role'] = [RR(0, 0, 1, 9), RR(1, 1, 1, 9), RR(2, 2, 1, 9),
                                RR(3, 3, 1, 9), RR(4, 4, 3, 9), RR(0, 1, 5, 9)
                                ] 
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._team_role_value(self.team_A, True), 7)

    def test_role_value_two_options(self):
        # Champ 0 can play role 0 with reward 1 or role 1 with reward 3.
        # Champ 1 can play both role 0 and 1 with reward 1 so the role
        # value should assign the highest.
        self.rewards['role'] = [RR(0, 0, 1, 9), RR(1, 1, 1, 9), RR(2, 2, 1, 9),
                                RR(3, 3, 1, 9), RR(4, 4, 3, 9), RR(0, 1, 3, 9),
                                RR(1, 0, 1, 9)
                                ]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._team_role_value(self.team_A, True), 9)

    def test_role_value_team_B(self):
        # 6 can play 1 and 2, 9 can play 1 and 4, 8 can play 4 and 2.
        # Highest assignment when 6 plays 1, 9 plays 4 and 8 plays 2
        # even though 8 would be better off alone in 4.
        self.rewards['role'] = [RR(5, 0, 2, 1), RR(6, 1, 2, 4), RR(6, 2, 9, 1),
                                RR(7, 3, 1, 2), RR(8, 4, 2, 3), RR(9, 4, 2, 5),
                                RR(9, 1, 2, 2), RR(8, 2, 5, 2)
                                ]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._team_role_value(self.team_B, False), 14)

    def test_role_value_multi_options(self):
        # 0 can play 0, 1, 2, 3
        # 1 can play 1, 2
        # 2 can play 1, 2
        # 3 can play 0, 1, 3
        # 4 can play 0, 3, 4
        # As 0 can't play 1 or 2 we give it high values there. As 3
        # can't play 1 we give it a high value for that one. As 4 
        # must play role 4 we give it high values for the rest. We
        # let 3 have higher values than 0 for both role 0 and 3, but
        # let the difference be bigger when it goes for it's lower 
        # option and 0 goes for it's highest.
        self.rewards['role'] = [RR(0, 0, 1, 9), RR(0, 1, 9, 9), RR(0, 2, 7, 9),
                                RR(0, 3, 3, 9), RR(1, 1, 1, 9), RR(1, 2, 1, 9),
                                RR(2, 1, 1, 9), RR(2, 2, 1, 9), RR(3, 0, 4, 9),
                                RR(3, 1, 9, 9), RR(3, 3, 5, 9), RR(4, 0, 9, 9),
                                RR(4, 3, 9, 9), RR(4, 4, 2, 9)
                                ]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._team_role_value(self.team_A, True), 11)

    def test_total_termainal_value(self):
        # Copying and pasting specific instances from the tests above.
        # :test_role_value_multi_options results in value of 11
        self.rewards['role'] += [RR(0, 0, 1, 9), RR(0, 1, 9, 9), RR(0, 2, 7, 9),
                                 RR(0, 3, 3, 9), RR(1, 1, 1, 9), RR(1, 2, 1, 9),
                                 RR(2, 1, 1, 9), RR(2, 2, 1, 9), RR(3, 0, 4, 9),
                                 RR(3, 1, 9, 9), RR(3, 3, 5, 9), RR(4, 0, 9, 9),
                                 RR(4, 3, 9, 9), RR(4, 4, 2, 9)
                                 ]
        # :test_role_value_team_B results in value of 14 for B, so -14
        self.rewards['role'] += [RR(5, 0, 2, 1), RR(6, 1, 2, 4), RR(6, 2, 9, 1),
                                 RR(7, 3, 1, 2), RR(8, 4, 2, 3), RR(9, 4, 2, 5),
                                 RR(9, 1, 2, 2), RR(8, 2, 5, 2)
                                 ]
        # :test_synergy_value_both_teams results in value of -1
        self.rewards['combo'] += [CR({0, 1}, set(), 2, 3), CR({0, 5}, set(), 5, 5),
                                  CR({5, 6, 7}, set(), 5, 3)
                                  ]
        # :test_counter_value results in value of -2
        self.rewards['combo'] += [CR({0}, {2}, 5, 5), CR({0}, {5}, 2, 3),
                                  CR({8, 9}, {2, 3, 4}, 1, 4)
                                  ]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft.terminal_value(), 11 - 14 - 1 - 2)


class TestMiscDraftMethods(unittest.TestCase):

    def test_terminal(self):
        draft = Draft(list(range(13)))
        self.assertFalse(draft.terminal())
        draft.apply(13)
        self.assertTrue(draft.terminal())

    def test_clone(self):
        rrs_lookup = [rrs(0, [4])]
        rewards = {'rrs_lookup': rrs_lookup, 'nn_input': None}
        draft = Draft(history=[-1]*4, rewards=rewards)
        draft_clone = draft.clone()
        draft_clone.apply(0)
        self.assertEqual(draft.history, [-1, -1, -1, -1])
        self.assertEqual(open_roles(draft), set(range(5)))
        self.assertEqual(draft_clone.history, [-1, -1, -1, -1, 0])
        self.assertEqual(open_roles(draft_clone), set(range(4)))


class TestNNInput(unittest.TestCase):

    def check_active_features(self, active_features, vector):
        for feature, value in enumerate(vector):
            if feature in active_features:
                self.assertEqual(value, 1, msg=f'feature {feature}')
            else:
                self.assertEqual(value, 0, msg=f'feature {feature}')

    def test_draft_state_first_ban(self):
        draft = Draft()
        draft_state = draft._make_nn_draft_state_input(0)
        active_features = set() # The following indices should be 1.
        active_features.add(0)
        active_features.add(3)
        # All roles should be open for both teams.
        open_roles = set(range(3 + len(draft.format), 3 + len(draft.format) + 10))
        active_features = active_features.union(open_roles)
        self.check_active_features(active_features, draft_state)
        correct_len = 3 + len(draft.format) + 10 + (4 * draft.num_champs)
        self.assertEqual(len(draft_state), correct_len)

    def test_draft_state_B_first_pick(self):
        rewards = {'role': [], 'combo': []}
        rewards['role'] = [RR(0, 0, 0, 0), RR(1, 0, 0, 0), RR(2, 0, 0, 0),
                           RR(3, 0, 0, 0), RR(4, 0, 0, 0)
                           ]
        draft = Draft(rewards=rewards)
        for i in range(5):
            draft.apply(i)
        # It is now B to pick and A should not have role 0 open.
        draft_state = draft._make_nn_draft_state_input(len(draft.history))
        active_features = set()
        offset = 0
                               # Skipping A to pick.
        active_features.add(1) # Its a pick.
        active_features.add(2) # B also has next pick.
        offset += 3
        active_features.add(offset + 5)
        offset += len(draft.format)
        # B still has all roles open
        active_features = active_features.union(set(range(offset, offset + 5)))
        offset += 5
        # A no longer has 0
        active_features = active_features.union(set(range(offset + 1, offset + 5)))
        offset += 5
        # B has no picks.
        offset += draft.num_champs
        # B bans.
        active_features.add(offset + 1)
        active_features.add(offset + 3)
        offset += draft.num_champs
        # A picks.
        active_features.add(offset + 4)
        offset += draft.num_champs
        # A bans.
        active_features.add(offset + 0)
        active_features.add(offset + 2)
        self.check_active_features(active_features, draft_state)

    def test_draft_state_A_pick(self):
        rewards = {'role': [], 'combo': []}
        rewards['role'] = [RR(0, 0, 0, 0), RR(1, 0, 0, 0), RR(2, 0, 0, 0),
                           RR(3, 0, 0, 0), RR(4, 0, 0, 0), RR(5, 0, 0, 0),
                           RR(6, 1, 0, 0), RR(7, 1, 0, 0)
                           ]
        draft = Draft(rewards=rewards)
        for i in range(8):
            draft.apply(i)
        # It is now A to pick. Both no longer have roles 0 and 1 open.
        # A doesn't have next pick.
        draft_state = draft._make_nn_draft_state_input(len(draft.history))
        active_features = set()
        offset = 0
        active_features.add(0) # A to select.
        active_features.add(1) # Its a pick.
                               # Skipping next turn.
        offset += 3
        active_features.add(offset + 8)
        offset += len(draft.format)
        A_open = set(range(offset + 2, offset + 5))
        offset += 5
        B_open = set(range(offset + 2, offset + 5))
        offset += 5
        active_features = active_features.union(A_open, B_open)
        # A picks.
        active_features.add(offset + 4)
        active_features.add(offset + 7)
        offset += draft.num_champs
        # A bans.
        active_features.add(offset + 0)
        active_features.add(offset + 2)
        offset += draft.num_champs
        # B picks.
        active_features.add(offset + 5)
        active_features.add(offset + 6)
        offset += draft.num_champs
        # B bans.
        active_features.add(offset + 1)
        active_features.add(offset + 3)
        self.check_active_features(active_features, draft_state)

    def test_draft_state_in_make_nn_input(self):
        # Copying and pasting from :test_draft_state_first_ban as I
        # just need to test its returned correctly in outer method.
        draft = Draft()
        draft_state, _, _ = draft.make_nn_input()
        active_features = set()
        active_features.add(0)
        active_features.add(3)
        open_roles = set(range(3 + len(draft.format), 3 + len(draft.format) + 10))
        active_features = active_features.union(open_roles)
        self.check_active_features(active_features, draft_state)

    def test_role_reward(self):
        rewards = {'role': [], 'combo': []}
        rewards['role'] = [RR(27, 4, 0.2, 0.1)]
        draft = Draft(rewards=rewards)
        _, nn_role_rewards, _ = draft.make_nn_input()
        reward = nn_role_rewards[0]
        # It is A to ban so first value should be A's.
        self.assertAlmostEqual(reward[0], 0.2)
        self.assertAlmostEqual(reward[1], 0.1)
        active_features = set()
        offset = 2
        active_features.add(offset + 4)
        offset += 5
        active_features.add(offset + 27)
        # Masking reward values to check other features now we have
        # asserted they are correct.
        reward[0] = 0
        reward[1] = 0
        self.check_active_features(active_features, reward)
        # Now checking values when it is B to select.
        draft.apply(27)
        _, nn_role_rewards, _ = draft.make_nn_input()
        reward = nn_role_rewards[0]
        self.assertAlmostEqual(reward[0], 0.1)
        self.assertAlmostEqual(reward[1], 0.2)
        reward[0] = 0
        reward[1] = 0
        self.check_active_features(active_features, reward)

    def test_combo_reward(self):
        rewards = {'role': [RR(0, 0, 0, 0)], 'combo': []}
        rewards['combo'] = [CR({0, 9}, {17, 22, 41}, 0.5, 0.9)]
        draft = Draft(rewards=rewards)
        _, _, nn_combo_rewards = draft.make_nn_input()
        reward = nn_combo_rewards[0]
        self.assertAlmostEqual(reward[0], 0.5)
        self.assertAlmostEqual(reward[1], 0.9)
        active_features = set()
        offset = 2
        active_features.add(offset + 0)
        active_features.add(offset + 9)
        offset += draft.num_champs
        active_features.add(offset + 17)
        active_features.add(offset + 22)
        active_features.add(offset + 41)
        reward[0] = 0
        reward[1] = 0
        self.check_active_features(active_features, reward)
        # Checking when B to select.
        draft.apply(0)
        _, _, nn_combo_rewards = draft.make_nn_input()
        reward = nn_combo_rewards[0]
        self.assertAlmostEqual(reward[0], 0.9)
        self.assertAlmostEqual(reward[1], 0.5)
        reward[0] = 0
        reward[1] = 0
        self.check_active_features(active_features, reward)

    def test_stacked_rewards(self):
        rewards = {'role': [RR(0, 0, 0.5, 0.8), RR(1, 1, 0.3, 0.2)],
                   'combo': [CR({2, 8}, set(), 0.9, 0.1),  CR({0}, {1}, 0.2, 0.8)]
                   }
        # Setting history up to A's first pick.
        history = [-1 for _ in range(4)]
        open_roles_history = [(tuple(range(5)), tuple(range(5))) for _ in range(5)]
        draft = Draft(history=history, rewards=rewards)
        draft.roles['open_history'] = open_roles_history
        _, nn_role_rewards, nn_combo_rewards = draft.make_nn_input()
        # Role 0
        self.assertAlmostEqual(nn_role_rewards[0, 0], 0.5)
        self.assertAlmostEqual(nn_role_rewards[0, 1], 0.8)
        # Role 1
        self.assertAlmostEqual(nn_role_rewards[1, 0], 0.3)
        self.assertAlmostEqual(nn_role_rewards[1, 1], 0.2)
        # Combo 0
        self.assertAlmostEqual(nn_combo_rewards[0, 0], 0.9)
        self.assertAlmostEqual(nn_combo_rewards[0, 1], 0.1)
        # Combo 1
        self.assertAlmostEqual(nn_combo_rewards[1, 0], 0.2)
        self.assertAlmostEqual(nn_combo_rewards[1, 1], 0.8)
        # Check other features.
        nn_role_rewards[:, 0] = 0
        nn_role_rewards[:, 1] = 0
        nn_combo_rewards[:, 0] = 0
        nn_combo_rewards[:, 1] = 0
        role_0_active_features = {2, 7} # Role 0, champ 0
        role_1_active_features = {3, 8} # Role 1, champ 1
        offset = 2
        combo_0_active_features = {offset + 2, offset + 8}
        combo_1_active_features = {offset + 0, offset + draft.num_champs + 1}
        self.check_active_features(role_0_active_features, nn_role_rewards[0])
        self.check_active_features(role_1_active_features, nn_role_rewards[1])
        self.check_active_features(combo_0_active_features, nn_combo_rewards[0])
        self.check_active_features(combo_1_active_features, nn_combo_rewards[1])


if __name__ == '__main__':
    unittest.main()
