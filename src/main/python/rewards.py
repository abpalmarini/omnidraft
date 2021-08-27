from operator import itemgetter
from collections import namedtuple

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

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


class RoleRewardsModel(QAbstractTableModel):

    def __init__(self, all_heroes, team_1_tag, team_2_tag):
        super().__init__()

        self.headers = ("Hero", "Role", team_1_tag, team_2_tag)
        self.hero_roles = {hero: set() for hero in all_heroes}
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

    def contains_filter(self, reward):
        return self.current_filter in reward.name.lower()

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

    def add_reward(self, name, role, team_1_value, team_2_value):
        reward = RoleReward(name, role, team_1_value, team_2_value)
        self.hero_roles[name].add(role)

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
                self.hero_roles[reward.name].remove(reward.role)
            else:
                rewards.append(reward)
        self.rewards = rewards

        self.layoutAboutToBeChanged.emit()
        self.view_rewards = [r for r in self.rewards if self.contains_filter(r)]
        self.layoutChanged.emit()


# A synergy consists of a group of heroes each with a list of applicable
# roles they could be in.
SynergyHero = namedtuple('SynergyHero', ['name', 'roles'])


class SynergyReward:

    def __init__(self, heroes, team_1_value, team_2_value):
        self.heroes = heroes
        self.team_1_value = team_1_value
        self.team_2_value = team_2_value

    # convient way to get data for each column in table
    def __getitem__(self, index):
        if index < len(self.heroes):
            return self.heroes[index].name
        elif index < 5:
            return None
        elif index == 5:
            return self.team_1_value
        elif index == 6:
            return self.team_2_value
        else:
            raise IndexError


class SynergyRewardsModel(QAbstractTableModel):

    def __init__(self, team_1_tag, team_2_tag):
        super().__init__()

        self.headers = ("Heroes", team_1_tag, team_2_tag)
        self.all_combos = set()
        self.rewards = []
        self.view_rewards = []
        self.current_sort = (None, None)
        self.current_filter = ""

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return
        if orientation == Qt.Horizontal:
            if section < 5: return  # first 5 are all for synergy heroes
            tag = section - 4
            return self.headers[tag]
        else:
            return str(section + 1)

    def rowCount(self, parent=QModelIndex()):
        return len(self.view_rewards) if not parent.isValid() else 0

    def columnCount(self, parent=QModelIndex()):
        return 7 if not parent.isValid() else 0  # 5 for possible heroes and 2 for each tag

    def data(self, index, role=Qt.DisplayRole):
        reward = self.view_rewards[index.row()]
        if role == Qt.DisplayRole:
            return reward[index.column()]

    def sort(self, column, order=Qt.AscendingOrder):
        # only allow sorting of team values
        if column < 5: return 
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

    # Give users ability to enter multiple hero names separated with a
    # space. For a reward to contain the filter all parts must be part
    # of any hero name.
    def contains_filter(self, reward):
        filters = self.current_filter.split()

        def filter_in_any_name(text):
            for hero in reward.heroes:
                if text in hero.name.lower():
                    return True
            return False

        return all(map(filter_in_any_name, filters))

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
