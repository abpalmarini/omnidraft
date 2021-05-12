A_PICK = 1
A_BAN  = 2
B_PICK = 3
B_BAN  = 4

class Draft:

    def __init__(self, history=None, rewards=None, champs_roles=None):
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
        self.child_visits = []

        # Used to help with producing legal actions.
        self.team_A_roles = {'open': set(range(5)), 'partial': []}
        self.team_B_roles = {'open': set(range(5)), 'partial': []}

    def to_select(self):
        return self.format[len(self.history)]

    def terminal(self):
        return len(history) == len(self.format)

    def terminal_value(self):
        try:
            return self._terminal_value
        except AttributeError:
            pass

    def apply(self, action):
        to_select = self.to_select()
        # @Speed can adjust to not update open roles if its last pick
        if to_select == A_PICK:
            self._update_open_roles(action, self.team_A_roles)
        elif to_select == B_PICK:
            self._update_open_roles(action, self.team_B_roles)
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
                    if available(c) and has_open_role(roles, self.team_A_roles)]
        elif to_select == B_PICK:
            return [c for c, roles in enumerate(self.champs_roles) 
                    if available(c) and has_open_role(roles, self.team_B_roles)]
        else:
            return [c for c, roles in enumerate(self.champs_roles)
                    if available(c) and bool(roles)] 

    def _update_open_roles(self, champ, team_roles):
        options = self.champs_roles[champ].intersection(team_roles['open'])
        num_partial = len(team_roles['partial'])

        def handle_options():
            if len(options) == 1:
                team_roles['open'] -= options
                for roles in team_roles['partial']:
                    roles -= options
            else:
                team_roles['partial'].append(options)

        def total_resolve(champs_involved):
            combined = options.union(*team_roles['partial'])
            if len(combined) == champs_involved:
                team_roles['open'] -= combined
                team_roles['partial'] = []
                return True
            return False

        def pair_resolve():
            for i in range(num_partial):
                combined = options.union(team_roles['partial'][i])
                if len(combined) == 2:
                    team_roles['partial'].pop(i)
                    team_roles['open'] -= combined
                    for roles in team_roles['partial']:
                        roles -= combined
                    return True
            return False

        def triplet_resolve():
            for i in range(2):
                for j in range(1, 3):
                    if i == j: continue 
                    pair = team_roles['partial'][i], team_roles['partial'][j]
                    combined = options.union(*pair)
                    if len(combined) == 3:
                        # Pop j before i as j is always larger.
                        team_roles['partial'].pop(j)
                        team_roles['partial'].pop(i)
                        team_roles['open'] -= combined
                        team_roles['partial'][0] -= combined
                        return True
            return False

        if num_partial == 0:
            handle_options()
        elif num_partial == 1:
            if total_resolve(2):
                pass
            else:
                handle_options()
        elif num_partial == 2:
            if total_resolve(3):
                pass
            elif pair_resolve():
                pass
            else:
                handle_options()
        elif num_partial == 3:
            if total_resolve(4):
                pass
            elif triplet_resolve():
                pass
            elif pair_resolve():
                pass
            else:
                handle_options()

    def _generate_rewards(self):
        pass

    def _find_champs_roles(self):
        pass
