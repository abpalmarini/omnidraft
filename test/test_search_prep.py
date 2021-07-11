import unittest 
from collections import namedtuple

from search_prep import *


RoleR = namedtuple('RoleR', ['hero_name', 'role', 'A_value', 'B_value'])
SynergyR = namedtuple('SynergyR', ['heroes', 'A_value', 'B_value'])
CounterR = namedtuple('CounterR', ['heroes', 'adversaries', 'A_value', 'B_value'])


class TestSearchPrep(unittest.TestCase):

    def test_correctly_ordered_heroes(self):
        # check with just role rewards
        role_rs = [
            RoleR('Krul', 0, 2, 2), RoleR('Krul', 1, 0, 2),
            RoleR('Taka', 0, 3, 0), RoleR('Rona', 3, 0, 1),
        ]
        heroes, hero_nums = get_ordered_heroes(role_rs, [], [])
        self.assertEqual(hero_nums[('Krul', 0)], 0) 
        self.assertEqual(hero_nums[('Taka', 0)], 1) 
        self.assertEqual(hero_nums[('Krul', 1)], 2) 
        self.assertEqual(hero_nums[('Rona', 3)], 3) 

        # add synergy only applicable to krul in role 1
        synergy_rs = [SynergyR([('Krul', [1]), ('Taka', [0])], 5, 0)]
        heroes, hero_nums = get_ordered_heroes(role_rs, synergy_rs, [])
        self.assertEqual(heroes[0].name, 'Taka')
        self.assertEqual(heroes[1].name, 'Krul')
        self.assertEqual(heroes[1].role, 1)
        self.assertEqual(heroes[2].potential, 4)  # value not added to other krul

        # finally check counters work
        counter_rs = [CounterR([('Rona', [3])], [('Krul', [0, 1])], 10, 10)]
        heroes, hero_nums = get_ordered_heroes(role_rs, synergy_rs, counter_rs)
        self.assertEqual(hero_nums[('Rona', 3)], 0)
        self.assertEqual(heroes[0].potential, 21)

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
        # 4 new synergies should be created
        synergy_1 = SynergyR([('Taka', [0]), ('Krul', [1, 2]), ('Rona', [3, 4])], 2, 1)
        # only 2 synergies between compatible roles should be created
        synergy_2 = SynergyR([('Taka', [0]), ('Krul', [1, 2]), ('Gwen', [1, 2])], 0, 1)

        _, hero_nums = get_ordered_heroes(role_rs, [synergy_1], [])
        new_synergy_rs = translate_synergy_rs([synergy_1], hero_nums)
        self.assertEqual(len(new_synergy_rs), 4)
        correct_synergy_rs = [
            ([0, 1, 3], 2, 1),
            ([0, 1, 4], 2, 1),
            ([0, 2, 3], 2, 1),
            ([0, 2, 4], 2, 1),
        ]
        self.assertEqual(new_synergy_rs, correct_synergy_rs)
        return

        _, hero_nums = get_ordered_heroes(role_rs, [synergy_2], [])
        new_synergy_rs = translate_synergy_rs([synergy_2], hero_nums)
        self.assertEqual(len(new_synergy_rs), 2)
        correct_synergy_rs = [
            ([0, 1, 6], 0, 1),
            ([0, 2, 5], 0, 1),
        ]
        self.assertEqual(new_synergy_rs, correct_synergy_rs)

        _, hero_nums = get_ordered_heroes(role_rs, [synergy_1, synergy_2], [])
        new_synergy_rs = translate_synergy_rs([synergy_1, synergy_2], hero_nums)
        self.assertEqual(len(new_synergy_rs), 6)


if __name__ == '__main__':
    unittest.main()
