import unittest 
import itertools
import random

from test.draft_az import draft_az
from autodraft.ai_prep import *
from _draft_ai import ffi, lib

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

    new_draft = Draft(new_format, draft.history)

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

    # @Later everything inside the stars can be executed once and then 
    # have multiple draft histories/states run on the search algorithm.
    # I will probably want to turn this into a standalone function if
    # it becomes clear that this is indeed the best way to go about
    # initialising details needed for search. Also, given that format
    # is only required once it would probably be best if I decoupled the
    # draft format and history.
    def run_c_search(self, draft, role_rs, synergy_rs, counter_rs):
        ordered_heroes, hero_nums = get_ordered_heroes(
            role_rs,
            synergy_rs,
            counter_rs,
        )
        # *********************************************************************
        # set the role rewards
        for hero_num, hero in enumerate(ordered_heroes):
            lib.set_role_r(hero_num, hero.A_role_value, hero.B_role_value)

        # set the synergy rewards
        new_synergy_rs = translate_synergy_rs(synergy_rs, hero_nums)
        for i, synergy_r in enumerate(new_synergy_rs):
            heroes, A_value, B_value = synergy_r
            lib.set_synergy_r(i, bit_format(heroes), A_value, B_value)

        # set the counter rewards
        new_counter_rs = translate_counter_rs(counter_rs, hero_nums)
        for i, counter_r in enumerate(new_counter_rs):
            heroes, foes, A_value, B_value = counter_r
            lib.set_counter_r(
                i,
                bit_format(heroes),
                bit_format(foes),
                A_value,
                B_value,
            )

        # set draft format
        # @Later I will want to just load up a fixed draft based on
        # a given tag.
        for stage, (team, selection_type) in enumerate(draft.format):
            lib.set_draft_stage(stage, team, selection_type)

        # set hero info for updating legal actions
        role_heroes = get_heroes_per_role(ordered_heroes)
        same_hero_refs = get_same_hero_refs(ordered_heroes, hero_nums)
        for hero_num, hero in enumerate(ordered_heroes):
            same_hero = same_hero_refs[hero_num]
            same_role_and_hero = role_heroes[hero.role] | same_hero
            lib.set_h_info(
                hero_num,
                bit_format(same_role_and_hero),  # passing in same, but search requires diff
                bit_format(same_hero),           # C code will take negation
            )

        # set all sizes
        lib.set_sizes(
            len(ordered_heroes),
            len(new_synergy_rs),
            len(new_counter_rs),
            len(draft.format),
        )
        # *********************************************************************

        teams_A, teams_B, banned = get_picks_n_bans(draft, hero_nums)

        def total_team_potential(team):
            return sum(ordered_heroes[h].potential for h in team)

        # sort teams from most likely to do well to least (achieves
        # maximum chance of cut offs during search)
        teams_A.sort(key=total_team_potential, reverse=True)
        teams_B.sort(key=total_team_potential, reverse=True)

        # prepare input for C search
        num_teams_A = len(teams_A)
        num_teams_B = len(teams_B)
        team_A_size = len(teams_A[0])
        team_B_size = len(teams_B[0])
        banned_size = len(banned)
        start_teams_A = [ffi.new('int[]', team) for team in teams_A]
        start_teams_B = [ffi.new('int[]', team) for team in teams_B]

        search_result = lib.run_search(
            num_teams_A,
            num_teams_B,
            team_A_size,
            team_B_size,
            banned_size,
            start_teams_A,
            start_teams_B,
            banned,
        )
        value = search_result.value
        action = ordered_heroes[search_result.best_hero].name
        selection = draft.format[len(draft.history)][1] 
        if selection == PICK or selection == BAN:
            return value, action
        else:
            action_2 = ordered_heroes[search_result.best_hero_2].name
            return value, action, action_2
    
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
        # getting countered which results in a total value of 2 (A is up by
        # 1 beforehand) vs 1 total for SAW.
        draft = Draft(SIMPLE_FORMAT, history)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)
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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action, action_2 = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action, action_2 = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action, action_2 = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action, action_2 = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action, action_2 = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action, action_2 = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action, action_2 = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

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

        draft, role_rs, synergy_rs, counter_rs = translate_old_draft(old_draft)
        value, action = self.run_c_search(draft, role_rs, synergy_rs, counter_rs)

        self.assertEqual(value, target_value)
        self.assertEqual(action, target_action)


if __name__ == '__main__':
    unittest.main()
