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
        self.champs_roles = champs_roles or self.find_champs_roles()
        self.child_visits = []

        # Used to help with producing legal actions.
        self.team_A_roles = {
            'open': set(range(5)), 
            'partial': set(), 
            'num_partial': 0
            }
        self.team_B_roles = {
            'open': set(range(5)), 
            'partial': set(), 
            'num_partial': 0
            }

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
        if to_select == A_PICK:
            self._update_filled_roles(action, self.team_A_roles)
        elif to_select == B_PICK:
            self._update_filled_roles(action, self.team_B_roles)
        self.history.append(action)

    # Returns champs that have not been picked or banned, and for pick
    # actions can play in at least one open role for team to pick. See
    # _update_filed_roles for logic maintaining valid open roles.
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

    # If a champ can only play in a single role then we can immediately
    # remove that role from open roles. However, if it has the option
    # of being able to play more than one, then we can't remove them.
    # Instead we cache these as partially filled roles and wait until
    # the number of partially filled roles is equal to the number of 
    # champs who could occupy them. At that point all must play one of
    # these roles so we can remove them all from being open. 
    def _update_filled_roles(self, champ, team_roles):

        def check_partial_roles(team_roles):
            if len(team_roles['partial']) == team_roles['num_partial']:
                team_roles['open'] = team_roles['open'] - team_roles['partial']
                team_roles['partial'] = set()
                team_roles['num_partial'] = 0

        options = self.champs_roles[champ].intersection(team_roles['open'])
        if len(options) == 1:
            role = next(iter(options))
            team_roles['open'].remove(role)
            team_roles['partial'].discard(role)
            check_partial_roles(team_roles)
        else:
            team_roles['partial'] = team_roles['partial'].union(options)
            team_roles['num_partial'] += 1
            check_partial_roles(team_roles)

    def _generate_rewards(self):
        pass

    def _find_champs_roles(self):
        pass
