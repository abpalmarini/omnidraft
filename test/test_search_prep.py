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
        self.assertEqual(heroes[2].potential, 4)

        # finally check counters work
        counter_rs = [CounterR([('Rona', [3])], [('Krul', [0, 1])], 10, 10)]
        heroes, hero_nums = get_ordered_heroes(role_rs, synergy_rs, counter_rs)
        self.assertEqual(hero_nums[('Rona', 3)], 0)
        self.assertEqual(heroes[0].potential, 21)
               

if __name__ == '__main__':
    unittest.main()
