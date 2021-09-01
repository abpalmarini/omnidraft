from PySide6.QtCore import QSortFilterProxyModel, Slot, Qt, QSize
from PySide6.QtWidgets import (QDialog, QAbstractItemView, QListView, QLineEdit,
                               QVBoxLayout, QLabel, QComboBox, QGridLayout,
                               QDoubleSpinBox, QDialogButtonBox)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from reward_models import RoleReward


SEARCH_ICON_SIZE = QSize(64, 64)

roles = ("Top Laner", "Jungler", "Mid Laner", "Bot Laner", "Support")


def init_value_spinbox():
    v_spinbox = QDoubleSpinBox()
    v_spinbox.setMaximum(10.00)
    return v_spinbox


class RoleRewardDialog(QDialog):

    def __init__(self, reward_model, hero_icons, team_tags, parent):
        super().__init__(parent)

        self.reward_model = reward_model
        self.hero_icons = hero_icons
        self.edit_reward = None

        self.hero_label = QLabel("Champion:") 
        self.hero = QLabel()  # default label for now, need to make custom picture after

        self.role_label = QLabel("Role:")
        self.role_combobox = QComboBox()
        self.role_combobox.addItems(roles)
        self.update_role_combobox()

        self.v_1_label = QLabel(team_tags[0] + " value:")
        self.v_2_label = QLabel(team_tags[1] + " value:")
        self.v_1_spinbox = init_value_spinbox()
        self.v_2_spinbox = init_value_spinbox()

        self.setup_hero_search()

        dialog_buttonbox = QDialogButtonBox(QDialogButtonBox.Save |
                                            QDialogButtonBox.Cancel)
        dialog_buttonbox.accepted.connect(self.accept)
        dialog_buttonbox.rejected.connect(self.reject)

        self.layout = QGridLayout(self)
        self.layout.addWidget(self.hero_label, 0, 0)
        self.layout.addWidget(self.hero, 0, 1)
        self.layout.addWidget(self.role_label, 1, 0)
        self.layout.addWidget(self.role_combobox, 1, 1)
        self.layout.addWidget(self.v_1_label, 2, 0)
        self.layout.addWidget(self.v_1_spinbox, 2, 1)
        self.layout.addWidget(self.v_2_label, 3, 0)
        self.layout.addWidget(self.v_2_spinbox, 3, 1)
        self.layout.addLayout(self.hero_search_layout, 4, 0, 1, 2)
        self.layout.addWidget(dialog_buttonbox, 5, 0, 1, 2)

    def setup_hero_search(self):
        # source model
        self.hero_model = QStandardItemModel(len(self.hero_icons), 1)
        for i, hero_name in enumerate(self.hero_icons):
            item = QStandardItem(self.hero_icons[hero_name], hero_name)
            self.hero_model.setItem(i, item)

        # filter model
        self.hero_f_model = QSortFilterProxyModel()
        self.hero_f_model.setSourceModel(self.hero_model)
        self.hero_f_model.setFilterCaseSensitivity(Qt.CaseInsensitive)

        # list view
        self.hero_view = QListView()
        self.hero_view.setModel(self.hero_f_model)
        self.hero_view.setViewMode(QListView.IconMode)
        self.hero_view.setIconSize(SEARCH_ICON_SIZE)
        self.hero_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.hero_view.setMovement(QListView.Static)
        self.hero_view.setUniformItemSizes(True)
        self.hero_view.clicked.connect(self.hero_selected)

        # search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.textChanged.connect(self.hero_f_model.setFilterRegularExpression)

        # hero search layout
        self.hero_search_layout = QVBoxLayout()
        self.hero_search_layout.addWidget(self.search_bar)
        self.hero_search_layout.addWidget(self.hero_view)

    def update_role_combobox(self):
        hero_name = self.hero.text()
        self.role_combobox.setCurrentIndex(-1)
        combobox_model = self.role_combobox.model()
        if not hero_name:
            # disable all selections
            for i in range(len(roles)):
                combobox_model.item(i).setEnabled(False)
        else:
            # ensure duplicates can not be created
            used_roles = self.reward_model.get_hero_roles(hero_name)
            for i, role in enumerate(roles):
                combobox_model.item(i).setEnabled(role not in used_roles)

    def clear_inputs(self):
        self.hero.clear()
        self.update_role_combobox()
        self.v_1_spinbox.setValue(0.00)
        self.v_2_spinbox.setValue(0.00)
        self.search_bar.clear()
        self.hero_view.clearSelection()

    def set_inputs(self, reward):
        self.hero.setText(reward.name)
        self.update_role_combobox()
        self.role_combobox.setCurrentText(reward.role)
        self.v_1_spinbox.setValue(reward.team_1_value)
        self.v_2_spinbox.setValue(reward.team_2_value)
        self.hero_view.clearSelection()

    @Slot()
    def hero_selected(self, f_index):
        index = self.hero_f_model.mapToSource(f_index)
        hero_name = self.hero_model.itemFromIndex(index).text()
        self.hero.setText(hero_name)
        self.update_role_combobox()

    def open_add(self):
        self.edit_reward = None
        self.clear_inputs()
        QDialog.open(self)
        self.search_bar.setFocus(Qt.PopupFocusReason)

    # For editing the reward is deleted from model first to allow for
    # same logic when creating a new reward. The original reward is
    # saved so it can be added back if the dialog is rejected.
    def open_edit(self, reward_index):
        self.edit_reward = self.reward_model.data(reward_index, Qt.UserRole)
        self.reward_model.delete_rewards([reward_index])
        self.set_inputs(self.edit_reward)
        QDialog.open(self)
        self.search_bar.setFocus(Qt.PopupFocusReason)

    # Create role reward and add to model if everything has been input
    # before closing the dialog.
    @Slot()
    def accept(self):
        # only check needed as duplicate roles are disabled for each hero
        # and a hero must be selected before you can select a role
        if self.role_combobox.currentIndex() == -1:
            return
        hero_name = self.hero.text()
        role = self.role_combobox.currentText()
        team_1_value = self.v_1_spinbox.value()
        team_2_value = self.v_2_spinbox.value()
        reward = RoleReward(hero_name, role, team_1_value, team_2_value)
        self.reward_model.add_reward(reward)
        QDialog.accept(self)

    @Slot()
    def reject(self):
        if self.edit_reward is not None:
            self.reward_model.add_reward(self.edit_reward)
        QDialog.reject(self)
