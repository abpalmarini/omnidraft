""" Initial prep and interface for using the draft AI C engine. """

from collections import namedtuple
import itertools
import random

from _draft_ai import ffi, lib


constants = lib.get_constants()  # defined in draft_ai.h and returned to ensure consistency

# max sizes
MAX_NUM_HEROES = constants.max_num_heroes
MAX_SYNERGY_RS = constants.max_synergy_rs
MAX_COUNTER_RS = constants.max_counter_rs  
MAX_DRAFT_LEN  = constants.max_draft_len

# teams / zobrist table indices
A         = constants.a
B         = constants.b
BAN_KEYS  = constants.ban_keys

# selection types
PICK      = constants.pick
BAN       = constants.ban
PICK_PICK = constants.pick_pick
PICK_BAN  = constants.pick_ban
BAN_PICK  = constants.ban_pick
BAN_BAN   = constants.ban_ban

INF = constants.inf

PICKS = {PICK, PICK_PICK, PICK_BAN}
BANS = {BAN, BAN_PICK, BAN_BAN}

ZOBRIST_BITS = 64
ROLES = range(5)


# For synergies and counters the heroes (and foes) are expected to be a
# list of tuples with each tuple containing the hero name and a list of
# applicable roles. 
RoleR = namedtuple('RoleR', ['hero_name', 'role', 'A_value', 'B_value'])
SynergyR = namedtuple('SynergyR', ['heroes', 'A_value', 'B_value'])
CounterR = namedtuple('CounterR', ['heroes', 'foes', 'A_value', 'B_value'])


class Hero:
    """Represents a unique hero-role combination."""

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


class DraftAI:
    """
    Abstracted interface for using the C draft AI engine. Once
    initialised with a draft format and rewards, search can be run
    repeatedly with run_search(history) to find the optimal value
    and action(s).
    """

    def __init__(self, draft_format, role_rs, synergy_rs, counter_rs):
        """
        Construct a DraftAI (defining the draft format and rewards it
        will operate on for all future searches).
        """

        if len(role_rs) > MAX_NUM_HEROES:
            raise ValueError(f"Max of {MAX_NUM_HEROES} role_rs supported")

        def check_value(value):
            if not isinstance(value, int):
                raise TypeError("Invalid team value: must be an int")
            if value < 0 or value > 1000:
                # 1000 picked as users can than use 0 to 10 with 2 decimal
                # places. Can also safely assume it will never exceed INF.
                raise ValueError("Invalid team value: must be in range [0, 1000]")

        for r in itertools.chain(role_rs, synergy_rs, counter_rs):
            if isinstance(r, RoleR) and r.role not in ROLES:
                raise ValueError("Roles must be an integer from 0 to 4")
            check_value(r.A_value)
            check_value(r.B_value)

        self.draft_format = self.get_ai_draft_format(draft_format)
        self.init_ordered_heroes(role_rs, synergy_rs, counter_rs)
        self._set_C_globals(synergy_rs, counter_rs)

    # Creates a unique 'hero' for each real hero-role combination and
    # orders them by most potential.
    def init_ordered_heroes(self, role_rs, synergy_rs, counter_rs):
        heroes = [Hero(role_r, synergy_rs, counter_rs) for role_r in role_rs]
        heroes.sort(key=lambda hero: hero.potential, reverse=True)
        self.ordered_heroes = heroes

        # allow for getting specifc hero num for a hero-role combination
        self.hero_nums = {}
        for num, hero in enumerate(self.ordered_heroes):
            name_role = (hero.name, hero.role)
            if name_role not in self.hero_nums:
                self.hero_nums[name_role] = num
            else:
                raise ValueError(f"Duplicate role reward: {name_role}")

        # allow for getting all roles a hero can play
        self.hero_roles = {}
        for hero in heroes:
            if hero.name not in self.hero_roles:
                roles = [role for role in ROLES if (hero.name, role) in self.hero_nums]
                self.hero_roles[hero.name] = roles

    # After heroes have been ordered, and additional ones created for
    # flex picks, synergy rewards using these hero nums can be created.
    # Multiple versions of a reward may be created if it contains heroes
    # who play more than one role as they are now treated different.
    def translate_synergy_rs(self, synergy_rs):
        ai_synergy_rs = []
        synergies = set()

        def valid_synergy_nums(heroes):
            valid = []
            hero_names, hero_roles = zip(*heroes)
            for roles in itertools.product(*hero_roles):
                if len(set(roles)) != len(heroes):
                    # only sets of heroes in unique roles are valid
                    continue
                synergy_nums = []
                for hero_name, role in zip(hero_names, roles):
                    synergy_nums.append(self.hero_nums[(hero_name, role)])
                synergy_nums.sort()  # sort to catch potential duplicates
                valid.append(synergy_nums)
            return valid

        for r in synergy_rs:
            for heroes in valid_synergy_nums(r.heroes):
                synergy = tuple(heroes)
                if synergy not in synergies:
                    ai_synergy_rs.append((heroes, r.A_value, r.B_value))
                    synergies.add(synergy)
                else:
                    hero_names = [self.ordered_heroes[h].name for h in heroes]
                    raise ValueError(f"Duplicate synergy reward: {hero_names}")

        if len(ai_synergy_rs) <= MAX_SYNERGY_RS:
            return ai_synergy_rs
        else:
            raise ValueError(f"Not enough memory for all AI synergy rs")

    # Same as for synergies, but also taking into account the foes.
    def translate_counter_rs(self, counter_rs):
        ai_counter_rs = []
        counters = set()

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
                        counter_nums_h.append(self.hero_nums[(hero_name, role)])
                    counter_nums_f = []
                    for hero_name, role in zip(foe_names, roles_f):
                        counter_nums_f.append(self.hero_nums[(hero_name, role)])
                    counter_nums_h.sort()
                    counter_nums_f.sort()
                    valid.append((counter_nums_h, counter_nums_f))
            return valid

        for r in counter_rs:
            for heroes, foes in valid_counter_nums(r.heroes, r.foes):
                counter = (tuple(heroes), tuple(foes))
                if counter not in counters:
                    ai_counter_rs.append((heroes, foes, r.A_value, r.B_value))
                    counters.add(counter)
                else:
                    hero_names = [self.ordered_heroes[h].name for h in heroes]
                    foe_names = [self.ordered_heroes[h].name for h in foes]
                    raise ValueError(
                        f"Duplicate counter reward possible for {hero_names} vs {foe_names}"
                    )

        if len(ai_counter_rs) <= MAX_COUNTER_RS:
            return ai_counter_rs
        else:
            raise ValueError(f"Not enough memory for all AI counter rs")

    def get_heroes_per_role(self):
        heroes_per_role = [set() for _ in ROLES]
        for hero_num, hero in enumerate(self.ordered_heroes):
            heroes_per_role[hero.role].add(hero_num)
        return heroes_per_role

    # Returns a list where element n contains a list of all hero num
    # occurrences that refer to hero n, including itself. (Needed
    # for generating legal actions).
    def get_same_hero_refs(self):
        all_refs = []
        for hero in self.ordered_heroes:
            refs = set() 
            for role in ROLES:
                # will be true for at least one (its role)
                if (hero.name, role) in self.hero_nums:
                    refs.add(self.hero_nums[(hero.name, role)])
            all_refs.append(refs)
        return all_refs

    # Generates the random zobrist bitstrings for a hero being picked by
    # team A, picked by team B or being banned by either team. States can
    # then be uniquely identified with a single hash by taking the XOR of
    # the keys matching the combination of picked and banned heroes (see
    # wikipedia.org/wiki/Zobrist_hashing for more details).
    #
    # All hero nums that are role variations of the same underlying hero
    # are given the same key for bans because a ban of any is equivalent
    # (unlike picks, bans don't effect the open roles a team then has).
    def generate_zobrist_keys(self):
        used = set()

        def unique_key():
            key = random.getrandbits(ZOBRIST_BITS)
            while key in used:                          # single chance of getting duplicate is less
                key = random.getrandbits(ZOBRIST_BITS)  # than 1e-15%, but better safe than sorry
            return key

        # every hero num gets a unique key for picks
        pick_keys_A = [unique_key() for _ in range(len(self.ordered_heroes))]
        pick_keys_B = [unique_key() for _ in range(len(self.ordered_heroes))]

        # all hero role variations share same key for a ban
        name_key = {}
        ban_keys = []
        for hero in self.ordered_heroes:
            if hero.name in name_key:
                ban_keys.append(name_key[hero.name])
            else:
                key = unique_key()
                name_key[hero.name] = key
                ban_keys.append(key)

        return pick_keys_A, pick_keys_B, ban_keys

    # Saves the transposition table (and the zobrist keys used to represent
    # states inside the transposition table) to the specified file so that
    # it can be loaded for reuse at a later point. 
    def save_tt(self, filename):
        c_filename = ffi.new("char[]", filename.encode("ascii"))
        lib.write_tt_and_zobrist_keys(c_filename)

    # Load a transposition table (and the zobrist keys used to represent
    # states inside the transposition table) into memory, ready to be used
    # for running search.
    #
    # @Important: A TT is only valid if being used with the exact same
    # rewards that were used to populate it. There is currently no check for
    # this so it is up to the caller to ensure correctness.
    def load_tt(self, filename):
        c_filename = ffi.new("char[]", filename.encode("ascii"))
        lib.read_tt_and_zobrist_keys(c_filename)

    # Set the C global memory with all information required by the
    # engine for running searches on a new set of rewards/draft format.
    def _set_C_globals(self, synergy_rs, counter_rs):

        # role rewards
        for hero_num, hero in enumerate(self.ordered_heroes):
            lib.set_role_r(hero_num, hero.A_role_value, hero.B_role_value)

        # synergy rewards
        self.ai_synergy_rs = self.translate_synergy_rs(synergy_rs)
        for i, synergy_r in enumerate(self.ai_synergy_rs):
            heroes, A_value, B_value = synergy_r
            lib.set_synergy_r(i, len(heroes), heroes, A_value, B_value)

        # counter rewards
        self.ai_counter_rs = self.translate_counter_rs(counter_rs)
        for i, counter_r in enumerate(self.ai_counter_rs):
            heroes, foes, A_value, B_value = counter_r
            lib.set_counter_r(
                i,
                len(heroes),
                heroes,
                len(foes),
                foes,
                A_value,
                B_value,
            )

        # draft format
        for stage, (team, selection_type) in enumerate(self.draft_format):
            lib.set_draft_stage(stage, team, selection_type)

        # hero info for updating legal actions
        heroes_per_role = self.get_heroes_per_role()
        same_hero_refs = self.get_same_hero_refs()
        for hero_num, hero in enumerate(self.ordered_heroes):
            same_hero = same_hero_refs[hero_num]
            same_role_and_hero = list(heroes_per_role[hero.role] | same_hero)
            same_hero = list(same_hero)
            lib.set_h_info(
                hero_num,
                len(same_role_and_hero),
                same_role_and_hero,
                len(same_hero),
                same_hero,
            )

        # sizes
        lib.set_sizes(
            len(self.ordered_heroes),
            len(self.ai_synergy_rs),
            len(self.ai_counter_rs),
            len(self.draft_format),
        )

        # zobrist keys
        keys = self.generate_zobrist_keys()
        pick_keys_A, pick_keys_B, ban_keys = keys
        for h in range(len(self.ordered_heroes)):
            lib.set_zobrist_key(A, h, pick_keys_A[h])
            lib.set_zobrist_key(B, h, pick_keys_B[h])
            lib.set_zobrist_key(BAN_KEYS, h, ban_keys[h])

        lib.clear_tt()  # ensure state values for old drafts aren't used

    # Group all bans, team A selections and team B selections into
    # separate lists.
    def _split_history(self, history):
        banned = []
        team_A = []
        team_B = []
        for hero, (team, selection) in zip(history, self.draft_format):
            if selection in BANS:
                banned.append(hero)
            elif team == A:
                team_A.append(hero)
            else:
                team_B.append(hero)
        return banned, team_A, team_B

    # As flex picks map to a different hero num for every role they play,
    # there can be many possible 'teams'. All valid ones (no role clashes)
    # should be accounted for in search. This does not effect bans as the
    # same roles will be open, and all duplicates made illegal, no matter
    # which variation is selected.
    #
    # @Later an outer function can handle cases where selections made based
    # on the AI's suggestion can eliminate the other flex possibilities as
    # we know the intended role for maximum value.
    def get_picks_n_bans(self, history):
        banned_names, team_A_names, team_B_names = self._split_history(history)

        banned = []
        for hero_name in banned_names:
            for role in ROLES:
                if (hero_name, role) in self.hero_nums:
                    banned.append(self.hero_nums[(hero_name, role)])
                    break  # only one role variation needed for bans

        team_A_roles = [self.hero_roles[hero_name] for hero_name in team_A_names]
        team_B_roles = [self.hero_roles[hero_name] for hero_name in team_B_names]

        teams_A = []
        teams_B = []

        for roles_A in itertools.product(*team_A_roles):
            if len(set(roles_A)) != len(team_A_names):
                continue
            team_A = []
            for hero_name, role in zip(team_A_names, roles_A):
                team_A.append(self.hero_nums[(hero_name, role)])
            teams_A.append(team_A)

        for roles_B in itertools.product(*team_B_roles):
            if len(set(roles_B)) != len(team_B_names):
                continue
            team_B = []
            for hero_name, role in zip(team_B_names, roles_B):
                team_B.append(self.hero_nums[(hero_name, role)])
            teams_B.append(team_B)

        # ensure at least one team role assignment is possible
        error_msg = "Invalid history: no role assignements possible for team {}"
        if len(teams_A) == 0:
            raise ValueError(error_msg.format('A'))
        elif len(teams_B) == 0:
            raise ValueError(error_msg.format('B'))

        return teams_A, teams_B, banned

    def run_search(self, history):
        """
        Wrapper for the C run_search function. Prepares all inputs and
        returns the optimal value and action(s) for a given history.

        @Important: This function will only work if called on the most
                    recently instantiated DraftAI object. This is 
                    because they all share the same underlying C global
                    memory.
        """

        for hero in history:
            if hero not in self.hero_roles:
                raise ValueError(f"Invalid history: {hero} has no role reward")

        teams_A, teams_B, banned = self.get_picks_n_bans(history)

        def total_team_potential(team):
            return sum(self.ordered_heroes[h].potential for h in team)

        # sort teams from most likely to do well to least (achieves
        # maximum likelihood of cut offs during search)
        teams_A.sort(key=total_team_potential, reverse=True)
        teams_B.sort(key=total_team_potential, reverse=True)

        search_result = lib.run_search(
            len(teams_A),
            len(teams_B),
            len(teams_A[0]),  # all team variations will be same size
            len(teams_B[0]),
            len(banned),
            [ffi.new('int[]', team) for team in teams_A],
            [ffi.new('int[]', team) for team in teams_B],
            banned,
        )
        value = search_result.value
        best_hero = self.ordered_heroes[search_result.best_hero].name

        _, selection = self.draft_format[len(history)]
        if selection == PICK or selection == BAN:
            return value, best_hero
        else:
            best_hero_2 = self.ordered_heroes[search_result.best_hero_2].name
            return value, best_hero, best_hero_2

    # Turns a draft format where each stage is an indictor of the
    # selecting team and a selection type consisting of either a pick
    # or ban to one that further indicates if it is a double selection
    # of some kind.
    def get_ai_draft_format(self, draft_format):
        ai_draft_format = []
        for stage in range(len(draft_format)):
            team, selection = draft_format[stage]
            if stage + 1 < len(draft_format):
                next_team, next_selection = draft_format[stage + 1]
            else:
                next_team, next_selection = None, None

            # find new selection flag if current team has two in a row
            if team == next_team:
                if selection == PICK and next_selection == PICK:
                    selection = PICK_PICK
                elif selection == PICK and next_selection == BAN:
                    selection = PICK_BAN
                elif selection == BAN and next_selection == PICK:
                    selection = BAN_PICK
                elif selection == BAN and next_selection == BAN:
                    selection = BAN_BAN
                else:
                    assert False
            ai_draft_format.append((team, selection))
        return ai_draft_format

    def selectable_heroes(self, history, stage=None):
        """
        Returns the set of all hero names that can be selected at the
        given stage in the draft history. If no stage is provided it
        defaults to the next selection.

        To be selectable, heroes must not be present in the history
        and for picks there must also exist a valid role assignment
        between the hero and the rest of the selecting team.
        """

        stage = len(history) if stage is None else stage
        assert stage <= len(history)
        team, selection = self.draft_format[stage]
        selected = set()
        team_heroes = []
        for i in range(len(history)):
            if i == stage:
                continue  # ignore any current hero for deciding selectable
            selected.add(history[i])
            team_i, selection_i = self.draft_format[i]
            if team_i == team and selection_i in PICKS:
                team_heroes.append(history[i])

        if selection in BANS:
            selectable = set(self.hero_roles.keys()) - selected
        else:
            selectable = set()
            team_roles = [self.hero_roles[hero] for hero in team_heroes]
            for hero in self.hero_roles.keys():
                if hero in selected:
                    continue
                # check for a valid role assignment with hero and current team
                for roles in itertools.product(*team_roles, self.hero_roles[hero]):
                    if len(set(roles)) == len(team_heroes) + 1:
                        selectable.add(hero)
                        break
        return selectable

    # Returns a list of all role assignments based on what the heroes
    # can play and ensuring no clashes.
    def valid_role_asgmts(self, team_names):
        role_asgmts = []
        team_roles = [self.hero_roles[hero_name] for hero_name in team_names]
        for roles in itertools.product(*team_roles):
            if len(set(roles)) == len(team_names):
                role_asgmts.append(roles)
        return role_asgmts

    # Get hero nums for the given hero names playing in the given roles.
    def get_hero_nums(self, names, roles):
        nums = []
        for name_role in zip(names, roles):
            nums.append(self.hero_nums[name_role])
        return nums

    # To find the optimal role assignments a small minimax search is
    # done over both team's possible role assignments. The unexploitable
    # team choosese first and is set to the MAX player. Thus, the
    # returned assignments is whichever assignement gets MAX the most
    # value given MIN's best response.
    def optimal_role_asgmts(self, history, unexploitable):
        """
        Returns the optimal role assignments for the heroes of each team
        at the given point in history. The unexploitable argument is
        used to resolve situations where the value doesn't converge. It
        indicates the team who should receive the role assignment
        that results in their best guaranteed value even if more would be
        possible vs the enemy assignment if they were willing to leave
        themselves open to counter exploitation.
        """

        _, team_A_names, team_B_names = self._split_history(history)
        if unexploitable == A:
            names_max = team_A_names
            names_min = team_B_names
        else:
            names_max = team_B_names
            names_min = team_A_names

        value_max = -INF
        for roles_max in self.valid_role_asgmts(names_max):
            team_nums_max = self.get_hero_nums(names_max, roles_max)

            value_min = INF
            for roles_min in self.valid_role_asgmts(names_min):
                team_nums_min = self.get_hero_nums(names_min, roles_min)

                # get value in terms of MAX's perspective
                if unexploitable == A:
                    value = self.reward_value(team_nums_max, team_nums_min)
                else:
                    value = -self.reward_value(team_nums_min, team_nums_max)

                if value < value_min:
                    value_min = value
                    _opt_roles_min = roles_min

            if value_min > value_max:
                value_max = value_min
                opt_roles_max = roles_max
                opt_roles_min = _opt_roles_min

        opt_asgmt_max = list(zip(names_max, opt_roles_max))
        opt_asgmt_min = list(zip(names_min, opt_roles_min))
        if unexploitable == A:
            return opt_asgmt_max, opt_asgmt_min
        else:
            return opt_asgmt_min, opt_asgmt_max

    # Return the zero-sum value in team A's perspective for all granted
    # role, synergy and counter rewards for the given team hero nums.
    def reward_value(self, team_A, team_B):
        value = 0
        team_A = set(team_A)
        team_B = set(team_B)

        # role rewards
        for h in team_A:
            value += self.ordered_heroes[h].A_role_value
        for h in team_B:
            value -= self.ordered_heroes[h].B_role_value

        # synergy rewards
        for synergy_hs, A_value, B_value in self.ai_synergy_rs:
            if all(map(lambda h: h in team_A, synergy_hs)):
                value += A_value
            elif all(map(lambda h: h in team_B, synergy_hs)):
                value -= B_value

        # counter rewards
        for counter_hs, counter_fs, A_value, B_value in self.ai_counter_rs:
            if (all(map(lambda h: h in team_A, counter_hs))
                    and all(map(lambda f: f in team_B, counter_fs))):
                value += A_value
            elif (all(map(lambda h: h in team_B, counter_hs))
                    and all(map(lambda f: f in team_A, counter_fs))):
                value -= B_value

        return value

    # Return the total number of unique possible drafts from the given history
    # for the instantiated draft format and heroes used in the role rewards.
    def num_unique_drafts(self, history):
        available_heroes = len(self.hero_roles) - len(history)
        num_remaining_selections = len(self.draft_format) - len(history)
        drafts = 1
        for i in range(num_remaining_selections):
            drafts *= (available_heroes - i)
        return drafts
