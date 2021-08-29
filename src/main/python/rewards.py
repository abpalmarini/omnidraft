from operator import itemgetter
from collections import namedtuple
import itertools

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


class BaseRewardsModel(QAbstractTableModel):

    def __init__(self):
        super().__init__()

        self.rewards = []
        self.view_rewards = []
        self.current_sort = (None, None)
        self.current_filter = ""

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
        if role == Qt.DisplayRole:
            return reward[index.column()]

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


class RoleReward:

    def __init__(self, name, role, team_1_value, team_2_value):
        self.name = name
        self.role = role
        self.team_1_value = team_1_value
        self.team_2_value = team_2_value

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

    def __init__(self, all_heroes, team_1_tag, team_2_tag):
        super().__init__()

        self.headers = ("Hero", "Role", team_1_tag, team_2_tag)
        self.hero_roles = {hero: set() for hero in all_heroes}

    def contains_filter(self, reward):
        return self.current_filter in reward.name.lower()

    def update_extra_state(self, reward, add=True):
        if add:
            self.hero_roles[reward.name].add(reward.role)
        else:
            self.hero_roles[reward.name].remove(reward.role)


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
        self.hero_role_asgmts = set()
        names, roles = zip(*self.heroes)
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

    def __init__(self, team_1_tag, team_2_tag):
        super().__init__()

        self.headers = tuple(None for _ in range(5)) + (team_1_tag, team_2_tag)
        self.hero_role_combos = set()

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
        if column >= 5:
            BaseRewardsModel.sort(self, column, order)

    def update_extra_state(self, reward, add=True):
        if add:
            self.hero_role_combos |= reward.hero_role_asgmts
        else:
            self.hero_role_combos -= reward.hero_role_asgmts

    # Returns a list of all synergy rewards using a role reward.
    def uses_role_reward(self, name, role):
        name_role = (name, role)
        return [r for r in self.rewards if name_role in r.used_role_rs]
