import random
import numpy as np
from itertools import combinations, chain
from copy import deepcopy


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


class ComboReward:
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
    num_champs = 50

    def __init__(self, history=None, rewards=None, roles=None):
        self.history = history or []
        self.rewards = rewards or self._generate_rewards()
        if 'rrs_lookup' not in self.rewards:
            self._set_rrs_lookup()
        if 'nn_input' not in self.rewards:
            self._set_nn_rewards_input()
        self.roles = roles or self._init_roles()
        self.child_visits = []

    def to_select(self, pos=None):
        if pos is None:
            pos = len(self.history)
        return self.format[pos]

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
            value += self._combo_value(team_A, team_B)
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

    def _combo_value(self, team_A, team_B):
        value = 0
        for reward in self.rewards['combo']:
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

    # Returns champs that have not been picked or banned, have been
    # assigned a role in a role reward and for pick actions can play
    # in at least one open role for team to pick. Without enforcing
    # that the NN must have one champ per role it could gain a higher
    # reward by picking a champ in a duplicate role to avoid being
    # countered. See _update_open_roles for logic maintaining valid
    # open roles.
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
            legal = [champ for champ, rrs in enumerate(self.rewards['rrs_lookup'])
                     if has_open_role(rrs, self.roles['A']) and available(champ)]
            return legal or self._add_legal_champs(self.roles['A']['open'])
        elif to_select == (B, PICK):
            legal = [champ for champ, rrs in enumerate(self.rewards['rrs_lookup'])
                     if has_open_role(rrs, self.roles['B']) and available(champ)]
            return legal or self._add_legal_champs(self.roles['B']['open'])
        else:
            return [champ for champ, rrs in enumerate(self.rewards['rrs_lookup'])
                    if bool(rrs) and available(champ)]

    # For cases during training where a team has no champs available to
    # select for one of their open roles we randomly choose a previously
    # unmentioned champ for each open role and assign it zero reward.
    def _add_legal_champs(self, open_roles):
        unmentioned_champs = []
        for champ, rrs in enumerate(self.rewards['rrs_lookup']):
            if not rrs:
                unmentioned_champs.append(champ)
        new_champs = random.sample(unmentioned_champs, len(open_roles))
        for champ, role in zip(new_champs, open_roles):
            reward = RoleReward(champ, role, 0, 0)
            self.rewards['role'].append(reward)
            self.rewards['rrs_lookup'][champ].append(reward)
        self._set_nn_rewards_input()
        return new_champs

    def clone(self):
        return Draft(self.history.copy(), self.rewards, deepcopy(self.roles))

    # Basic implementation of generating role and combo (synergy and
    # counter) rewards needed for a draft. This is unlikely to
    # represent the type of rewards that will be seen in the real world.
    # The hope is that it will provide the network with a large range of
    # varying types that it can learn the direct relationship they have
    # on the draft outcome and thus be able to deal with anything.
    def _generate_rewards(self):
        roles = range(NUM_ROLES)
        synergy_size_options = range(2, NUM_ROLES + 1)
        counter_size_options = range(1, NUM_ROLES + 1)
        flex_size_options = range(2, NUM_ROLES + 1)

        def halving_weights(n):
            return [2**(-x) for x in range(1, n + 1)]

        # @Adjustable
        min_champs_per_role = 3
        max_synergies = 15
        synergy_size_weights = halving_weights(len(synergy_size_options))
        max_counters = 15
        counter_size_weights = halving_weights(len(counter_size_options))
        max_flex_champs = 10
        flex_size_weights = halving_weights(len(flex_size_options))

        # Segregate an initial selection of champs into roles.
        champs_per_role = []
        champ_pool = set(range(self.num_champs))
        for _ in range(NUM_ROLES):
            num_champs_in_role = random.randint(min_champs_per_role,
                                                self.num_champs // NUM_ROLES)
            champs = random.sample(champ_pool, num_champs_in_role)
            champs_per_role.append(champs)
            champ_pool -= set(champs)
        champs_used = set(range(self.num_champs)) - champ_pool

        # Create random synergies. 
        synergies = []
        num_synergies = random.randrange(max_synergies)
        synergy_sizes = random.choices(synergy_size_options,
                                       weights=synergy_size_weights,
                                       k=num_synergies)
        for size in synergy_sizes:
            roles_involved = random.sample(roles, size)
            champs = {random.choice(champs_per_role[role])
                      for role in roles_involved}
            if champs not in synergies:
                synergies.append(champs)

        # Create random counters.
        counters = []
        num_counters = random.randrange(max_counters)
        team_sizes = random.choices(counter_size_options,
                                    weights=counter_size_weights,
                                    k=num_counters)
        enemy_sizes = random.choices(counter_size_options,
                                     weights=counter_size_weights,
                                     k=num_counters)
        for team_size, enemy_size in zip(team_sizes, enemy_sizes):
            champs = random.sample(champs_used, team_size + enemy_size)
            counter = (set(champs[:team_size]), set(champs[team_size:]))
            if counter not in counters:
                counters.append(counter)

        # Now that synergies have been created we can let a sample of
        # champs play more than one role. 
        champs_selected = set()
        num_flex_champs = random.randrange(max_flex_champs)
        flex_sizes = random.choices(flex_size_options,
                                    weights=flex_size_weights,
                                    k=num_flex_champs)
        for size in flex_sizes:
            select_role, *extra_roles = random.sample(roles, size)
            champ = random.choice(champs_per_role[select_role])
            if champ not in champs_selected:
                champs_selected.add(champ)
                for role in extra_roles:
                    champs_per_role[role].append(champ)

        def rand_team_values():
            assignment = random.randrange(4)
            if assignment == 0:
                # Both teams receive same reward value.
                value = random.random()
                return value, value
            elif assignment == 1:
                # Each team receives a different value.
                return random.random(), random.random()
            elif assignment == 2:
                # Just team A receives a value.
                return random.random(), 0
            elif assignment == 3:
                # Just team B receives a value.
                return 0, random.random()

        # Randomly assign a reward value for team A/B and create the
        # the reward objects.
        rewards = {'role': [], 'combo': []}
        for role, champs in enumerate(champs_per_role):
            for champ in champs:
                reward = RoleReward(champ, role, *rand_team_values())
                rewards['role'].append(reward)
        for champs in synergies:
            reward = ComboReward(champs, set(), *rand_team_values())
            rewards['combo'].append(reward)
        for team_champs, enemy_champs in counters:
            reward = ComboReward(team_champs, enemy_champs, *rand_team_values())
            rewards['combo'].append(reward)
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
    # The role and combo rewards are given seperate vector 
    # representations.
    # Role:
    # - 2 real values for indicating the value of the reward for the
    #   selecting and enemy team
    # - (n = num roles) binary features for indicating the role
    # - (n = num champs) binary features for indicating the champ
    # Combo:
    # - 2 real values for indicating the value of the reward for the
    #   selecting and enemy team
    # - (2 * n = num champs) binary features for indicating the champs
    #   required for the selecting and enemy team
    def _set_nn_rewards_input(self):
        nn_input = {}

        # Role.
        num_role_rewards = len(self.rewards['role'])
        num_role_features = 2 + NUM_ROLES + self.num_champs
        nn_role_rewards = np.zeros((num_role_rewards, num_role_features),
                                    dtype=np.float32)
        role_A_values = np.empty(num_role_rewards, dtype=np.float32)
        role_B_values = np.empty(num_role_rewards, dtype=np.float32)
        for i, reward in enumerate(self.rewards['role']):
            role_A_values[i] = reward.A_value
            role_B_values[i] = reward.B_value
            nn_reward = nn_role_rewards[i]
            offset = 2 # Skipping the reward values.
            nn_reward[offset + reward.role] = 1
            offset += NUM_ROLES
            nn_reward[offset + reward.champ] = 1
        nn_input['role'] = (role_A_values, role_B_values, nn_role_rewards)

        # Combo.
        num_combo_rewards = len(self.rewards['combo'])
        num_combo_features = 2 + (2 * self.num_champs)
        nn_combo_rewards = np.zeros((num_combo_rewards, num_combo_features))
        combo_A_values = np.empty(num_combo_rewards)
        combo_B_values = np.empty(num_combo_rewards)
        for i, reward in enumerate(self.rewards['combo']):
            combo_A_values[i] = reward.A_value
            combo_B_values[i] = reward.B_value
            nn_reward = nn_combo_rewards[i]
            offset = 2 # Skipping the reward values.
            for champ in reward.team_champs:
                nn_reward[offset + champ] = 1
            offset += self.num_champs
            for champ in reward.enemy_champs:
                nn_reward[offset + champ] = 1
        nn_input['combo'] = (combo_A_values, combo_B_values, nn_combo_rewards)

        self.rewards['nn_input'] = nn_input

    # Creates the NN input representation for the state of the draft
    # at a given position in its history. This is a single vector
    # represented as follows:
    # - 1 binary feature indicating if the selecting team is A or B
    # - 1 binary feature indicating if the selecting team is picking
    #   or banning
    # - 1 binary feature indicating if the selecting team also selects
    #   next
    # - (n = total draft selections) binary features for indicating
    #   draft position
    # - (2 * n = num roles) binary features for indicating the selecting
    #   and enemy teams' open roles
    # - (4 * n = num champs) binary features for indicating what the
    #   selecting and enemy team have picked and banned
    def _make_nn_draft_state_input(self, pos):
        num_features = (1 + 1 + 1
                        + len(self.format)
                        + (2 * NUM_ROLES)
                        + (4 * self.num_champs))
        draft_state = np.zeros(num_features, dtype=np.float32)
        offset = 0

        # Turn information.
        team, selection_type = self.to_select(pos)
        next_turn_team, _ = self.to_select((pos + 1) % len(self.format))
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

    # Returns a single vector representing the entire draft state when
    # selecting for the given draft position as well as a vector for
    # each reward. For details on their representation see
    # _make_nn_draft_state_input and _set_nn_rewards_input.
    def make_nn_input(self, pos=None):
        if pos is None:
            pos = len(self.history)
        nn_draft_state = self._make_nn_draft_state_input(pos)
        nn_rewards = self.rewards['nn_input']
        role_A_values, role_B_values, nn_role_rewards = nn_rewards['role']
        combo_A_values, combo_B_values, nn_combo_rewards = nn_rewards['combo']
        # Setting the 'my team' and 'enemy team' values.
        team, _ = self.to_select(pos)
        if team == A:
            nn_role_rewards[:, 0] = role_A_values
            nn_role_rewards[:, 1] = role_B_values
            nn_combo_rewards[:, 0] = combo_A_values
            nn_combo_rewards[:, 1] = combo_B_values
        else:
            nn_role_rewards[:, 0] = role_B_values
            nn_role_rewards[:, 1] = role_A_values
            nn_combo_rewards[:, 0] = combo_B_values
            nn_combo_rewards[:, 1] = combo_A_values
        return nn_draft_state, nn_role_rewards, nn_combo_rewards
