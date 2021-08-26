from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

class RoleReward:

    def __init__(self, hero_name, role, team_1_value, team_2_value):
        self.hero_name = hero_name
        self.role = role
        self.team_1_value = team_1_value
        self.team_2_value = team_2_value

    def __getitem__(self, index):
        if index == 0:
            return self.hero_name
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
        self.display_rewards = []

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return
        if orientation == Qt.Horizontal:
            return self.data_fields[section]
        else:
            return str(section)

    def rowCount(self, parent=QModelIndex()):
        return len(self.display_rewards) if not parent.isValid() else 0

    def columnCount(self, parent=QModelIndex()):
        return len(self.data_fields) if not parent.isValid() else 0

    def data(self, index, role=Qt.DisplayRole):
        reward = self.display_rewards[index.row()]
        if role == Qt.DisplayRole:
            return reward[index.column()]
