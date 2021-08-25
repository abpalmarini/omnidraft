import unittest 
from collections import namedtuple

from omnidraft.draft_ai import *


class TestAIPrep(unittest.TestCase):

    def test_correctly_ordered_heroes(self):
        # check with just role rewards
        role_rs = [
            RoleR('Krul', 0, 2, 2), RoleR('Krul', 1, 0, 2),
            RoleR('Taka', 0, 3, 0), RoleR('Rona', 3, 0, 1),
        ]
        draft_ai = DraftAI([], role_rs, [], [])
        heroes, hero_nums = draft_ai.ordered_heroes, draft_ai.hero_nums
        self.assertEqual(hero_nums[('Krul', 0)], 0) 
        self.assertEqual(hero_nums[('Taka', 0)], 1) 
        self.assertEqual(hero_nums[('Krul', 1)], 2) 
        self.assertEqual(hero_nums[('Rona', 3)], 3) 

        # add synergy only applicable to krul in role 1
        synergy_rs = [SynergyR([('Krul', [1]), ('Taka', [0])], 5, 0)]
        draft_ai = DraftAI([], role_rs, synergy_rs, [])
        heroes, hero_nums = draft_ai.ordered_heroes, draft_ai.hero_nums
        self.assertEqual(heroes[0].name, 'Taka')
        self.assertEqual(heroes[1].name, 'Krul')
        self.assertEqual(heroes[1].role, 1)
        self.assertEqual(heroes[2].potential, 4)  # value not added to other krul

        # finally check counters work
        counter_rs = [CounterR([('Rona', [3])], ['Krul'], 10, 10)]
        draft_ai = DraftAI([], role_rs, synergy_rs, counter_rs)
        heroes, hero_nums = draft_ai.ordered_heroes, draft_ai.hero_nums
        self.assertEqual(hero_nums[('Rona', 3)], 0)
        self.assertEqual(heroes[0].potential, 21)  # doesn't get duplicate for both kruls

    def test_correct_hero_roles(self):
        role_rs = [
            RoleR('Krul', 0, 2, 2), RoleR('Krul', 1, 0, 2),
            RoleR('Taka', 4, 3, 0), RoleR('Rona', 3, 0, 1),
            RoleR('Taka', 0, 1, 2),
        ]
        draft_ai = DraftAI([], role_rs, [], [])
        self.assertEqual(draft_ai.hero_roles['Krul'], [0, 1])
        self.assertEqual(draft_ai.hero_roles['Rona'], [3])
        self.assertEqual(draft_ai.hero_roles['Taka'], [0, 4])

    def test_translate_synergy_rs(self):
        role_rs = [
            RoleR('Taka', 0, 0, 7),
            RoleR('Krul', 1, 0, 6),
            RoleR('Krul', 2, 0, 5),
            RoleR('Rona', 3, 0, 4),
            RoleR('Rona', 4, 0, 3),
            RoleR('Gwen', 1, 0, 1),
            RoleR('Gwen', 2, 0, 0),
        ]
        all_correct = []

        # 4 new synergies should be created
        synergy_1 = SynergyR([('Taka', [0]), ('Krul', [1, 2]), ('Rona', [3, 4])], 2, 1)
        draft_ai = DraftAI([], role_rs, [synergy_1], [])
        new_synergy_rs = draft_ai.translate_synergy_rs([synergy_1])
        self.assertEqual(len(new_synergy_rs), 4)
        correct_synergy_rs = [
            ([0, 1, 3], 2, 1),
            ([0, 1, 4], 2, 1),
            ([0, 2, 3], 2, 1),
            ([0, 2, 4], 2, 1),
        ]
        self.assertEqual(new_synergy_rs, correct_synergy_rs)
        all_correct += correct_synergy_rs
        
        # only 2 synergies between compatible roles should be created
        synergy_2 = SynergyR([('Taka', [0]), ('Krul', [1, 2]), ('Gwen', [1, 2])], 0, 1)
        draft_ai = DraftAI([], role_rs, [synergy_2], [])
        new_synergy_rs = draft_ai.translate_synergy_rs([synergy_2])
        self.assertEqual(len(new_synergy_rs), 2)
        correct_synergy_rs = [
            ([0, 1, 6], 0, 1),
            ([0, 2, 5], 0, 1),
        ]
        self.assertEqual(new_synergy_rs, correct_synergy_rs)
        all_correct += correct_synergy_rs

        # test both combined
        draft_ai = DraftAI([], role_rs, [synergy_1, synergy_2], [])
        new_synergy_rs = draft_ai.translate_synergy_rs([synergy_1, synergy_2])
        self.assertEqual(new_synergy_rs, all_correct)

    def test_translate_counter_rs(self):
        role_rs = [
            RoleR('Taka', 0, 2, 9),
            RoleR('Krul', 1, 1, 9),
            RoleR('Krul', 2, 0, 9),
            RoleR('Rona', 3, 0, 8),
            RoleR('Rona', 4, 0, 7),
            RoleR('Gwen', 1, 0, 4),
            RoleR('Gwen', 2, 0, 3),
            RoleR('Lyra', 3, 0, 2),
            RoleR('Lyra', 4, 0, 1),
        ]
        all_correct = []

        # doesn't matter about clashes in roles across teams
        counter_1 = CounterR([('Krul', [2])], ['Gwen'], 1, 0)
        draft_ai = DraftAI([], role_rs, [], [counter_1])
        new_counter_rs = draft_ai.translate_counter_rs([counter_1])
        correct_counter_rs = [
            ([2], [5], 1, 0),
            ([2], [6], 1, 0),
        ]
        self.assertEqual(new_counter_rs, correct_counter_rs)
        all_correct += new_counter_rs

        counter_2 = CounterR(
            [('Taka', [0]), ('Krul', [1, 2]), ('Gwen', [1, 2])],
            ['Rona'],
            0,
            1,
        )
        draft_ai = DraftAI([], role_rs, [], [counter_2])
        new_counter_rs = draft_ai.translate_counter_rs([counter_2])
        correct_counter_rs = [
            ([0, 1, 6], [3], 0, 1),
            ([0, 1, 6], [4], 0, 1),
            ([0, 2, 5], [3], 0, 1),
            ([0, 2, 5], [4], 0, 1),
        ]
        self.assertEqual(new_counter_rs, correct_counter_rs)
        all_correct += new_counter_rs

        # clashes in both heroes and adversaries
        counter_3 = CounterR(
            [('Taka', [0]), ('Krul', [1, 2]), ('Gwen', [1, 2])],
            ['Rona', 'Lyra'],
            1,
            0,
        )
        draft_ai = DraftAI([], role_rs, [], [counter_3])
        new_counter_rs = draft_ai.translate_counter_rs([counter_3])
        correct_counter_rs = [
            ([0, 1, 6], [3, 8], 1, 0),
            ([0, 1, 6], [4, 7], 1, 0),
            ([0, 2, 5], [3, 8], 1, 0),
            ([0, 2, 5], [4, 7], 1, 0),
        ]
        self.assertEqual(new_counter_rs, correct_counter_rs)
        all_correct += new_counter_rs

        # test all combined
        all_counters = [counter_1, counter_2, counter_3]
        draft_ai = DraftAI([], role_rs, [], all_counters)
        new_counter_rs = draft_ai.translate_counter_rs(all_counters)
        self.assertEqual(new_counter_rs, all_correct)

    def test_get_heroes_per_role(self):
        role_rs = [
            RoleR('Taka', 0, 0, 9),
            RoleR('Krul', 1, 0, 8),
            RoleR('Krul', 2, 0, 7),
            RoleR('Rona', 3, 0, 6),
            RoleR('Rona', 4, 0, 5),
            RoleR('Gwen', 1, 0, 3),
            RoleR('Gwen', 2, 0, 2),
            RoleR('Lyra', 0, 0, 1),
        ]
        draft_ai = DraftAI([], role_rs, [], [])
        hero_nums_per_role = draft_ai.get_heroes_per_role()
        correct = [
            {0, 7},
            {1, 5},
            {2, 6},
            {3},
            {4},
        ]
        self.assertEqual(hero_nums_per_role, correct)

    def test_get_same_hero_refs(self):
        role_rs = [
            RoleR('Taka', 0, 0, 9),
            RoleR('Krul', 1, 0, 8),
            RoleR('Krul', 2, 0, 7),
            RoleR('Rona', 3, 0, 6),
            RoleR('Rona', 4, 0, 5),
            RoleR('Gwen', 1, 0, 3),
            RoleR('Gwen', 2, 0, 2),
            RoleR('Lyra', 0, 0, 1),
        ]
        draft_ai = DraftAI([], role_rs, [], [])
        same_hero_refs = draft_ai.get_same_hero_refs()
        correct = [
            {0},
            {1, 2},
            {1, 2},
            {3, 4},
            {3, 4},
            {5, 6},
            {5, 6},
            {7},
        ]
        self.assertEqual(same_hero_refs, correct)

    def test_get_picks_n_bans(self):
        small_format = [
            (A, BAN),
            (B, BAN),
            (A, PICK_PICK),
            (A, PICK),
            (B, PICK_PICK),
            (B, PICK),
        ]
        role_rs = [
            RoleR('Taka', 0, 1, 9),
            RoleR('Krul', 1, 0, 9),
            RoleR('Krul', 2, 0, 8),
            RoleR('Rona', 3, 0, 7),
            RoleR('Rona', 4, 0, 6),
            RoleR('Skye', 4, 0, 5),
            RoleR('Gwen', 1, 0, 4),
            RoleR('Reza', 3, 0, 3),
            RoleR('Lyra', 1, 0, 2),
            RoleR('Lyra', 2, 0, 1),
        ]
        draft_ai = DraftAI(small_format, role_rs, [], [])

        # banned flex heroes don't cause multiple teams to be created
        history = ['Taka', 'Krul', 'Skye', 'Gwen', 'Reza']
        team_As, team_Bs, banned = draft_ai.get_picks_n_bans(history)
        self.assertEqual(len(team_As), 1)
        self.assertEqual(len(team_Bs), 1)
        self.assertEqual(team_As[0], [5, 6])
        self.assertEqual(team_Bs[0], [7])
        self.assertEqual(banned, [0, 1])  # bans return only first occurrence of a flex

        # a flex with one available role doesn't cause multiple teams
        history = ['Taka', 'Krul', 'Rona', 'Skye']
        team_As, team_Bs, banned = draft_ai.get_picks_n_bans(history)
        self.assertEqual(len(team_As), 1)
        self.assertEqual(team_As[0], [3, 5])
        self.assertEqual(team_Bs[0], [])
        self.assertEqual(banned, [0, 1])

        # multiple sets of teams created for a flex pick
        history = ['Taka', 'Krul', 'Lyra', 'Reza', 'Gwen']
        team_As, team_Bs, banned = draft_ai.get_picks_n_bans(history)
        self.assertEqual(len(team_As), 2)
        self.assertEqual(len(team_Bs), 1)
        self.assertEqual(team_As[0], [8, 7])
        self.assertEqual(team_As[1], [9, 7])
        self.assertEqual(team_Bs[0], [6])
        self.assertEqual(banned, [0, 1])

        # multiple sets of teams created for a flex pick (team B)
        history = ['Taka', 'Krul', 'Gwen', 'Reza', 'Lyra']
        team_As, team_Bs, banned = draft_ai.get_picks_n_bans(history)
        self.assertEqual(len(team_As), 1)
        self.assertEqual(len(team_Bs), 2)
        self.assertEqual(team_As[0], [6, 7])
        self.assertEqual(team_Bs[0], [8])
        self.assertEqual(team_Bs[1], [9])
        self.assertEqual(banned, [0, 1])

        # double flex pick clashing roles
        history = ['Taka', 'Reza', 'Lyra', 'Krul', 'Skye']
        team_As, team_Bs, banned = draft_ai.get_picks_n_bans(history)
        self.assertEqual(len(team_As), 2)
        self.assertEqual(len(team_Bs), 1)
        self.assertEqual(team_As[0], [8, 2])
        self.assertEqual(team_As[1], [9, 1])
        self.assertEqual(team_Bs[0], [5])
        self.assertEqual(banned, [0, 7])

        # double flex pick with no clashing roles
        history = ['Gwen', 'Skye', 'Taka', 'Reza', 'Krul', 'Rona']
        team_As, team_Bs, banned = draft_ai.get_picks_n_bans(history)
        self.assertEqual(len(team_As), 1)
        self.assertEqual(len(team_Bs), 4)
        self.assertEqual(team_As[0], [0, 7])
        self.assertEqual(team_Bs[0], [1, 3])
        self.assertEqual(team_Bs[1], [1, 4])
        self.assertEqual(team_Bs[2], [2, 3])
        self.assertEqual(team_Bs[3], [2, 4])
        self.assertEqual(banned, [6, 5])

        # double flex pick with no clashing roles + flex pick on enemy team
        history = ['Gwen', 'Skye', 'Taka', 'Lyra', 'Krul', 'Rona']
        team_As, team_Bs, banned = draft_ai.get_picks_n_bans(history)
        self.assertEqual(len(team_As), 2)
        self.assertEqual(len(team_Bs), 4)
        self.assertEqual(team_As[0], [0, 8])
        self.assertEqual(team_As[1], [0, 9])
        self.assertEqual(team_Bs[0], [1, 3])
        self.assertEqual(team_Bs[1], [1, 4])
        self.assertEqual(team_Bs[2], [2, 3])
        self.assertEqual(team_Bs[3], [2, 4])
        self.assertEqual(banned, [6, 5])

    def test_get_picks_n_bans_with_ban_pick(self):
        small_format = [
            (A, PICK),
            (B, PICK),
            (A, BAN),
            (B, BAN_PICK),
            (B, PICK),
            (A, PICK),
        ]
        role_rs = [
            RoleR('Taka', 0, 1, 9),
            RoleR('Krul', 1, 0, 9),
            RoleR('Krul', 2, 0, 8),
            RoleR('Rona', 3, 0, 7),
            RoleR('Rona', 4, 0, 6),
            RoleR('Skye', 4, 0, 5),
            RoleR('Gwen', 1, 0, 4),
            RoleR('Reza', 3, 0, 3),
            RoleR('Lyra', 1, 0, 2),
            RoleR('Lyra', 2, 0, 1),
        ]
        draft_ai = DraftAI(small_format, role_rs, [], [])

        # banned flex heroes don't cause multiple teams to be created
        history = ['Taka', 'Rona', 'Skye', 'Gwen', 'Reza', 'Lyra']
        team_As, team_Bs, banned = draft_ai.get_picks_n_bans(history)
        self.assertEqual(len(team_As), 2)
        self.assertEqual(len(team_Bs), 1)
        self.assertEqual(team_As[0], [0, 8])
        self.assertEqual(team_As[1], [0, 9])
        self.assertEqual(team_Bs[0], [4, 7])
        self.assertEqual(banned, [5, 6])  

    def test_generate_zobrist_keys(self):
        role_rs = [
            RoleR('Taka', 0, 0, 9),
            RoleR('Krul', 1, 0, 8),
            RoleR('Rona', 2, 0, 7),
            RoleR('Krul', 3, 0, 6),
            RoleR('Rona', 4, 0, 5),
        ]
        draft_ai = DraftAI([], role_rs, [], [])
        pick_keys_A, pick_keys_B, ban_keys = draft_ai.generate_zobrist_keys()

        # test all keys are differnet for picks
        self.assertTrue(len(set(pick_keys_A)) == 5)
        self.assertTrue(len(set(pick_keys_B)) == 5)

        # test that duplicates in banned share same key
        self.assertTrue(len(set(ban_keys)) == 3)
        self.assertEqual(ban_keys[1], ban_keys[3])
        self.assertEqual(ban_keys[2], ban_keys[4])


if __name__ == '__main__':
    unittest.main()
