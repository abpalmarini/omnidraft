import unittest 
from autodraft.selfplay import Draft


def open_roles(draft):
    return draft.A_roles['open']


class TestOpenRoles(unittest.TestCase):

    def test_single(self):
        champs_roles = [{4}]
        draft = Draft(history=[0, 0, 0, 0], rewards=[], champs_roles=champs_roles)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(0)
        self.assertEqual(open_roles(draft), {0, 1, 2, 3})

    def test_single_turns_double_to_single(self):
        champs_roles = [{0, 1}, {1}, set()]
        draft = Draft(history=[0, 0, 0, 0], rewards=[], champs_roles=champs_roles)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        # Skip over team B picks.
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), {2, 3 ,4})

    def test_four_plus_single_turns_double_to_single(self):
        champs_roles = [{0, 1, 2, 3}, {2, 3}, {3}, set()]
        draft = Draft(history=[0, 0, 0, 0], rewards=[], champs_roles=champs_roles)
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
        draft = Draft(history=[0, 0, 0, 0], rewards=[], champs_roles=champs_roles)
        draft.apply(0)
        self.assertEqual(open_roles(draft), set(range(5)))
        draft.apply(-1)
        draft.apply(-1)
        draft.apply(1)
        self.assertEqual(open_roles(draft), {2, 3, 4})

    def test_extra_double_plus_double_resolve(self):
        champs_roles = [{0, 1}, {2, 3}, {2, 3}, set()]
        draft = Draft(history=[0, 0, 0, 0], rewards=[], champs_roles=champs_roles)
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
        draft = Draft(history=[0, 0, 0, 0], rewards=[], champs_roles=champs_roles)
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
        draft = Draft(history=[0, 0, 0, 0], rewards=[], champs_roles=champs_roles)
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
