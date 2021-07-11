"""
Various functions for turning raw draft and reward detials into the
bit level data types needed for search.
"""

import itertools


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
# Multiple versions are created to accomadate for the fact that heroes
# playing more than one role are treated as being uniqe.
def translate_synergy_rs(synergy_rs, hero_nums):
    new_synergy_rs = []

    def valid_synergy_mappings(heroes):
        valid = []
        hero_names, hero_roles = zip(*heroes)
        for possible_roles in itertools.product(*hero_roles):
            if len(set(possible_roles)) != len(heroes):
                # only sets of heroes in uniqe roles are valid
                continue
            synergy_hero_nums = []
            for hero_name, role in zip(hero_names, possible_roles):
                synergy_hero_nums.append(hero_nums[(hero_name, role)])
            valid.append(synergy_hero_nums)
        return valid

    for r in synergy_rs:
        for heroes in valid_synergy_mappings(r.heroes):
            new_synergy_rs.append((heroes, r.A_value, r.B_value))
    return new_synergy_rs
