import itertools
from operator import itemgetter

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QFont


# Flags for the status of a reward based on teams in the team builder.
TEAM_1  = 1
TEAM_2  = 2
NO_TEAM = 3


class BaseRewardsModel(QAbstractTableModel):

    def __init__(self):
        super().__init__()

        self.rewards = []
        self.view_rewards = []
        self.current_sort = (None, None)
        self.current_filter = ""

        # heroes selected for each team in the team builder
        self.team_1 = []
        self.team_2 = []

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return
        if orientation == Qt.Horizontal:
            return self.headers[section]
        else:
            return str(section + 1)

    def rowCount(self, parent=QModelIndex()):
        return len(self.view_rewards) if not parent.isValid() else 0

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers) if not parent.isValid() else 0

    def data(self, index, role=Qt.DisplayRole):
        reward = self.view_rewards[index.row()]
        column = index.column()
        if role == Qt.DisplayRole:
            return reward[column]
        elif role == Qt.BackgroundRole:
            # highlight rewards based on status in team builder
            if reward.status == TEAM_1:
                return QColor(0, 0, 255, 127)
            elif reward.status == TEAM_2:
                return QColor(255, 0, 0, 127)
        elif role == Qt.FontRole:
            # return bold value if reward is granted for either team
            font = QFont()
            team_1_v_column = len(self.headers) - 2
            team_2_v_column = len(self.headers) - 1
            if column == team_1_v_column and reward.status == TEAM_1:
                font.setBold(True)
            if column == team_2_v_column and reward.status == TEAM_2:
                font.setBold(True)
            return font
        elif role == Qt.UserRole:
            return reward

    # Full set of rewards are sorted (rather than just those in view) so
    # that applying a new filter does not require a re-sort each time.
    def sort(self, column, order=Qt.AscendingOrder):
        self.current_sort = (column, order)
        if order == Qt.AscendingOrder:
            self.rewards.sort(key=itemgetter(column))
        else:
            self.rewards.sort(key=itemgetter(column), reverse=True)
        self.layoutAboutToBeChanged.emit()
        if not self.current_filter:
            self.view_rewards = list(self.rewards)
        else:
            self.view_rewards = [r for r in self.rewards if self.contains_filter(r)]
        self.layoutChanged.emit()

    def filter_rewards(self, text):
        prev_filter = self.current_filter
        self.current_filter = text.lower()
        self.layoutAboutToBeChanged.emit()
        if not self.current_filter:
            self.view_rewards = list(self.rewards)
        elif self.current_filter.startswith(prev_filter):
            # new view rewards will be subset of old
            self.view_rewards = [r for r in self.view_rewards if self.contains_filter(r)]
        else:
            self.view_rewards = [r for r in self.rewards if self.contains_filter(r)]
        self.layoutChanged.emit()

    def add_reward(self, reward):
        # hook for specific reward types to update helper data structures
        self.update_extra_state(reward, add=True)

        reward.update_status(self.team_1, self.team_2)

        # place in correct sorted position
        sort_column, sort_order = self.current_sort
        pos = 0
        if sort_order == Qt.AscendingOrder:
            while pos < len(self.rewards):
                if reward[sort_column] < self.rewards[pos][sort_column]:
                    break
                pos += 1
        else:
            while pos < len(self.rewards):
                if reward[sort_column] > self.rewards[pos][sort_column]:
                    break
                pos += 1
        self.rewards.insert(pos, reward)

        # update view rewards if necessary
        if self.contains_filter(reward):
            self.layoutAboutToBeChanged.emit()
            self.view_rewards = [r for r in self.rewards if self.contains_filter(r)]
            self.layoutChanged.emit()

    # Delete a single reward given the reward object.
    def delete_reward(self, reward):
        self.update_extra_state(reward, add=False)
        self.rewards.remove(reward)
        if self.contains_filter(reward): 
            self.layoutAboutToBeChanged.emit()
            self.view_rewards.remove(reward)
            self.layoutChanged.emit()

    # Deletes rewards from a list of indexes while maintaining sorted order.
    def delete_rewards(self, indexes):
        # indices correspond to the rewards in view
        del_rewards = {self.view_rewards[index.row()] for index in indexes}
        rewards = []
        for reward in self.rewards:
            if reward in del_rewards:
                self.update_extra_state(reward, add=False)
            else:
                rewards.append(reward)
        self.rewards = rewards

        self.layoutAboutToBeChanged.emit()
        self.view_rewards = [r for r in self.rewards if self.contains_filter(r)]
        self.layoutChanged.emit()

    # To be called whenever the teams in the team builder change, so
    # that rewards being granted can be highlighted.
    def update_reward_statuses(self, team_1, team_2):
        team_1.sort(key=itemgetter(0))  # sort first to ensure it matches any
        team_2.sort(key=itemgetter(0))  # synergy/counter combinations
        self.team_1 = team_1
        self.team_2 = team_2
        self.layoutAboutToBeChanged.emit()
        for reward in self.rewards:
            reward.update_status(team_1, team_2)
        self.layoutChanged.emit()


class RoleReward:

    def __init__(self, name, role, team_1_value, team_2_value):
        self.name = name
        self.role = role
        self.team_1_value = team_1_value
        self.team_2_value = team_2_value

    def update_status(self, team_1, team_2):
        if (self.name, self.role) in team_1:
            self.status = TEAM_1
        elif (self.name, self.role) in team_2:
            self.status = TEAM_2
        else:
            self.status = NO_TEAM

    def __getitem__(self, index):
        if index == 0:
            return self.name
        elif index == 1:
            return self.role
        elif index == 2:
            return self.team_1_value
        elif index == 3:
            return self.team_2_value
        else:
            raise IndexError


class RoleRewardsModel(BaseRewardsModel):

    def __init__(self, all_heroes, team_tags):
        super().__init__()

        self.headers = (None, None, team_tags[0], team_tags[1])
        self.hero_roles = {hero: set() for hero in all_heroes}

    def contains_filter(self, reward):
        return self.current_filter in reward.name.lower()

    def update_extra_state(self, reward, add=True):
        if add:
            self.hero_roles[reward.name].add(reward.role)
        else:
            self.hero_roles[reward.name].remove(reward.role)

    def get_hero_roles(self, hero_name):
        return self.hero_roles[hero_name]


class SynergyReward:

    # heroes expected to be dict of names and their applicable roles
    def __init__(self, heroes, team_1_value, team_2_value):
        self.heroes = list(heroes.items())
        self.heroes.sort(key=itemgetter(0))  # ensure same role assignments produced for duplicates
        self.team_1_value = team_1_value
        self.team_2_value = team_2_value
        self.init_hero_role_asgmts()
        self.init_used_role_rs()

    def init_hero_role_asgmts(self):
        names, roles = zip(*self.heroes)
        self.hero_names = names
        self.hero_role_asgmts = set()
        for role_asgmt in itertools.product(*roles):
            # find all role assignments with no clashes
            if len(set(role_asgmt)) == len(self.heroes):
                asgmt = tuple(zip(names, role_asgmt))
                self.hero_role_asgmts.add(asgmt)

    # used role rewards tracked to ensure safe deleting
    def init_used_role_rs(self):
        self.used_role_rs = set()
        for hero_role_asgmt in self.hero_role_asgmts:
            for name_role in hero_role_asgmt:
                self.used_role_rs.add(name_role)

    def update_status(self, team_1, team_2):
        # get heroes (name and role) in each team that are part of synergy
        team_1_h = tuple(hero for hero in team_1 if hero[0] in self.hero_names)
        team_2_h = tuple(hero for hero in team_2 if hero[0] in self.hero_names)

        # check if a team contains all synergy heroes in an applicable role
        if team_1_h in self.hero_role_asgmts:
            self.status = TEAM_1
        elif team_2_h in self.hero_role_asgmts:
            self.status = TEAM_2
        else:
            self.status = NO_TEAM

    def __getitem__(self, index):
        if index < len(self.heroes):
            return self.heroes[index][0]
        elif index < 5:
            return None
        elif index == 5:
            return self.team_1_value
        elif index == 6:
            return self.team_2_value
        else:
            raise IndexError


class SynergyRewardsModel(BaseRewardsModel):

    def __init__(self, team_tags):
        super().__init__()

        self.headers = tuple(None for _ in range(5)) + (team_tags[0], team_tags[1])
        self.hero_role_asgmts = set()

    # Give users ability to enter multiple hero names separated with a
    # space. For a reward to contain the filter all parts must be part
    # of any hero name.
    def contains_filter(self, reward):
        filters = self.current_filter.split()

        def filter_in_any_name(text):
            for hero in reward.heroes:
                if text in hero[0].lower():
                    return True
            return False

        return all(map(filter_in_any_name, filters))

    def sort(self, column, order=Qt.AscendingOrder):
        # only allow sorting of team values
        if column >= len(self.headers) - 2:
            BaseRewardsModel.sort(self, column, order)

    def update_extra_state(self, reward, add=True):
        if add:
            self.hero_role_asgmts |= reward.hero_role_asgmts
        else:
            self.hero_role_asgmts -= reward.hero_role_asgmts

    # Returns a list of all synergy rewards using a role reward.
    def uses_role_reward(self, role_reward):
        name_role = (role_reward.name, role_reward.role)
        return [r for r in self.rewards if name_role in r.used_role_rs]


class CounterReward:

    def __init__(self, heroes, foes, team_1_value, team_2_value):
        self.heroes = list(heroes.items())
        self.heroes.sort(key=itemgetter(0))
        self.foes = tuple(sorted(foes))
        self.team_1_value = team_1_value
        self.team_2_value = team_2_value
        self.init_hero_role_asgmts()
        self.init_used_role_rs()

    def init_hero_role_asgmts(self):
        names, roles = zip(*self.heroes)
        self.hero_names = names
        self.hero_role_asgmts = set()
        for role_asgmt in itertools.product(*roles):
            if len(set(role_asgmt)) == len(self.heroes):
                asgmt = tuple(zip(names, role_asgmt))
                self.hero_role_asgmts.add((asgmt, self.foes))  # counters must store foes as well

    def init_used_role_rs(self):
        self.used_role_rs = set()
        for hero_role_asgmt, _ in self.hero_role_asgmts:
            for name_role in hero_role_asgmt:
                self.used_role_rs.add(name_role)

    # To check if a counter is granted one team must have all heroes
    # in an applicable role and the other team must contain all foes.
    def update_status(self, team_1, team_2):
        team_1_h = tuple(hero for hero in team_1 if hero[0] in self.hero_names)
        team_2_h = tuple(hero for hero in team_2 if hero[0] in self.hero_names)
        team_1_f = tuple(hero[0] for hero in team_1 if hero[0] in self.foes)
        team_2_f = tuple(hero[0] for hero in team_2 if hero[0] in self.foes)
        if (team_1_h, team_2_f) in self.hero_role_asgmts:
            self.status = TEAM_1
        elif (team_2_h, team_1_f) in self.hero_role_asgmts:
            self.status = TEAM_2
        else:
            self.status = NO_TEAM

    # First 5 indices correspond to team heroes, 6th index is a separator,
    # next 5 indices are foe heroes, then final 2 are team values.
    def __getitem__(self, index):
        if index < len(self.heroes):
            return self.heroes[index][0]
        elif index < 5:
            return None
        elif index == 5:  # separator gap between team heroes and foes
            return ">"
        elif index < 6 + len(self.foes):
            return self.foes[index - 6]
        elif index < 11:
            return None
        elif index == 11:
            return self.team_1_value
        elif index == 12:
            return self.team_2_value
        else:
            raise IndexError


class CounterRewardsModel(BaseRewardsModel):

    def __init__(self, team_tags):
        super().__init__()

        self.headers = tuple(None for _ in range(11)) + (team_tags[0], team_tags[1])
        self.hero_role_asgmts = set()

    def contains_filter(self, reward):
        filters = self.current_filter.split()

        def filter_in_any_name(text):
            for hero in reward.heroes:
                if text in hero[0].lower():
                    return True
            for name in reward.foes:
                if text in name.lower():
                    return True
            return False

        return all(map(filter_in_any_name, filters))

    def sort(self, column, order=Qt.AscendingOrder):
        # only allow sorting of team values
        if column >= len(self.headers) - 2:
            BaseRewardsModel.sort(self, column, order)

    def update_extra_state(self, reward, add=True):
        if add:
            self.hero_role_asgmts |= reward.hero_role_asgmts
        else:
            self.hero_role_asgmts -= reward.hero_role_asgmts

    # Returns both a list of counter rewards using the specific role
    # reward as part of the team heroes, and a list of counter rewards
    # where the hero is used as part of foes.
    def uses_role_reward(self, role_reward):
        name_role = (role_reward.name, role_reward.role)
        used_in_team = [r for r in self.rewards if name_role in r.used_role_rs]
        used_in_foes = [r for r in self.rewards if role_reward.name in r.foes]
        return used_in_team, used_in_foes
