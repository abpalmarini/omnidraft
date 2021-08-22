""" Initial prep and interface for using the draft AI C engine. """

from _draft_ai import ffi, lib

from collections import namedtuple
import itertools
import random

# Make sure these stay the same as defined in draft_ai.h:
# teams / zobrist table indices
A         = 0
B         = 1
BAN_KEYS  = 2

# selection types
PICK      = 0
BAN       = 1
PICK_PICK = 2
PICK_BAN  = 3
BAN_PICK  = 4
BAN_BAN   = 5

ZOBRIST_BITS = 64


# For synergies and counters the heroes (and foes) are expected
# to be a list of tuples with each tuple containing the hero name and a
# list of applicable roles.
RoleR = namedtuple('RoleR', ['hero_name', 'role', 'A_value', 'B_value'])
SynergyR = namedtuple('SynergyR', ['heroes', 'A_value', 'B_value'])
CounterR = namedtuple('CounterR', ['heroes', 'foes', 'A_value', 'B_value'])


# Represents a *unique* hero-role combination.
class Hero:

    def __init__(self, role_r, all_synergy_rs, all_counter_rs):
        self.name = role_r.hero_name
        self.role = role_r.role
        self.A_role_value = role_r.A_value
        self.B_role_value = role_r.B_value
        self.synergy_rs = self.find_rewards(all_synergy_rs)
        self.counter_rs = self.find_rewards(all_counter_rs)

        self.potential = self.calculate_potential()

    def find_rewards(self, all_rewards):
        rewards = []
        for r in all_rewards:
            for hero_name, appl_roles in r.heroes:
                if self.name == hero_name and self.role in appl_roles:
                    rewards.append(r)
        return rewards

    # Simple approach that just totals all reward values.
    #
    # @Later can experiment with alternative approaches that take into
    # account the difficulty (size) of achieving a synergy/counter as
    # well as being countered themself.
    def calculate_potential(self):
        potential = 0
        potential += self.A_role_value + self.B_role_value
        for synergy_r in self.synergy_rs:
            potential += synergy_r.A_value + synergy_r.B_value
        for counter_r in self.counter_rs:
            potential += counter_r.A_value + counter_r.B_value
        return potential


# Creates a unique hero for each real hero-role combination and orders
# them by most potential. Treating heroes who play multiple roles as
# being different is what allows for fast generation of legal actions.
def get_ordered_heroes(role_rs, synergy_rs, counter_rs):
    heroes = [Hero(role_r, synergy_rs, counter_rs) for role_r in role_rs]
    heroes.sort(key=lambda hero: hero.potential, reverse=True)
    hero_nums = {(hero.name, hero.role): num for num, hero in enumerate(heroes)}
    return heroes, hero_nums  


# Now that heroes have been ordered, and additional ones created for
# flex picks, synergy rewards using these numbers can be created.
# Multiple versions are created to accommodate for the fact that heroes
# playing more than one role are treated as being unique.
def translate_synergy_rs(synergy_rs, hero_nums):
    ai_synergy_rs = []

    def valid_synergy_nums(heroes):
        valid = []
        hero_names, hero_roles = zip(*heroes)
        for roles in itertools.product(*hero_roles):
            if len(set(roles)) != len(heroes):
                # only sets of heroes in unique roles are valid
                continue
            synergy_nums = []
            for hero_name, role in zip(hero_names, roles):
                synergy_nums.append(hero_nums[(hero_name, role)])
            valid.append(synergy_nums)
        return valid

    for r in synergy_rs:
        for heroes in valid_synergy_nums(r.heroes):
            ai_synergy_rs.append((heroes, r.A_value, r.B_value))
    return ai_synergy_rs


# Same as for synergies, but also taking into account the foes.
def translate_counter_rs(counter_rs, hero_nums):
    ai_counter_rs = []

    def valid_counter_nums(heroes, foes):
        valid = []
        hero_names, hero_roles = zip(*heroes)
        foe_names, foe_roles = zip(*foes)
        for roles_h in itertools.product(*hero_roles):
            if len(set(roles_h)) != len(heroes):
                continue
            for roles_f in itertools.product(*foe_roles):
                if len(set(roles_f)) != len(foes):
                    continue
                counter_nums_h = []
                for hero_name, role in zip(hero_names, roles_h):
                    counter_nums_h.append(hero_nums[(hero_name, role)])
                counter_nums_f = []
                for hero_name, role in zip(foe_names, roles_f):
                    counter_nums_f.append(hero_nums[(hero_name, role)])
                valid.append((counter_nums_h, counter_nums_f))
        return valid

    for r in counter_rs:
        for heroes, foes in valid_counter_nums(r.heroes, r.foes):
            ai_counter_rs.append((heroes, foes, r.A_value, r.B_value))
    return ai_counter_rs


def get_heroes_per_role(ordered_heroes):
    role_heroes = [set() for _ in range(5)]
    for hero_num, hero in enumerate(ordered_heroes):
        role_heroes[hero.role].add(hero_num)
    return role_heroes


# Returns a list where element n contains a list of all hero num
# occurrences that refer to hero n, including itself. Once turned
# into a bit field the bitwise AND of the negation and the legal
# actions can quickly remove the now illegal heroes.
def get_same_hero_refs(ordered_heroes, hero_nums):
    all_refs = []
    for hero in ordered_heroes:
        refs = set() 
        for role in range(5):
            # will be true for at least one (its role)
            if (hero.name, role) in hero_nums:
                refs.add(hero_nums[(hero.name, role)])
        all_refs.append(refs)
    return all_refs


# As flex picks map to a different hero num for every role they play,
# there can be many possible 'teams'. All valid ones (no role clashes)
# should be accounted for in search. This does not effect bans as the
# same roles will be open, and all duplicates made illegal, no matter
# which variation is selected.
#
# @Later an outer function can handle cases where selections made based
# on the AI's suggestion can eliminate the other flex possibilities as
# we know the intended role for maximum value.
def get_picks_n_bans(history, draft_format, hero_nums):
    banned_names = []
    team_A_names = []
    team_B_names = []
    for hero_name, (team, selection) in zip(history, draft_format):
        if selection == BAN or selection == BAN_PICK or selection == BAN_BAN:
            banned_names.append(hero_name)
        elif team == A:
            team_A_names.append(hero_name)
        else:
            team_B_names.append(hero_name)

    banned = []
    for hero_name in banned_names:
        for role in range(5):
            if (hero_name, role) in hero_nums:
                banned.append(hero_nums[(hero_name, role)])
                break  # only one role variation needed for bans

    def all_roles(hero_name):
        return [role for role in range(5) if (hero_name, role) in hero_nums]

    team_A_roles = [all_roles(hero_name) for hero_name in team_A_names]
    team_B_roles = [all_roles(hero_name) for hero_name in team_B_names]

    teams_A = []
    teams_B = []

    for roles_A in itertools.product(*team_A_roles):
        if len(set(roles_A)) != len(team_A_names):
            continue
        team_A = []
        for hero_name, role in zip(team_A_names, roles_A):
            team_A.append(hero_nums[(hero_name, role)])
        teams_A.append(team_A)

    for roles_B in itertools.product(*team_B_roles):
        if len(set(roles_B)) != len(team_B_names):
            continue
        team_B = []
        for hero_name, role in zip(team_B_names, roles_B):
            team_B.append(hero_nums[(hero_name, role)])
        teams_B.append(team_B)

    return teams_A, teams_B, banned


# Generates the random zobrist bitstrings for a hero being picked by
# team A, picked by team B or being banned by either team. States can
# then be uniquely identified with a single hash by taking the XOR of
# the keys matching the combination of picked and banned heroes (see
# wikipedia.org/wiki/Zobrist_hashing for more details).
#
# All hero nums that are role variations of the same underlying hero
# are given the same key for bans because a ban of any is equivalent
# (unlike picks, bans don't effect the open roles a team then has).
def generate_zobrist_keys(ordered_heroes):
    used = set()

    def unique_key():
        key = random.getrandbits(ZOBRIST_BITS)
        while key in used:                          # single chance of getting duplicate is less
            key = random.getrandbits(ZOBRIST_BITS)  # than 1e-15%, but better safe than sorry
        return key

    # every hero num gets a unique key for picks
    pick_keys_A = [unique_key() for _ in range(len(ordered_heroes))]
    pick_keys_B = [unique_key() for _ in range(len(ordered_heroes))]

    # all hero role variations share same key for a ban
    name_key = {}
    ban_keys = []
    for hero in ordered_heroes:
        if hero.name in name_key:
            ban_keys.append(name_key[hero.name])
        else:
            key = unique_key()
            name_key[hero.name] = key
            ban_keys.append(key)

    return pick_keys_A, pick_keys_B, ban_keys


class DraftAI:
    """
    Abstracted interface for using the C draft AI code. Once initialised
    with a draft format and rewards, search can be run repeatedly for
    for any state to find the optimal value and action(s).
    """

    def __init__(self, draft_format, role_rs, synergy_rs, counter_rs):
        """
        Construct a DraftAI (defining the draft format and rewards it
        will operate on for all future searches).
        """

        self.draft_format = draft_format
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
        self._set_C_zobrist_keys()

        lib.clear_tt()

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

        # tt values are inapplicable when rewards switch so clearing
        # for now, but @Later it would be better to save and load for
        # each side so users can switch back and forth
        lib.clear_tt()

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

    def _set_C_zobrist_keys(self):
        keys = generate_zobrist_keys(self.ordered_heroes)
        pick_keys_A, pick_keys_B, ban_keys = keys
        for h in range(len(self.ordered_heroes)):
            lib.set_zobrist_key(A, h, pick_keys_A[h])
            lib.set_zobrist_key(B, h, pick_keys_B[h])
            lib.set_zobrist_key(BAN_KEYS, h, ban_keys[h])
