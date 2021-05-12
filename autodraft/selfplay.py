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
        # need to check for whether partial already has something or not, if it doesn't and 
        # options is len 1 then I just remove from open, if options is greater than one then I just add it
        # need to refactor by either creating methods for these things or doing some general thing with for 
        # loops
        if not team_roles['partial']:
            if len(options) == 1:
                team_roles['open'] = team_roles['open'] - options
            else:
                team_roles['partial'].append(options)
        # PARTIAL OF SIZE ONE
        elif len(team_roles['partial']) == 1:
            combined = options.union(*team_roles['partial'])
            if len(combined) == 2:
                team_roles['open'] = team_roles['open'] - combined
                team_roles['partial'] = []
                return 
            if len(options) == 1:
                team_roles['partial'][0] = team_roles['partial'][0] - options
                team_roles['open'] = team_roles['open'] - options
            else:
                team_roles['partial'].append(options)
        # PARTIAL OF SIZE TWO
        elif len(team_roles['partial']) == 2:
            combined = options.union(*team_roles['partial'])
            if len(combined) == 3:
                team_roles['open'] = team_roles['open'] - combined
                team_roles['partial'] = []
                return
            # First pair
            combined = options.union(team_roles['partial'][0])
            if len(combined) == 2:
                team_roles['open'] = team_roles['open'] - combined
                team_roles['partial'].pop(0)
                team_roles['partial'][0] = team_roles['partial'][0] - combined
                return
            # Second pair
            combined = options.union(team_roles['partial'][1])
            if len(combined) == 2:
                team_roles['open'] = team_roles['open'] - combined
                team_roles['partial'].pop(1)
                team_roles['partial'][0] = team_roles['partial'][0] - combined
                return
            # If doesn't resolve with anything remove from open and
            # partials if single, else add to partials.
            if len(options) == 1:
                team_roles['open'] = team_roles['open'] - options
                for i in range(3):
                    team_roles['partial'][i] = team_roles['partial'][i] - options
            else:
                team_roles['partial'].append(options)
        # PARTIAL OF SIZE THREE
        elif len(team_roles['partial']) == 3:
            combined = options.union(*team_roles['partial'])
            if len(combined) == 4:
                team_roles['open'] = team_roles['open'] - combined
                team_roles['partial'] = []
                return
            # Need to try all triplets
            for i in range(2):
                for j in range(1, 3):
                    if i == j: continue 
                    pair = team_roles['partial'][i], team_roles['partial'][j]
                    combined = options.union(*pair)
                    if len(combined) == 3:
                        team_roles['open'] = team_roles['open'] - combined
                        # Pop j before i as j is always larger.
                        team_roles['partial'].pop(j)
                        team_roles['partial'].pop(i)
                        team_roles['partial'][0] = team_roles['partial'][0] - combined
                        return
            # Finally try all pairs
            for i in range(3):
                combined = options.union(team_roles['partial'][i])
                if len(combined) == 2:
                    team_roles['open'] = team_roles['open'] - combined
                    team_roles['partial'].pop(i)
                    team_roles['partial'][0] = team_roles['partial'][0] - combined
                    team_roles['partial'][1] = team_roles['partial'][1] - combined
                    return
            # If doesn't resolve with anything remove from open and
            # partials if single, else add to partials.
            if len(options) == 1:
                team_roles['open'] = team_roles['open'] - options
                for i in range(3):
                    team_roles['partial'][i] = team_roles['partial'][i] - options
            else:
                team_roles['partial'].append(options)


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
