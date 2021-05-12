from itertools import combinations
from copy import deepcopy

A_PICK = 1
A_BAN  = 2
B_PICK = 3
B_BAN  = 4

class Draft:

    def __init__(self, history=None, rewards=None, champs_roles=None,
                 A_roles=None, B_roles=None):
        self.format = (A_BAN, 
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
        self.num_champs = 70

        self.history = history or []
        self.rewards = rewards or self._generate_rewards()
        self.champs_roles = champs_roles or self._find_champs_roles()
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
            pass

    def apply(self, action):
        to_select = self.to_select()
        if to_select == A_PICK:
            self._update_open_roles(action, self.A_roles)
        elif to_select == B_PICK:
            self._update_open_roles(action, self.B_roles)
        self.history.append(action)

    # Returns champs that have not been picked or banned, and for pick
    # actions can play in at least one open role for team to pick. See
    # _update_open_roles for logic maintaining valid open roles.
    def legal_actions(self):

        def has_open_role(roles, team_roles):
            return bool(roles.intersection(team_roles['open']))

        def available(champ):
            return champ not in self.history
            
        to_select = self.to_select()
        if to_select == A_PICK:
            return [c for c, roles in enumerate(self.champs_roles) 
                    if available(c) and has_open_role(roles, self.A_roles)]
        elif to_select == B_PICK:
            return [c for c, roles in enumerate(self.champs_roles) 
                    if available(c) and has_open_role(roles, self.B_roles)]
        else:
            return [c for c, roles in enumerate(self.champs_roles)
                    if available(c) and bool(roles)] 

    def clone(self):
        history = self.history.copy()
        A_roles = deepcopy(self.A_roles)
        B_roles = deepcopy(self.B_roles)
        return Draft(history, self.rewards, self.champs_roles, A_roles, B_roles)

    # To ensure valid actions only contain champs who can fill an open
    # role we maintain a set of open roles and a list of roles
    # partially open (when a selected champ can play more than one).
    # By checking if the number of unique roles, in some subset of the
    # partial roles, is equal to the number of champs who can play them
    # we can determine when they are no longer open.
    def _update_open_roles(self, champ, team_roles):
        options = self.champs_roles[champ].intersection(team_roles['open'])
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

    def _generate_rewards(self):
        pass

    def _find_champs_roles(self):
        pass
