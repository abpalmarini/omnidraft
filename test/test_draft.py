import unittest 
from autodraft.draft import Draft, RoleReward, SynergyReward, CounterReward


def open_roles(draft):
    return draft.A_roles['open']

# Help to quickly create list of role rewards.
def rrs(champ, roles):
    role_rewards = []
    for role in roles:
        role_rewards.append(RoleReward(champ, role, 0, 0))
    return role_rewards


class TestLegalActions(unittest.TestCase):

    def test_legal_actions_first_ban(self):
        rrs_lookup = [
            rrs(0, [0]), rrs(1, [1]), rrs(2, [2]),
            rrs(3, [3]), rrs(4, [])
            ]
        draft = Draft(rewards=[], rrs_lookup=rrs_lookup)
        self.assertEqual(draft.legal_actions(), list(range(4)))

    def test_legal_actions_second_ban(self):
        rrs_lookup = [
            rrs(0, [0]), rrs(1, [1]), rrs(2, [2]), 
            rrs(3, [3]), rrs(4, [])
            ]
        draft = Draft(rewards=[], rrs_lookup=rrs_lookup)
        draft.apply(3)
        self.assertEqual(draft.legal_actions(), list(range(3)))

    def test_legal_actions_first_pick(self):
        rrs_lookup = [
            rrs(0, [0]), rrs(1, [1]), rrs(2, [2]), 
            rrs(3, [3]), rrs(4, [])
            ]
        draft = Draft(history=[4]*4, rewards=[], rrs_lookup=rrs_lookup)
        self.assertEqual(draft.legal_actions(), list(range(4)))

    def test_legal_actions_second_pick(self):
        rrs_lookup = [
            rrs(0, [0]), rrs(1, [1]), rrs(2, [2]), 
            rrs(3, [3]), rrs(4, [])
            ]
        draft = Draft(history=[4]*4, rewards=[], rrs_lookup=rrs_lookup)
        draft.apply(3)
        self.assertEqual(draft.legal_actions(), list(range(3)))

    def test_legal_actions_role_removed(self):
        rrs_lookup = [
            rrs(0, [0]), rrs(1, [1]), rrs(2, [2]),
            rrs(3, [3]), rrs(4, [4]), rrs(5, [0]),
            rrs(6, [])
            ]
        draft = Draft(history=[6]*4, rewards=[], rrs_lookup=rrs_lookup)
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


class TestOpenRoles(unittest.TestCase):

    def test_single(self):
        rrs_lookup = [rrs(0, [4])]
        draft = Draft(history=[-1]*4, rewards=[], rrs_lookup=rrs_lookup)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(0)
        self.assertEqual(open_roles(draft), {0, 1, 2, 3})

    def test_single_turns_double_to_single(self):
        rrs_lookup = [rrs(0, [0, 1]), rrs(1, [1]), rrs(2, [])]
        draft = Draft(history=[-1]*4, rewards=[], rrs_lookup=rrs_lookup)
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
        draft = Draft(history=[-1]*4, rewards=[], rrs_lookup=rrs_lookup)
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
        draft = Draft(history=[-1]*4, rewards=[], rrs_lookup=rrs_lookup)
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
        draft = Draft(history=[-1]*4, rewards=[], rrs_lookup=rrs_lookup)
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
        draft = Draft(history=[-1]*4, rewards=[], rrs_lookup=rrs_lookup)
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
        draft = Draft(history=[-1]*4, rewards=[], rrs_lookup=rrs_lookup)
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
        self.rewards = {'role': [], 'synergy': [], 'counter': []}
        # This provides A with champs 0..4 and B with champs 5..9
        self.history = [-1, -1, -1, -1, 0, 5, 6, 1, 2, 7, 8, 3, 4, 9]
        self.team_A = {0, 1, 2, 3, 4}
        self.team_B = {5, 6, 7, 8, 9}

    def test_synergy_value_one_team(self):
        SR = SynergyReward
        self.rewards['synergy'] = [SR({0, 1}, 2, 3), SR({0, 5}, 5, 5),
                                   SR({1, 2, 3}, 1, 5)
                                   ]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._synergy_value(self.team_A, self.team_B), 3)

    def test_synergy_value_both_teams(self):
        SR = SynergyReward
        self.rewards['synergy'] = [SR({0, 1}, 2, 3), SR({0, 5}, 5, 5),
                                   SR({5, 6, 7}, 5, 3)
                                   ]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._synergy_value(self.team_A, self.team_B), -1)

    def test_counter_value_same_team(self):
        CR = CounterReward
        self.rewards['counter'] = [CR({0}, {2}, 5, 5)]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._counter_value(self.team_A, self.team_B), 0)

    def test_counter_value(self):
        CR = CounterReward
        self.rewards['counter'] = [CR({0}, {2}, 5, 5), CR({0}, {5}, 2, 3), 
                                   CR({8, 9}, {2, 3, 4}, 1, 4)
                                   ]
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._counter_value(self.team_A, self.team_B), -2)

    def test_role_value_standard(self):
        RR = RoleReward
        self.rewards['role'] = [RR(0, 0, 1, 9), RR(1, 1, 1, 9), RR(2, 2, 1, 9),
                                RR(3, 3, 1, 9), RR(4, 4, 3, 9)
                                ] 
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._team_role_value(self.team_A, True), 7)

    def test_role_value_high_value_not_possible(self):
        RR = RoleReward
        self.rewards['role'] = [RR(0, 0, 1, 9), RR(1, 1, 1, 9), RR(2, 2, 1, 9),
                                RR(3, 3, 1, 9), RR(4, 4, 3, 9), RR(0, 1, 5, 9)
                                ] 
        draft = Draft(self.history, self.rewards)
        self.assertEqual(draft._team_role_value(self.team_A, True), 7)

    def test_role_value_two_options(self):
        RR = RoleReward
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
        RR = RoleReward
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
        RR = RoleReward
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
        RR = RoleReward
        SR = SynergyReward
        CR = CounterReward
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
        self.rewards['synergy'] = [SR({0, 1}, 2, 3), SR({0, 5}, 5, 5),
                                   SR({5, 6, 7}, 5, 3)
                                   ]
        # :test_counter_value results in value of -2
        self.rewards['counter'] = [CR({0}, {2}, 5, 5), CR({0}, {5}, 2, 3), 
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
        draft = Draft(history=[-1]*4, rrs_lookup=rrs_lookup)
        draft_clone = draft.clone()
        draft_clone.apply(0)
        self.assertEqual(draft.history, [-1, -1, -1, -1])
        self.assertEqual(open_roles(draft), set(range(5)))
        self.assertEqual(draft_clone.history, [-1, -1, -1, -1, 0])
        self.assertEqual(open_roles(draft_clone), set(range(4)))
        

if __name__ == '__main__':
    unittest.main()
