"""
Various functions for turning raw draft and reward details into the
bit level data types needed for search.
"""

from collections import namedtuple
import itertools

# @Unclear where to put these. C file will also need.
A         = 1
B         = 2
PICK      = 3
PICK_PICK = 4
BAN       = 5
BAN_BAN   = 6
PICK_BAN  = 7
BAN_PICK  = 8

# Format assumed to contain a list of tuples of team and selection type.
Draft = namedtuple('Draft', ['format', 'history'])

# For synergies and counters the heroes (and adversaries) are expected
# to be a list of tuples with each tuple containing the hero name and a
# list of applicable roles.
RoleR = namedtuple('RoleR', ['hero_name', 'role', 'A_value', 'B_value'])
SynergyR = namedtuple('SynergyR', ['heroes', 'A_value', 'B_value'])
CounterR = namedtuple('CounterR', ['heroes', 'adversaries', 'A_value', 'B_value'])


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
    new_synergy_rs = []

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
            new_synergy_rs.append((heroes, r.A_value, r.B_value))
    return new_synergy_rs


# Same as for synergies, but also taking into account the adversaries.
def translate_counter_rs(counter_rs, hero_nums):
    new_counter_rs = []

    def valid_counter_nums(heroes, adversaries):
        valid = []
        hero_names, hero_roles = zip(*heroes)
        adversary_names, adversary_roles = zip(*adversaries)
        for roles_h in itertools.product(*hero_roles):
            if len(set(roles_h)) != len(heroes):
                continue
            for roles_a in itertools.product(*adversary_roles):
                if len(set(roles_a)) != len(adversaries):
                    continue
                counter_nums_h = []
                for hero_name, role in zip(hero_names, roles_h):
                    counter_nums_h.append(hero_nums[(hero_name, role)])
                counter_nums_a = []
                for hero_name, role in zip(adversary_names, roles_a):
                    counter_nums_a.append(hero_nums[(hero_name, role)])
                valid.append((counter_nums_h, counter_nums_a))
        return valid

    for r in counter_rs:
        for heroes, adversaries in valid_counter_nums(r.heroes, r.adversaries):
            new_counter_rs.append((heroes, adversaries, r.A_value, r.B_value))
    return new_counter_rs


def get_heroes_per_role(ordered_heroes):
    role_heroes = [[] for _ in range(5)]
    for hero_num, hero in enumerate(ordered_heroes):
        role_heroes[hero.role].append(hero_num)
    return role_heroes


# Returns a list where element n contains a list of all hero num
# occurrences that refer to hero n, including itself. Once turned
# into a bit field the bitwise AND of the negation and the legal
# actions can quickly remove the now illegal heroes.
def get_same_hero_refs(ordered_heroes, hero_nums):
    all_refs = []
    for hero in ordered_heroes:
        refs = []
        for role in range(5):
            # will be true for at least one (its role)
            if (hero.name, role) in hero_nums:
                refs.append(hero_nums[(hero.name, role)])
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
        if selection == BAN or selection == BAN_BAN:
            banned_names.append(hero_name)
        elif team == A:
            team_A_names.append(hero_name)
        else:
            team_B_names.append(hero_name)

    picks_n_bans = []  # holds all sets of possible teams and bans

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

    # check all playable role assignements across both teams
    for roles_A in itertools.product(*team_A_roles):
        if len(set(roles_A)) != len(team_A_names):
            continue
        for roles_B in itertools.product(*team_B_roles):
            if len(set(roles_B)) != len(team_B_names):
                continue
            team_A = []
            for hero_name, role in zip(team_A_names, roles_A):
                team_A.append(hero_nums[(hero_name, role)])
            team_B = []
            for hero_name, role in zip(team_B_names, roles_B):
                team_B.append(hero_nums[(hero_name, role)])
            picks_n_bans.append((team_A, team_B, banned))

    return picks_n_bans