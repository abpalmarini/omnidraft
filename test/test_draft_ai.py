import unittest 
import itertools
import random

from test.draft_az import draft_az
from omnidraft.draft_ai import *

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
    new_format = []
    for stage in range(len(draft.format)):
        team, selection = draft.format[stage]
        team_n, selection_n = draft.format[(stage + 1) % len(draft.format)]
        if team != team_n:
            if selection == draft_az.PICK:
                new_format.append((A if team == draft_az.A else B, PICK))
            else:
                new_format.append((A if team == draft_az.A else B, BAN))
        else:
            if selection == draft_az.PICK and selection_n == draft_az.PICK:
                new_format.append((A if team == draft_az.A else B, PICK_PICK))
            elif selection == draft_az.PICK and selection_n == draft_az.BAN:
                new_format.append((A if team == draft_az.A else B, PICK_BAN))
            elif selection == draft_az.BAN and selection_n == draft_az.BAN:
                new_format.append((A if team == draft_az.A else B, BAN_BAN))
            elif selection == draft_az.BAN and selection_n == draft_az.PICK:
                new_format.append((A if team == draft_az.A else B, BAN_PICK))
            else:
                assert False

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
            foes = [(hero, hero_roles[hero]) for hero in r.enemy_champs]
            counter_r = CounterR(heroes, foes, r.A_value, r.B_value)
            counter_rs.append(counter_r)

    return draft.history, new_format, role_rs, synergy_rs, counter_rs


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
            # actions should not be updated if just equal to current
            # value as that value may have been a cutoff
            if child_v > v:
                v = child_v
                best_action = action
            elif child_v >= v:
                v = child_v
            alpha = max(alpha, v)
            if v >= beta:
                break
    else:
        # minimising
        v = INF
        best_action = None
        for action in draft.legal_actions():
            draft_c = draft.clone()
            draft_c.apply(action)
            child_v = alphabeta(draft_c, alpha, beta)[0]
            if child_v < v:
                v = child_v
                best_action = action
            elif child_v <= v:
                v = child_v
            beta = min(beta, v)
            if v <= alpha:
                break
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

    def run_c_search(self, history, draft_format, role_rs, synergy_rs, counter_rs):
        ai = DraftAI(draft_format, role_rs, synergy_rs, counter_rs)
        return ai.run_search(history)
    
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
            RoleR('Vox', 4, 3, 1),
            RoleR('SAW', 4, 4, 2),
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
        value, action = self.run_c_search(
            history,
            SIMPLE_FORMAT,
            role_rs,
            [],
            counter_rs,
        )
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
        value, action = self.run_c_search(
            history,
            SIMPLE_FORMAT,
            role_rs,
            synergy_rs,
            [],
        )
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
        # getting countered which results in a total value of 2 (A is up by
        # 1 beforehand) vs 1 total for SAW.
        value, action = self.run_c_search(
            history,
            SIMPLE_FORMAT,
            role_rs,
            synergy_rs,
            counter_rs,
        )
        self.assertEqual(value, 2)
        self.assertEqual(action, 'Vox')

    def test_double_picks(self):
        random.seed(0)
        old_draft = draft_az.Draft()  # standard wildrift draft format
        scale_rewards(old_draft)
        # start from A's first double pick
        for _ in range(7):
            old_draft.apply(random.choice(old_draft.legal_actions()))

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        target_value, target_action = 1386, 2  # hard coding after running once

        # get second action as well
        # old_draft_c = old_draft.clone()
        # old_draft_c.apply(target_action)
        # _, target_action_2 = alphabeta(old_draft_c, -INF, INF)
        target_action_2 = 9
        target_actions = (target_action, target_action_2)

        value, action, action_2 = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        # order of actions does not matter for two picks
        self.assertTrue((action, action_2) == target_actions 
                        or (action_2, action) == target_actions)

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

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        # target_value = -target_value  # get value in terms of team B's perspective
        target_value, target_action = -1055, 23  # hard coded after running once

        value, action = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)

    def test_double_bans(self):
        random.seed(2)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        # problem is this contains a triple pick which my ai doesn't handle
        # no game actually has a triple pick though, so I just need to change
        # this test
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.BAN),  # starting from here
            (draft_az.A, draft_az.BAN),  
            (draft_az.B, draft_az.BAN),
            (draft_az.B, draft_az.BAN),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )
        for _ in range(6):
            old_draft.apply(random.choice(old_draft.legal_actions()))

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        target_value, target_action = 437, 9  # hard coding after running once

        # get second action as well
        # old_draft_c = old_draft.clone()
        # old_draft_c.apply(target_action)
        # _, target_action_2 = alphabeta(old_draft_c, -INF, INF)
        target_action_2 = 11
        target_actions = (target_action, target_action_2)

        value, action, action_2 = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        # order of actions does not matter for two bans
        self.assertTrue((action, action_2) == target_actions 
                        or (action_2, action) == target_actions)

    def test_pick_then_ban(self):
        random.seed(3)
        # random.seed(9) gives me another chance to test multiple initial teams.
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

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        # target_value = -target_value  # get value in terms of team B's perspective
        target_value, target_action = -28, 11  # hard coding after running once

        # get second action as well
        # old_draft_c = old_draft.clone()
        # old_draft_c.apply(target_action)
        # _, target_action_2 = alphabeta(old_draft_c, -INF, INF)
        target_action_2 = 1

        value, action, action_2 = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        # order of selections matter for pick then ban
        self.assertEqual(action, target_action)
        self.assertEqual(action_2, target_action_2)

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

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        target_value, target_action = 1422, 26  # hard coded after running once

        value, action = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)

    def test_flex_pick_in_history_A_pick(self):
        random.seed(6)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),  # starting from here
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.BAN),  
            (draft_az.A, draft_az.BAN),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )
        # from inspection the following are all flex picks [1, 20, 29, 31, 39, 43]
        # this history will mean for each team comp the enemies can respond with 5
        # of their own
        old_draft.apply(1)   # roles: 1, 2, 3
        old_draft.apply(39)  # roles: 1, 2, 3
        old_draft.apply(43)  # roles: 3, 4
        old_draft.apply(20)  # roles: 2, 4

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        target_value, target_action = -1085, 10  # hard coding after running once

        value, action = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)

    def test_flex_pick_in_history_A_ban(self):
        random.seed(6)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.BAN),
            (draft_az.A, draft_az.BAN),  # starting from here
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )
        # from inspection the following are all flex picks [1, 20, 29, 31, 39, 43]
        # this history will mean for each team comp the enemies can respond with 5
        # of their own
        old_draft.apply(1)   # roles: 1, 2, 3
        old_draft.apply(39)  # roles: 1, 2, 3
        old_draft.apply(43)  # roles: 3, 4
        old_draft.apply(20)  # roles: 2, 4
        old_draft.apply(2)   # roles: 0
        old_draft.apply(7)   # roles: 2
        old_draft.apply(10)

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        target_value, target_action = -586, 45  # hard coding after running once

        value, action = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)

    def test_flex_pick_in_history_B_pick_pick(self):
        random.seed(11)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),  # starting from here
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )
        # from inspection the following are all flex picks [1, 20, 29, 31, 39, 43]
        # this history will mean for each team comp the enemies can respond with 5
        # of their own
        old_draft.apply(3)  # 1, 3
        old_draft.apply(16) # 2, 3, 4
        old_draft.apply(40) # 0, 1
        old_draft.apply(15) # 0, 2
        old_draft.apply(44) # 4

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        # target_value = -target_value
        target_value, target_action = 1346, 11

        # get second action as well
        # old_draft_c = old_draft.clone()
        # old_draft_c.apply(target_action)
        # _, target_action_2 = alphabeta(old_draft_c, -INF, INF)
        target_action_2 = 38
        target_actions = (target_action, target_action_2)

        value, action, action_2 = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        # order of actions does not matter for two picks
        self.assertTrue((action, action_2) == target_actions 
                        or (action_2, action) == target_actions)

    def test_flex_pick_in_history_B_pick_ban(self):
        random.seed(6)
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
        # from inspection the following are all flex picks [1, 20, 29, 31, 39, 43]
        # this history will mean for each team comp the enemies can respond with 5
        # of their own
        old_draft.apply(1)   # roles: 1, 2, 3
        old_draft.apply(39)  # roles: 1, 2, 3
        old_draft.apply(43)  # roles: 3, 4
        old_draft.apply(20)  # roles: 2, 4
        old_draft.apply(2)   # roles: 0

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        # target_value = -target_value  # get value in terms of team B's perspective
        target_value, target_action = 2027, 10  # hard coding after running once

        # get second action as well
        # old_draft_c = old_draft.clone()
        # old_draft_c.apply(target_action)
        # _, target_action_2 = alphabeta(old_draft_c, -INF, INF)
        target_action_2 = 40

        value, action, action_2 = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        # order of selection matters for pick then ban
        self.assertEqual(action, target_action)
        self.assertEqual(action_2, target_action_2)

    def test_flex_pick_in_history_B_ban_pick(self):
        random.seed(6)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.BAN),
            (draft_az.B, draft_az.BAN),  # starting from here
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )
        # from inspection the following are all flex picks [1, 20, 29, 31, 39, 43]
        # this history will mean for each team comp the enemies can respond with 5
        # of their own
        old_draft.apply(1)   # roles: 1, 2, 3
        old_draft.apply(39)  # roles: 1, 2, 3
        old_draft.apply(43)  # roles: 3, 4
        old_draft.apply(20)  # roles: 2, 4
        old_draft.apply(2)   # roles: 0

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        # target_value = -target_value
        target_value, target_action = 925, 45  # hard coding after running once

        # get second action as well
        # old_draft_c = old_draft.clone()
        # old_draft_c.apply(target_action)
        # _, target_action_2 = alphabeta(old_draft_c, -INF, INF)
        target_action_2 = 10

        value, action, action_2 = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        # order of selection matters for ban then pick
        self.assertEqual(action, target_action)
        self.assertEqual(action_2, target_action_2)

    def test_flex_pick_in_history_B_ban_ban(self):
        random.seed(6)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.BAN),
            (draft_az.A, draft_az.BAN),
            (draft_az.B, draft_az.BAN),  # starting from here
            (draft_az.B, draft_az.BAN),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )
        # from inspection the following are all flex picks [1, 20, 29, 31, 39, 43]
        # this history will mean for each team comp the enemies can respond with 5
        # of their own
        old_draft.apply(1)   # roles: 1, 2, 3
        old_draft.apply(39)  # roles: 1, 2, 3
        old_draft.apply(43)  # roles: 3, 4
        old_draft.apply(20)  # roles: 2, 4
        old_draft.apply(2)   # roles: 0
        old_draft.apply(10)

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        # target_value = -target_value
        target_value, target_action = 1016, 6

        # get second action as well
        # old_draft_c = old_draft.clone()
        # old_draft_c.apply(target_action)
        # _, target_action_2 = alphabeta(old_draft_c, -INF, INF)
        target_action_2 = 48
        target_actions = (target_action, target_action_2)

        value, action, action_2 = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        # order of actions does not matter for two bans
        self.assertTrue((action, action_2) == target_actions 
                        or (action_2, action) == target_actions)

    def test_flex_pick_in_history_B_last_pick(self):
        random.seed(9)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),  # starting from here
        )
        # from inspection these are pairs of heroes and playable roles 
        # for this random draft:
        # (44, [0, 1, 2]), (45, [1, 2]), (46, [1, 3]), (49, [1, 3])
        # by giving A 44 and 45, and B 46 and 49, there will be multiple
        # considerations needed for final pick no matter what
        old_draft.apply(44)
        old_draft.apply(46)
        old_draft.apply(49)
        old_draft.apply(45)
        for _ in range(5):
            old_draft.apply(random.choice(old_draft.legal_actions()))

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        # target_value = -target_value  # get value in terms of team B's perspective
        target_value, target_action = 1671, 14  # hard coding after running once

        value, action = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)

    def test_empty_history_pick(self):
        random.seed(10)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),  # starting from here
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
        )

        # target_value, target_action = alphabeta(old_draft, -INF, INF)
        target_value, target_action = 53, 38  # hard coding after running once

        value, action = self.run_c_search(*translate_old_draft(old_draft))

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)

    # This test is redundant as it is no longer the AI's job to handle
    # switching of reward team values. Instead, a new DraftAI object
    # should be instantiated with the switched rewards.
    def test_switch_reward_team_values(self):
        random.seed(12)
        old_draft = draft_az.Draft()
        scale_rewards(old_draft)
        old_draft.format = (
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.B, draft_az.PICK),
            (draft_az.A, draft_az.PICK),
            (draft_az.A, draft_az.PICK),  # starting from here
            (draft_az.B, draft_az.PICK),
        )
        for _ in range(8):
            old_draft.apply(random.choice(old_draft.legal_actions()))

        history, *draft_details = translate_old_draft(old_draft.clone())
        ai = DraftAI(*draft_details)

        target_value, target_action = alphabeta(old_draft.clone(), -INF, INF)
        value, action = ai.run_search(history)
        self.assertEqual(value, target_value, "before switch")
        self.assertEqual(action, target_action, "before switch")

        # switch reward values of old_draft
        for r in old_draft.rewards['role']:
            r.A_value, r.B_value = r.B_value, r.A_value
        for r in old_draft.rewards['combo']:
            r.A_value, r.B_value = r.B_value, r.A_value

        history, *draft_details = translate_old_draft(old_draft)
        switched_ai = DraftAI(*draft_details)

        target_value_s, target_action_s = alphabeta(old_draft, -INF, INF)
        value_s, action_s = switched_ai.run_search(history)
        self.assertEqual(value_s, target_value_s, "after initial switch")
        self.assertEqual(action_s, target_action_s, "after initial switch")

if __name__ == '__main__':
    unittest.main()
