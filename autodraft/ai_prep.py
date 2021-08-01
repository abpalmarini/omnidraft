"""
Various functions for turning raw draft and reward details into the
bit level data types needed for search.
"""

from collections import namedtuple
import itertools

# Make sure these stay the same as defined in ai_draft.h
A         = 0
B         = 1

PICK      = 0
BAN       = 1
PICK_PICK = 2
PICK_BAN  = 3
BAN_PICK  = 4
BAN_BAN   = 5


# Format assumed to contain a list of tuples of team and selection type.
Draft = namedtuple('Draft', ['format', 'history'])

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
def get_picks_n_bans(draft, hero_nums):
    banned_names = []
    team_A_names = []
    team_B_names = []
    for (team, selection), hero_name in zip(draft.format, draft.history):
        if selection == BAN or selection == BAN_BAN or selection == BAN_PICK:
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

    team_As = []
    team_Bs = []

    for roles_A in itertools.product(*team_A_roles):
        if len(set(roles_A)) != len(team_A_names):
            continue
        team_A = []
        for hero_name, role in zip(team_A_names, roles_A):
            team_A.append(hero_nums[(hero_name, role)])
        team_As.append(team_A)

    for roles_B in itertools.product(*team_B_roles):
        if len(set(roles_B)) != len(team_B_names):
            continue
        team_B = []
        for hero_name, role in zip(team_B_names, roles_B):
            team_B.append(hero_nums[(hero_name, role)])
        team_Bs.append(team_B)

    return team_As, team_Bs, banned


# Heroes in the search algorithm are represented by the bit
# corresponding to their hero number in a word. I.e. 2 to the 
# power of hero num.
def bit_format(heroes):
    return sum(2**hero_num for hero_num in heroes)
