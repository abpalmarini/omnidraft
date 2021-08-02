""" Abstracted interface for using the C draft AI code. """

from _draft_ai import ffi, lib
from autodraft.ai_prep import *

class DraftAI:

    def __init__(self, draft_format, role_rs, synergy_rs, counter_rs):
        """
        Construct a DraftAI--defining the draft format and rewards it
        will operate on for all future searches.
        """

        self.draft_format = draft_format  # @Later can load in format based on a tag
        self.ordered_heroes, self.hero_nums = get_ordered_heroes(
            role_rs,
            synergy_rs,
            counter_rs,
        )

        # set all C globals
        self._set_C_role_rs()
        num_ai_synergy_rs = self._set_C_synergy_rs(synergy_rs)
        num_ai_counter_rs = self._set_C_counter_rs(counter_rs)
        self._set_C_draft_format()
        self._set_C_h_infos()
        self._set_C_sizes(
            len(self.ordered_heroes),
            num_ai_synergy_rs,
            num_ai_counter_rs,
            len(self.draft_format),
        )

    def run_search(self, history):
        """
        Wrapper for the C run_search function. Prepares all inputs and
        returns the optimal value and action(s) for a given history.

        @Important: This function will only work if called on the most
                    recently instantiated DraftAI object. This is 
                    because they all share the same underlying C global
                    memory that is set up in __init__.
        """

        teams_A, teams_B, banned = get_picks_n_bans(
            history,
            self.draft_format,
            self.hero_nums,
        )

        def total_team_potential(team):
            return sum(self.ordered_heroes[h].potential for h in team)

        # sort teams from most likely to do well to least (achieves
        # maximum likelihood of cut offs during search)
        teams_A.sort(key=total_team_potential, reverse=True)
        teams_B.sort(key=total_team_potential, reverse=True)

        search_result = lib.run_search(
            len(teams_A),
            len(teams_B),
            len(teams_A[0]),  # all team variations will be same size
            len(teams_B[0]),
            len(banned),
            [ffi.new('int[]', team) for team in teams_A],
            [ffi.new('int[]', team) for team in teams_B],
            banned,
        )
        value = search_result.value
        best_hero = self.ordered_heroes[search_result.best_hero].name
        _, selection = self.draft_format[len(history)]
        if selection == PICK or selection == BAN:
            return value, best_hero
        else:
            best_hero_2 = self.ordered_heroes[search_result.best_hero_2].name
            return value, best_hero, best_hero_2

    def switch_reward_team_values(self):
        """ Switches team A and B values across all rewards. """

        lib.switch_reward_team_values()
        # once TT is built this must also clear it

    def _set_C_role_rs(self):
        for hero_num, hero in enumerate(self.ordered_heroes):
            lib.set_role_r(hero_num, hero.A_role_value, hero.B_role_value)

    def _set_C_synergy_rs(self, synergy_rs):
        ai_synergy_rs = translate_synergy_rs(synergy_rs, self.hero_nums)
        for i, synergy_r in enumerate(ai_synergy_rs):
            heroes, A_value, B_value = synergy_r
            lib.set_synergy_r(i, len(heroes), heroes, A_value, B_value)
        return len(ai_synergy_rs)

    def _set_C_counter_rs(self, counter_rs):
        ai_counter_rs = translate_counter_rs(counter_rs, self.hero_nums)
        for i, counter_r in enumerate(ai_counter_rs):
            heroes, foes, A_value, B_value = counter_r
            lib.set_counter_r(
                i,
                len(heroes),
                heroes,
                len(foes),
                foes,
                A_value,
                B_value,
            )
        return len(ai_counter_rs)

    def _set_C_draft_format(self):
        for stage, (team, selection_type) in enumerate(self.draft_format):
            lib.set_draft_stage(stage, team, selection_type)

    def _set_C_h_infos(self):
        role_heroes = get_heroes_per_role(self.ordered_heroes)
        same_hero_refs = get_same_hero_refs(self.ordered_heroes, self.hero_nums)
        for hero_num, hero in enumerate(self.ordered_heroes):
            same_hero = same_hero_refs[hero_num]
            same_role_and_hero = list(role_heroes[hero.role] | same_hero)
            same_hero = list(same_hero)
            lib.set_h_info(
                hero_num,
                len(same_role_and_hero),
                same_role_and_hero,
                len(same_hero),
                same_hero,
            )

    def _set_C_sizes(self, num_heroes, num_synergy_rs, num_counter_rs, draft_len):
        lib.set_sizes(num_heroes, num_synergy_rs, num_counter_rs, draft_len)
