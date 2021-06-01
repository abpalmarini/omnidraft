from itertools import combinations, chain
from copy import deepcopy
from random import random, randint, sample, choice, choices
import numpy as np


NUM_ROLES = 5
# @Enums
A = 1
B = 2
PICK = 3
BAN  = 4


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
    format = ((A, BAN),
              (B, BAN),
              (A, BAN),
              (B, BAN),
              (A, PICK),
              (B, PICK),
              (B, PICK),
              (A, PICK),
              (A, PICK),
              (B, PICK),
              (B, PICK),
              (A, PICK),
              (A, PICK),
              (B, PICK))
    num_champs = 70

    def __init__(self, history=None, rewards=None, roles=None):
        self.history = history or []
        self.rewards = rewards or self._generate_rewards()
        if 'rrs_lookup' not in self.rewards:
            self._set_rrs_lookup()
        if 'nn_input' not in self.rewards:
            self._set_nn_rewards_input()
        self.roles = roles or self._init_roles()
        self.child_visits = []

    def to_select(self):
        return self.format[len(self.history)]

    def terminal(self):
        return len(self.history) == len(self.format)

    # Zero-sum evalution from team A's perspective in accordance to
    # the supplied rewards.
    def terminal_value(self):
        try:
            return self._terminal_value
        except AttributeError:
            team_A = {champ for champ, turn in zip(self.history, self.format) 
                      if turn == (A, PICK)}
            team_B = {champ for champ, turn in zip(self.history, self.format)
                      if turn == (B, PICK)}
            value = 0
            value += self._team_role_value(team_A, is_A=True)
            value -= self._team_role_value(team_B, is_A=False)
            value += self._synergy_value(team_A, team_B)
            value += self._counter_value(team_A, team_B)
            self._terminal_value = value
            return value

    # As there could be multiple role assignments for a given team, we 
    # recursively search all possible assignments and return the value
    # of the best.
    def _team_role_value(self, team_champs, is_A):
        team_rrs = [self.rewards['rrs_lookup'][champ] for champ in team_champs]

        def best_value(current_value, roles_filled, pos):
            if pos == len(team_champs):
                return current_value
            best = float('-inf')
            for rr in team_rrs[pos]:
                if rr.role not in roles_filled:
                    roles_filled.add(rr.role)
                    value = current_value + (rr.A_value if is_A else rr.B_value)
                    total_value = best_value(value, roles_filled, pos + 1)
                    roles_filled.remove(rr.role)
                    if total_value > best:
                        best = total_value
            return best
        return best_value(0, set(), 0)

    def _synergy_value(self, team_A, team_B):
        value = 0
        for reward in self.rewards['synergy']:
            if reward.champs.issubset(team_A):
                value += reward.A_value
            elif reward.champs.issubset(team_B):
                value -= reward.B_value
        return value

    def _counter_value(self, team_A, team_B):
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
        if to_select == (A, PICK):
            self._update_open_roles(action, self.roles['A'])
        elif to_select == (B, PICK):
            self._update_open_roles(action, self.roles['B'])
        A_open_roles = tuple(self.roles['A']['open'])
        B_open_roles = tuple(self.roles['B']['open'])
        self.roles['open_history'].append((A_open_roles, B_open_roles))
        self.history.append(action)

    # Returns champs that have not been picked or banned, have been
    # mentioned in a reward and for pick actions can play in at least
    # one open role for team to pick. Without enforcing that the NN
    # must have one champ per role it could gain a higher reward by
    # picking a champ in a duplicate role to avoid being countered.
    # See _update_open_roles for logic maintaining valid open roles.
    def legal_actions(self):
        def has_open_role(role_rewards, team_roles):
            for role_reward in role_rewards:
                if role_reward.role in team_roles['open']:
                    return True
            return False
        def available(champ):
            return champ not in self.history
        to_select = self.to_select()
        if to_select == (A, PICK):
            return [champ for champ, rrs in enumerate(self.rewards['rrs_lookup'])
                    if has_open_role(rrs, self.roles['A']) and available(champ)]
        elif to_select == (B, PICK):
            return [champ for champ, rrs in enumerate(self.rewards['rrs_lookup'])
                    if has_open_role(rrs, self.roles['B']) and available(champ)]
        else:
            return [champ for champ, rrs in enumerate(self.rewards['rrs_lookup'])
                    if bool(rrs) and available(champ)]

    def clone(self):
        return Draft(self.history.copy(), self.rewards, deepcopy(self.roles))

    # To ensure valid actions only contain champs who can fill an open
    # role we maintain a set of open roles and a list of roles
    # partially open (when a selected champ can play more than one).
    # By checking if the number of unique roles, in some subset of the
    # partial roles, is equal to the number of champs who can play them
    # we can determine when they are no longer open.
    def _update_open_roles(self, champ, team_roles):
        champ_roles = {rr.role for rr in self.rewards['rrs_lookup'][champ]}
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
        self.rewards['rrs_lookup'] = rrs_lookup

    # Provides information on what roles each team could still pick
    # champs from. This is needed for producing legal actions. The
    # roles each team had open at each stage in the draft is kept
    # for later producing the draft state when training the NN.
    def _init_roles(self):
        roles = {}
        roles['A'] = {'open': set(range(5)), 'partial': []}
        roles['B'] = {'open': set(range(5)), 'partial': []}
        roles['open_history'] = [(tuple(range(5)), tuple(range(5)))]
        return roles

    # Creates the NN input representation for each reward. These are
    # created once at the start and cached as they do not change from
    # state to state. The only thing that does change is the ordering
    # of values for each reward (depending if it is A or B to pick).
    def _set_nn_rewards_input(self):
        num_rewards = (len(self.rewards['role'])
                       + len(self.rewards['synergy'])
                       + len(self.rewards['counter']))
        num_features = 2 + 1 + NUM_ROLES + (2 * self.num_champs)
        nn_rewards = np.zeros((num_rewards, num_features))
        A_values = np.empty(num_rewards)
        B_values = np.empty(num_rewards)
        all_rewards = chain(self.rewards['role'],
                            self.rewards['synergy'],
                            self.rewards['counter'])
        for i, reward in enumerate(all_rewards):
            A_values[i] = reward.A_value
            B_values[i] = reward.B_value
            nn_reward = nn_rewards[i]
            offset = 2 # Skipping the reward values.
            if isinstance(reward, RoleReward):
                nn_reward[offset + 0] = 1
                offset += 1
                nn_reward[offset + reward.role] = 1
                offset += NUM_ROLES
                nn_reward[offset + reward.champ] = 1
            elif isinstance(reward, SynergyReward):
                offset += 1 + NUM_ROLES
                for champ in reward.champs:
                    nn_reward[offset + champ] = 1
            elif isinstance(reward, CounterReward):
                offset += 1 + NUM_ROLES
                for champ in reward.team_champs:
                    nn_reward[offset + champ] = 1
                offset += self.num_champs
                for champ in reward.enemy_champs:
                    nn_reward[offset + champ] = 1
        self.rewards['nn_input'] = (A_values, B_values, nn_rewards)

    # Creates the NN input representation for the state of the draft
    # at a given position in its history.
    def _make_nn_draft_state_input(self, pos):
        num_features = (1 + 1 + 1
                        + len(self.format)
                        + (2 * NUM_ROLES)
                        + (4 * self.num_champs))
        draft_state = np.zeros(num_features, dtype=np.float32)
        offset = 0

        # Turn information.
        team, selection_type = self.format[pos]
        next_turn_team, _ = self.format[(pos + 1) % len(self.format)]
        if team == A:
            draft_state[offset + 0] = 1
        if selection_type == PICK:
            draft_state[offset + 1] = 1
        if next_turn_team == team:
            draft_state[offset + 2] = 1
        offset += 3

        # Position in draft.
        draft_state[offset + pos] = 1
        offset += len(self.format)

        # Open roles for the selecting team and enemy.
        A_open_roles, B_open_roles = self.roles['open_history'][pos]
        if team == A:
            team_open_roles = A_open_roles
            enemy_open_roles = B_open_roles
        else:
            team_open_roles = B_open_roles
            enemy_open_roles = A_open_roles
        for role in team_open_roles:
            draft_state[offset + role] = 1
        offset += NUM_ROLES
        for role in enemy_open_roles:
            draft_state[offset + role] = 1
        offset += NUM_ROLES

        # Champs picked and banned for the selecting team and enemy.
        A_picks, B_picks, A_bans, B_bans = [], [], [], []
        for champ, turn in zip(self.history[:pos], self.format):
            if turn == (A, PICK):
                A_picks.append(champ)
            elif turn == (B, PICK):
                B_picks.append(champ)
            elif turn == (A, BAN):
                A_bans.append(champ)
            else:
                B_bans.append(champ)
        if team == A:
            team_picks = A_picks
            team_bans = A_bans
            enemy_picks = B_picks
            enemy_bans = B_bans
        else:
            team_picks = B_picks
            team_bans = B_bans
            enemy_picks = A_picks
            enemy_bans = A_bans
        for champ in team_picks:
            draft_state[offset + champ] = 1
        offset += self.num_champs
        for champ in team_bans:
            draft_state[offset + champ] = 1
        offset += self.num_champs
        for champ in enemy_picks:
            draft_state[offset + champ] = 1
        offset += self.num_champs
        for champ in enemy_bans:
            draft_state[offset + champ] = 1
        
        return draft_state

    # Returns both: a single vector capturing the entire draft state
    # when selecting for the given draft position and a vector for each
    # reward.
    def make_nn_input(self, pos=None):
        if pos is None:
            pos = len(self.history)

        # TODO
