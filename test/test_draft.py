import unittest 
from autodraft.draft import Draft


def open_roles(draft):
    return draft.A_roles['open']


class TestLegalActions(unittest.TestCase):

    def test_legal_actions_first_ban(self):
        champs_roles = [{0}, {1}, {2}, {3}, set()]
        draft = Draft(rewards=[], champs_roles=champs_roles)
        self.assertEqual(draft.legal_actions(), list(range(4)))

    def test_legal_actions_second_ban(self):
        champs_roles = [{0}, {1}, {2}, {3}, set()]
        draft = Draft(rewards=[], champs_roles=champs_roles)
        draft.apply(3)
        self.assertEqual(draft.legal_actions(), list(range(3)))

    def test_legal_actions_first_pick(self):
        champs_roles = [{0}, {1}, {2}, {3}, set()]
        draft = Draft(history=[4]*4, rewards=[], champs_roles=champs_roles)
        self.assertEqual(draft.legal_actions(), list(range(4)))

    def test_legal_actions_second_pick(self):
        champs_roles = [{0}, {1}, {2}, {3}, set()]
        draft = Draft(history=[4]*4, rewards=[], champs_roles=champs_roles)
        draft.apply(3)
        self.assertEqual(draft.legal_actions(), list(range(3)))

    def test_legal_actions_role_removed(self):
        champs_roles = [{0}, {1}, {2}, {3}, {4}, {0}, set()]
        draft = Draft(history=[6]*4, rewards=[], champs_roles=champs_roles)
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
        champs_roles = [{4}]
        draft = Draft(history=[0]*4, rewards=[], champs_roles=champs_roles)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(0)
        self.assertEqual(open_roles(draft), {0, 1, 2, 3})

    def test_single_turns_double_to_single(self):
        champs_roles = [{0, 1}, {1}, set()]
        draft = Draft(history=[0]*4, rewards=[], champs_roles=champs_roles)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        # Skip over team B picks.
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), {2, 3 ,4})

    def test_four_plus_single_turns_double_to_single(self):
        champs_roles = [{0, 1, 2, 3}, {2, 3}, {3}, set()]
        draft = Draft(history=[0]*4, rewards=[], champs_roles=champs_roles)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(2)
        self.assertEqual(open_roles(draft), {0, 1, 4})

    def test_double_resolve(self):
        champs_roles = [{0, 1}, {0, 1}, set()]
        draft = Draft(history=[0]*4, rewards=[], champs_roles=champs_roles)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), {2, 3, 4})

    def test_extra_double_plus_double_resolve(self):
        champs_roles = [{0, 1}, {2, 3}, {2, 3}, set()]
        draft = Draft(history=[0]*4, rewards=[], champs_roles=champs_roles)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(2)
        self.assertEqual(open_roles(draft), {0, 1, 4})

    def test_three_way_resolve(self):
        champs_roles = [{0, 1}, {1, 2}, {0, 2}, set()]
        draft = Draft(history=[0]*4, rewards=[], champs_roles=champs_roles)
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
        champs_roles = [{0, 1, 2, 3}, {2, 3}, {3, 4}, {2, 4}, set()]
        draft = Draft(history=[0]*4, rewards=[], champs_roles=champs_roles)
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


if __name__ == '__main__':
    unittest.main()
