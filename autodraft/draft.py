from itertools import combinations
from copy import deepcopy
from random import random, randint, sample, choice, choices


A_PICK = 1
A_BAN  = 2
B_PICK = 3
B_BAN  = 4


class RoleReward:
    __slots__ = ['champ', 'role', 'A_value', 'B_value']
    def __init__(self, champ, role, A_value, B_value):
        self.champ = champ
        self.role = role
        self.A_value = A_value
        self.B_value = B_value


class SynergyReward:
    __slots__ = ['champs', 'A_value', 'B_value']
    def __init__(self, champs, A_value, B_value):
        self.champs = champs
        self.A_value = A_value
        self.B_value = B_value


class CounterReward:
    __slots__ = ['team_champs', 'enemy_champs', 'A_value', 'B_value']
    def __init__(self, team_champs, enemy_champs, A_value, B_value):
        self.team_champs = team_champs
        self.enemy_champs = enemy_champs
        self.A_value = A_value
        self.B_value = B_value


class Draft:
    # @Adjustable
    format = (A_BAN, 
              B_BAN,
              A_BAN,
              B_BAN,
              A_PICK,
              B_PICK,
              B_PICK,
              A_PICK,
              A_PICK,
              B_PICK,
              B_PICK,
              A_PICK,
              A_PICK,
              B_PICK) 
    num_champs = 70

    def __init__(self, history=None, rewards=None, rrs_lookup=None,
                 A_roles=None, B_roles=None):
        self.history = history or []
        self.rewards = rewards or self._generate_rewards()
        self.rrs_lookup = rrs_lookup or self._set_rrs_lookup()
        self.A_roles = A_roles or {'open': set(range(5)), 'partial': []}
        self.B_roles = B_roles or {'open': set(range(5)), 'partial': []}
        self.child_visits = []

    def to_select(self):
        return self.format[len(self.history)]

    def terminal(self):
        return len(self.history) == len(self.format)

    def terminal_value(self):
        try:
            return self._terminal_value
        except AttributeError:
            team_A = {champ for champ, turn in zip(self.history, self.format) 
                      if turn == A_PICK}
            team_B = {champ for champ, turn in zip(self.history, self.format)
                      if turn == B_PICK}
            value = 0
            value += _role_value(team_A, team_B)
            value += _synergy_value(team_A, team_B)
            value += _counter_value(team_A, team_B)

    def _role_value(team_A, team_B):
        # this function requires knowing all role rewards for each 
        # champ in the team and there is no way around that if we 
        # want to test which role assignment gives best reward.
        # we could loop through all role rewards every time here and 
        # store the values corresponding to team a and b heroes. 
        # however, if we need to evaluate terminal positions for a 
        # single set of commands over and over which we will as we 
        # approach the end stage of draft because for example in second 
        # last pick there is only 56 initial heroes to try then every other 
        # simulation is going to be doing a terminal value. so that saves
        # having to do about 750 loops through the role rewards per game at 
        # the MINIMUM. which means i save at least a second every 200 games.
        # so its probably best if i refactor champs_roles to include the role
        # rewards for each hero. that way i can still use it for open roles,
        # albeit with more hastle, but can also use it for this.
        pass
            
    def _synergy_value(team_A, team_B):
        value = 0
        for reward in self.rewards['synergy']:
            if reward.champs.issubset(team_A):
                value += reward.A_value
            elif reward.champs.issubset(team_B):
                value -= reward.B_value
        return value

    def _counter_value(team_A, team_B):
        value = 0
        for reward in self.rewards['counter']:
            if (reward.team_champs.issubset(team_A) 
                    and reward.enemy_champs.issubset(team_B)):
                value += reward.A_value
            elif (reward.team_champs.issubset(team_B)
                    and reward.enemy_champs.issubset(team_A)):
                value -= reward.B_value
        return value

    def apply(self, action):
        to_select = self.to_select()
        if to_select == A_PICK:
            self._update_open_roles(action, self.A_roles)
        elif to_select == B_PICK:
            self._update_open_roles(action, self.B_roles)
        self.history.append(action)

    # Returns champs that have not been picked or banned, have been
    # mentioned in a reward and for pick actions can play in at least
    # one open role for team to pick. See _update_open_roles for logic
    # maintaining valid open roles.
    def legal_actions(self):
        def has_open_role(role_rewards, team_roles):
            for role_reward in role_rewards:
                if role_reward.role in team_roles['open']:
                    return True
            return False
        def available(champ):
            return champ not in self.history
        to_select = self.to_select()
        if to_select == A_PICK:
            return [champ for champ, rrs in enumerate(self.rrs_lookup)
                    if has_open_role(rrs, self.A_roles) and available(champ)]
        elif to_select == B_PICK:
            return [champ for champ, rrs in enumerate(self.rrs_lookup)
                    if has_open_role(rrs, self.B_roles) and available(champ)]
        else:
            return [champ for champ, rrs in enumerate(self.rrs_lookup)
                    if bool(rrs) and available(champ)]

    def clone(self):
        history = self.history.copy()
        A_roles = deepcopy(self.A_roles)
        B_roles = deepcopy(self.B_roles)
        return Draft(history, self.rewards, self.rrs_lookup, A_roles, B_roles)

    # To ensure valid actions only contain champs who can fill an open
    # role we maintain a set of open roles and a list of roles
    # partially open (when a selected champ can play more than one).
    # By checking if the number of unique roles, in some subset of the
    # partial roles, is equal to the number of champs who can play them
    # we can determine when they are no longer open.
    def _update_open_roles(self, champ, team_roles):
        champ_roles = {rr.role for rr in self.rrs_lookup[champ]}
        options = champ_roles.intersection(team_roles['open'])
        for n_champs in range(len(team_roles['partial']), 0, -1):
            for partial_subset in combinations(team_roles['partial'], n_champs):
                unique_roles = options.union(*partial_subset)
                if len(unique_roles) == n_champs + 1:
                    for roles in partial_subset:
                        team_roles['partial'].remove(roles)
                    for roles in team_roles['partial']:
                        roles -= unique_roles
                    team_roles['open'] -= unique_roles
                    return
        # New champ role(s) was unable to resolve with anything else.
        if len(options) == 1:
            team_roles['open'] -= options
            for roles in team_roles['partial']:
                roles -= options
        else:
            team_roles['partial'].append(options)

    # Basic implementation of generating role, synergy and counter
    # rewards needed for a draft. This is unlikely to represent the
    # type of rewards that will be seen in the real world. The hope is
    # that it will provide the network with a large range of varying
    # types that it can learn the direct relationship they have on the
    # draft outcome. 
    def _generate_rewards(self):
        NUM_ROLES = 5
        # @Adjustable
        min_champs_per_role = 4
        num_synergies_range = (3, 20)
        p_synergy_size = [0.7, 0.2, 0.07, 0.03] # sizes 2..5
        num_counters_range = (3, 20)
        p_counter_size = [0.7, 0.2, 0.06, 0.03, 0.01] # sizes 1..5
        num_versatile_range = (5, 20)
        p_versatility = [0.65, 0.25, 0.07, 0.03] # sizes 2..5

        # Segregate an initial selection of champs into roles.
        champs_per_role = []
        champ_pool = set(range(self.num_champs))
        def rand_role_num(): 
            return randint(min_champs_per_role, self.num_champs // 5)
        for num in [rand_role_num() for _ in range(NUM_ROLES)]:
            champs = sample(champ_pool, num)
            champs_per_role.append(champs)
            champ_pool -= set(champs)

        # Create random synergies. 
        synergies = []
        num_synergies = randint(*num_synergies_range)
        sizes = choices(range(2, 6), k=num_synergies, weights=p_synergy_size)
        for size in sizes:
            roles_involved = sample(range(NUM_ROLES), k=size)
            champs = {choice(champs_per_role[role]) for role in roles_involved}
            synergies.append(champs)

        # Create random counters.
        counters = []
        champs_used = set(range(self.num_champs)) - champ_pool 
        num_counters = randint(*num_counters_range)
        team_sizes = choices(range(1, 6), k=num_counters, weights=p_counter_size)
        enemy_sizes = choices(range(1, 6), k=num_counters, weights=p_counter_size)
        for team_size, enemy_size in zip(team_sizes, enemy_sizes):
            champs = sample(champs_used, team_size + enemy_size)
            counter = (set(champs[:team_size]), set(champs[team_size:]))
            counters.append(counter)

        # Now that synergies have been created we can let a sample of
        # champs play more than one role. 
        champs_selected = set()
        num_versatile = randint(*num_versatile_range)
        amounts = choices(range(2, 6), k=num_versatile, weights=p_versatility)
        for amount in amounts:
            select_role, *extra_roles = sample(range(NUM_ROLES), k=amount)
            champ = choice(champs_per_role[select_role])
            if champ in champs_selected: continue 
            champs_selected.add(champ)
            for role in extra_roles:
                champs_per_role[role].append(champ)

        def rand_team_values():
            assignment = choice(range(4))
            if assignment == 0:
                # Both teams receive same reward value.
                value = random()
                return value, value
            elif assignment == 1:
                # Each team receives a different value.
                return random(), random()
            elif assignment == 2:
                # Just team A receives a value.
                return random(), 0
            elif assignment == 3:
                # Just team B receives a value.
                return 0, random()

        # Randomly assign a reward value for team A/B and create the
        # the reward objects.
        rewards = {'role': [], 'synergy': [], 'counter': []}
        for role, champs in enumerate(champs_per_role):
            for champ in champs:
                reward = RoleReward(champ, role, *rand_team_values())
                rewards['role'].append(reward)
        for champs in synergies:
            reward = SynergyReward(champs, *rand_team_values())
            rewards['synergy'].append(reward)
        for team_champs, enemy_champs in counters:
            reward = CounterReward(team_champs, enemy_champs, 
                                   *rand_team_values())
            rewards['counter'].append(reward)
        return rewards

    # Provides a list of size num_champs where each entry contains
    # the corresponding champ's role rewards. Fast access to a champ's
    # roles is needed for maintaining open roles and providing legal
    # actions. Fast access to roles + reward is need for calculating 
    # terminal value.
    def _set_rrs_lookup(self):
        rrs_lookup = [list() for _ in range(self.num_champs)]
        for role_reward in self.rewards['role']:
            rrs_lookup[role_reward.champ].append(role_reward)
        return rrs_lookup

