from operator import itemgetter

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

        self.data_fields = ("Hero", "Role", team_1_tag, team_2_tag)
        self.hero_roles = {hero: set() for hero in all_heroes}
        self.rewards = []
        self.view_rewards = []
        self.current_sort = (None, None)
        self.current_filter = ""

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return
        if orientation == Qt.Horizontal:
            return self.data_fields[section]
        else:
            return str(section + 1)

    def rowCount(self, parent=QModelIndex()):
        return len(self.view_rewards) if not parent.isValid() else 0

    def columnCount(self, parent=QModelIndex()):
        return len(self.data_fields) if not parent.isValid() else 0

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
        pass
