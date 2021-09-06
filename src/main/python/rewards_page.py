from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (QWidget, QTableView, QAbstractItemView, QLineEdit,
                               QPushButton, QGridLayout)

from collections import namedtuple

from reward_models import RoleRewardsModel, SynergyRewardsModel, CounterRewardsModel
from reward_dialogs import RoleRewardDialog, SynergyRewardDialog, CounterRewardDialog


RewardType = namedtuple('RewardCollection', ['model', 'view', 'dialog'])


class RewardsPage(QWidget):

    def __init__(self, hero_icons, team_tags):
        super().__init__()

        self.reward_types = []

        # role reward
        role_model = RoleRewardsModel(list(hero_icons.keys()), team_tags)
        role_view = self.init_reward_view(role_model)
        role_dialog = RoleRewardDialog(role_model, hero_icons, team_tags, self)
        self.reward_types.append(RewardType(role_model, role_view, role_dialog))

        # synergy reward
        synergy_model = SynergyRewardsModel(team_tags)
        synergy_view = self.init_reward_view(synergy_model)
        synergy_dialog = SynergyRewardDialog(role_model.hero_roles, synergy_model,
                                             hero_icons, team_tags, self)
        self.reward_types.append(RewardType(synergy_model, synergy_view, synergy_dialog))

        # counter reward
        counter_model = CounterRewardsModel(team_tags)
        counter_view = self.init_reward_view(counter_model)
        counter_dialog = CounterRewardDialog(role_model.hero_roles, counter_model,
                                             hero_icons, team_tags, self)
        self.reward_types.append(RewardType(counter_model, counter_view, counter_dialog))

        # search filter
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search...")
        for reward_type in self.reward_types:
            search_bar.textChanged.connect(reward_type.model.filter_rewards)

        # add reward buttons
        add_role_button = self.init_add_button('Role', role_dialog)
        add_synergy_button = self.init_add_button('Synergy', synergy_dialog)
        add_counter_button = self.init_add_button('Counter', counter_dialog)

        # enable editing
        for reward_type in self.reward_types:
            reward_type.view.doubleClicked.connect(self.open_editting)

        # delete button
        delete_button = QPushButton("Delete Selected Rewards")
        delete_button.clicked.connect(self.delete_clicked)

        # layout
        layout = QGridLayout(self)
        layout.addWidget(search_bar, 0, 0, 1, 2)
        layout.addWidget(delete_button, 0, 2)
        layout.addWidget(add_role_button, 1, 0)
        layout.addWidget(add_synergy_button, 1, 1)
        layout.addWidget(add_counter_button, 1, 2)
        layout.addWidget(role_view, 2, 0)
        layout.addWidget(synergy_view, 2, 1)
        layout.addWidget(counter_view, 2, 2)

    def init_reward_view(self, reward_model):
        table_view = QTableView()
        table_view.setModel(reward_model)

        table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        # have each view initially sorted in descending team 1 value
        team_1_value_column = reward_model.columnCount() - 2
        table_view.sortByColumn(team_1_value_column, Qt.DescendingOrder)
        table_view.setSortingEnabled(True)

        return table_view

    def init_add_button(self, reward_name, reward_dialog):
        add_button = QPushButton(f"Add {reward_name} Reward")
        add_button.clicked.connect(reward_dialog.open_add)
        return add_button

    @Slot()
    def open_editting(self, reward_index):
        for reward_type in self.reward_types:
            if reward_type.model == reward_index.model():
                reward_type.dialog.open_edit(reward_index)
                reward_type.view.clearSelection()
                break

    @Slot()
    def delete_clicked(self):
        for reward_type in self.reward_types:
            if reward_type.view.hasFocus():
                selection_model = reward_type.view.selectionModel()
                reward_indexes = selection_model.selectedRows()
                if reward_type == self.reward_types[0]:
                    # deleting a role reward requires the synergy and counter model
                    ret = reward_type.dialog.open_delete(
                        reward_indexes,
                        self.reward_types[1].model,
                        self.reward_types[2].model,
                    )
                else:
                    ret = reward_type.dialog.open_delete(reward_indexes)
                if ret:
                    reward_type.view.clearSelection()
                break
