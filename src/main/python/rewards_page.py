from PySide6.QtCore import Qt, Slot, QSize
from PySide6.QtWidgets import (QWidget, QTableView, QAbstractItemView, QLineEdit,
                               QPushButton, QGridLayout, QStyledItemDelegate,
                               QSizePolicy, QHBoxLayout, QHeaderView)

from collections import namedtuple

from reward_models import RoleRewardsModel, SynergyRewardsModel, CounterRewardsModel
from reward_dialogs import RoleRewardDialog, SynergyRewardDialog, CounterRewardDialog


REWARD_ICON_SIZE = QSize(50, 50)


RewardType = namedtuple('RewardCollection', ['model', 'view', 'dialog'])


class RewardIconDelegate(QStyledItemDelegate):

    def __init__(self, hero_icons):
        super().__init__()

        self.hero_icons = hero_icons

    def sizeHint(self, option, index):
        return REWARD_ICON_SIZE

    def paint(self, painter, option, index):
        hero = index.model().data(index)
        if not hero:
            super().paint(painter, option, index)
        else:
            icon = self.hero_icons[hero]
            icon.paint(painter, option.rect)


class RewardsPage(QWidget):

    def __init__(self, hero_icons, team_tags):
        super().__init__()

        self.reward_types = []
        self.icon_delegate = RewardIconDelegate(hero_icons)

        # role reward
        role_model = RoleRewardsModel(list(hero_icons.keys()), team_tags)
        role_view = self.init_reward_view(role_model, [0])
        role_dialog = RoleRewardDialog(role_model, hero_icons, team_tags, self)
        self.reward_types.append(RewardType(role_model, role_view, role_dialog))

        # synergy reward
        synergy_model = SynergyRewardsModel(team_tags)
        synergy_view = self.init_reward_view(synergy_model, list(range(5)))
        synergy_dialog = SynergyRewardDialog(role_model.hero_roles, synergy_model,
                                             hero_icons, team_tags, self)
        self.reward_types.append(RewardType(synergy_model, synergy_view, synergy_dialog))

        # counter reward
        counter_model = CounterRewardsModel(team_tags)
        counter_view = self.init_reward_view(counter_model, list(range(10)))
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

        # @Temp: dummy team builder widget to occupy all remaining space
        team_builder = QWidget()
        team_builder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # layout
        layout = QGridLayout(self)
        search_delete_layout = QHBoxLayout()
        search_delete_layout.addWidget(search_bar)
        search_delete_layout.addWidget(delete_button)
        layout.addLayout(search_delete_layout, 0, 0, 1, 3)
        layout.addWidget(add_role_button, 1, 0)
        layout.addWidget(add_synergy_button, 1, 1)
        layout.addWidget(add_counter_button, 1, 2)
        layout.addWidget(role_view, 2, 0)
        layout.addWidget(synergy_view, 2, 1)
        layout.addWidget(counter_view, 2, 2)
        layout.addWidget(team_builder, 0, 3, 3, 1)

    def init_reward_view(self, reward_model, icon_columns):
        table_view = QTableView()
        table_view.setModel(reward_model)

        table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        # have each view initially sorted in descending team 1 value
        team_1_value_column = reward_model.columnCount() - 2
        table_view.sortByColumn(team_1_value_column, Qt.DescendingOrder)
        table_view.setSortingEnabled(True)

        # adjusting team value columns to size, but @Later want to give same
        table_view.resizeColumnsToContents()

        # resize hero cells to icon size and have custom delegate paint them
        vertical_header = table_view.verticalHeader()
        vertical_header.setDefaultSectionSize(REWARD_ICON_SIZE.height())
        vertical_header.hide()
        for column in icon_columns:
            table_view.setColumnWidth(column, REWARD_ICON_SIZE.width())
            table_view.setItemDelegateForColumn(column, self.icon_delegate)

        # have table view occupy exact horizontal space with no adjusting
        horizontal_header = table_view.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.Fixed)
        table_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table_view.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        table_view.setFixedWidth(horizontal_header.length())

        return table_view

    def init_add_button(self, reward_name, reward_dialog):
        add_button = QPushButton(f"Add {reward_name} Reward")
        add_button.clicked.connect(reward_dialog.open_add)
        return add_button

    @Slot()
    def open_editting(self, reward_index):
        for reward_type in self.reward_types:
            if reward_type.model == reward_index.model():
                if reward_type == self.reward_types[0]:
                    # editing a role reward requires the synergy and counter model
                    reward_type.dialog.open_edit(
                        reward_index,
                        self.reward_types[1].model,
                        self.reward_types[2].model,
                    )
                else:
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
