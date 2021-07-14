import unittest 
import itertools
import random

from test.draft_az import draft_az
from prep_ai import *

INF = 30000

# The old draft simulator for AZ agent generated random rewards between
# 0 and 1. However, for now I think the best approach is for users to
# enter rewards from 0 to 10, with two decimal places, and I will scale
# this to ints between 0 and 1000 for the C implementation.
def scale_rewards(draft):
    for r in itertools.chain(draft.rewards['role'], draft.rewards['combo']):
        r.A_value = int(r.A_value * 1000)
        r.B_value = int(r.B_value * 1000)


# The new AI expects a simple draft that includes format and history as
# well as role, synergy and counter rewards separated out and with an
# indicator on applicable roles for a synergy to be granted.
def translate_old_draft(draft):
    # may need to adjust format as well
    new_draft = Draft(draft.format, draft.history)

    role_rs = []
    for r in draft.rewards['role']:
        role_rs.append(RoleR(r.champ, r.role, r.A_value, r.B_value))

    # find all roles a hero plays
    hero_roles = {}
    for r in role_rs:
        if r.hero_name in hero_roles:
            continue
        roles = []
        for rr in role_rs:
            if r.hero_name == rr.hero_name:
                roles.append(rr.role)
        hero_roles[r.hero_name] = roles

    # split combos into synergies and counters with correct format
    synergy_rs = []
    counter_rs = []
    for r in draft.rewards['combo']:
        heroes = [(hero, hero_roles[hero]) for hero in r.team_champs]
        if not r.enemy_champs:
            synergy_r = SynergyR(heroes, r.A_value, r.B_value)
            synergy_rs.append(synergy_r)
        else:
            adversaries = [(hero, hero_roles[hero]) for hero in r.enemy_champs]
            counter_r = CounterR(heroes, adversaries, r.A_value, r.B_value)
            counter_rs.append(counter_r)

    return new_draft, role_rs, synergy_rs, counter_rs


# Basic alpha-beta search function to work on the old draft simulator.
# This will take ages to run, but the old simulator is well tested so
# it can provide good tests for the new bit field C implementation.
def alphabeta(draft, alpha, beta):
    if draft.terminal():
        return draft.terminal_value(),
    team, _ = draft.to_select()
    if team == draft_az.A:
        # maximising
        v = -INF
        best_action = None
        for action in draft.legal_actions():
            draft_c = draft.clone()
            draft_c.apply(action)
            child_v = alphabeta(draft_c, alpha, beta)[0]
            if child_v >= v:
                v = child_v
                best_action = action
            if v >= beta:
                break
            alpha = max(alpha, v)
    else:
        # minimising
        v = INF
        best_action = None
        for action in draft.legal_actions():
            draft_c = draft.clone()
            draft_c.apply(action)
            child_v = alphabeta(draft_c, alpha, beta)[0]
            if child_v <= v:
                v = child_v
                best_action = action
            if v <= alpha:
                break
            beta = min(beta, v)
    return v, best_action


SIMPLE_FORMAT = [
    (A, PICK),
    (B, PICK_PICK),
    (B, PICK),
    (A, PICK_PICK),
    (A, PICK),
    (B, PICK_PICK),
    (B, PICK),
    (A, PICK_PICK),
    (A, PICK),
    (B, PICK),
]


class TestDraftAI(unittest.TestCase):

    def setUp(self):
        # compile and save C code to self
        pass

    def run_c_search(self, draft, role_rs, synergy_rs, counter_rs):
        # will add details as I build and things become more clear
        return None, None
    
    def test_A_last_pick_counter(self):
        role_rs = [
            # heroes for team A
            RoleR('Taka', 0, 1, 1),
            RoleR('Krul', 1, 1, 1),
            RoleR('Rona', 2, 1, 1),
            RoleR('Gwen', 3, 1, 1),
            # heroes for team B
            RoleR('Lyra', 0, 1, 1),
            RoleR('Reim', 1, 1, 1),
            RoleR('Reza', 2, 1, 1),
            RoleR('Skye', 3, 1, 1),
            # at this point score is even with the following options
            RoleR('Ozo', 4, 1, 1),
            RoleR('Vox', 4, 2, 1),
            RoleR('SAW', 4, 3, 1),
        ]
        counter_rs = [
            CounterR([('Ozo', [4])], [('SAW', [4])], 5, 5),
        ]
        history = [
            'Taka', 'Lyra', 'Reim', 'Krul',
            'Rona', 'Reza', 'Skye', 'Gwen',
        ]

        # Optimal pick is for A to pick Vox as picking SAW would allow
        # for B to pick Ozo if playing optimally. Additionally A should
        # not pick Ozo in the hopes that B picks SAW as it should be 
        # expecting B to play optimally.
        draft = Draft(SIMPLE_FORMAT, history)
        value, action = self.run_c_search(draft, role_rs, [], counter_rs)
        self.assertEqual(value, 1)
        self.assertEqual(action, 'Vox')

    def test_A_last_pick_synergy(self):
        role_rs = [
            # heroes for team A
            RoleR('Taka', 0, 1, 1),
            RoleR('Krul', 1, 1, 1),
            RoleR('Rona', 2, 1, 1),
            RoleR('Gwen', 3, 1, 1),
            # heroes for team B
            RoleR('Lyra', 0, 1, 1),
            RoleR('Reim', 1, 1, 1),
            RoleR('Reza', 2, 1, 1),
            RoleR('Skye', 3, 1, 1),
            # at this point score is even with the following options
            RoleR('Ozo', 4, 1, 0),
            RoleR('Vox', 4, 2, 1),
            RoleR('SAW', 4, 3, 2),
        ]
        synergy_rs = [
            SynergyR([('Ozo', [4]), ('Skye', [3])], 0, 5),
        ]
        history = [
            'Taka', 'Lyra', 'Reim', 'Krul',
            'Rona', 'Reza', 'Skye', 'Gwen',
        ]

        # Optimal pick is for A to pick Ozo to prevent B from being able
        # to select it and gain big synergy reward. Value should then be
        # -1 if B is correctly assumed to select SAW.
        draft = Draft(SIMPLE_FORMAT, history)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, [])
        self.assertEqual(value, -1)
        self.assertEqual(action, 'Ozo')

    def test_B_last_pick(self):
        role_rs = [
            # heroes for team A
            RoleR('Taka', 0, 1, 1),
            RoleR('Krul', 1, 1, 1),
            RoleR('Rona', 2, 1, 1),
            RoleR('Gwen', 3, 1, 1),
            RoleR('Ozo', 4, 1, 1),
            # heroes for team B
            RoleR('Lyra', 0, 1, 1),
            RoleR('Reim', 1, 1, 1),
            RoleR('Reza', 2, 1, 1),
            RoleR('Skye', 3, 1, 1),
            # at this point A is up by 1 and B has following options
            RoleR('Vox', 4, 9, 1),
            RoleR('SAW', 4, 9, 2),
        ]
        synergy_rs = [
            SynergyR([('Vox', [4]), ('Taka', [0])], 0, 9),  # can't be achieved by B
            SynergyR([('Vox', [4]), ('Skye', [3])], 4, 3),
        ]
        counter_rs = [
            CounterR([('Ozo', [4])], [('Vox', [4])], 1, 5),
        ]
        history = [
            'Taka', 'Lyra', 'Reim', 'Krul',
            'Rona', 'Reza', 'Skye', 'Gwen', 'Ozo',
        ]

        # Despite being countered by Ozo the optimal pick for B is still
        # Vox as it will get 1 for role, 3 for synergy and minus 1 for
        # getting countered which results in a value of 3 over 2 for SAW.
        draft = Draft(SIMPLE_FORMAT, history)
        value, action = self.run_c_search(draft, role_rs, [], counter_rs)
        self.assertEqual(value, 3)
        self.assertEqual(action, 'Vox')

    def test_double_picks(self):
        random.seed(0)
        old_draft = draft_az.Draft()  # standard wildrift draft format
        scale_rewards(old_draft)
        # start from A's first double pick
        for _ in range(7):
            old_draft.apply(random.choice(old_draft.legal_actions()))

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        target_value, target_action = 1386, 9  # hard coding after running once

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)

    def test_single_bans(self):
        random.seed(1)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.BAN),  # starting from here
            (draft_az.A, draft_az.BAN),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )
        for _ in range(6):
            old_draft.apply(random.choice(old_draft.legal_actions()))

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        # target_value = -target_value  # get value in terms of team B's perspective
        target_value, target_action = -1055, 23  # hard coded after running once

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)

    def test_double_bans(self):
        random.seed(2)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.BAN),  # starting from here
            (draft_az.A, draft_az.BAN),  
            (draft_az.B, draft_az.BAN),
            (draft_az.B, draft_az.BAN),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )
        for _ in range(6):
            old_draft.apply(random.choice(old_draft.legal_actions()))

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        target_value, target_action = 1260, 30  # hard coded after running once

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)

    def test_pick_then_ban(self):
        random.seed(3)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),  # starting from here
            (draft_az.B, draft_az.BAN),  
            (draft_az.A, draft_az.BAN),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )
        for _ in range(5):
            old_draft.apply(random.choice(old_draft.legal_actions()))

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        # target_value = -target_value  # get value in terms of team B's perspective
        target_value, target_action = -28, 18  # hard coded after running once

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)

    def test_ban_then_pick(self):
        random.seed(4)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),  # starting from here
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.BAN),  
            (draft_az.A, draft_az.BAN),   # the ban then pick
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )
        for _ in range(4):
            old_draft.apply(random.choice(old_draft.legal_actions()))

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        target_value, target_action = 1422, 26  # hard coded after running once

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)


if __name__ == '__main__':
    unittest.main()
