from PySide6.QtCore import QSortFilterProxyModel, Slot, Qt, QSize
from PySide6.QtWidgets import (QDialog, QAbstractItemView, QListView, QLineEdit,
                               QVBoxLayout, QLabel, QComboBox, QGridLayout, QFrame,
                               QDoubleSpinBox, QDialogButtonBox, QMessageBox,
                               QSizePolicy)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from ai import draft_ai
from reward_models import RoleReward


MAX_ROLE_RS_ERROR_MSG = """
The current engine only supports {} role rewards. Extending it to support double has not been a priority, but is on the roadmap.
"""


SEARCH_ICON_SIZE = QSize(64, 64)
HERO_BOX_SIZE = QSize(64, 64)


roles = ("Top Laner", "Jungler", "Mid Laner", "Bot Laner", "Support")


class HeroBox(QLabel):

    def __init__(self, hero_icons):
        super().__init__()

        self.name = ""
        self.hero_icons = hero_icons

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(2)

    def set_hero(self, name):
        self.name = name
        self.setPixmap(self.hero_icons[name].pixmap(self.sizeHint()))

    def sizeHint(self):
        return HERO_BOX_SIZE

    def clear(self):
        self.name = ""
        QLabel.clear(self)


def init_value_spinbox():
    v_spinbox = QDoubleSpinBox()
    v_spinbox.setMaximum(10.00)
    return v_spinbox


def init_search_list_view():
    search_view = QListView()
    search_view.setViewMode(QListView.IconMode)
    search_view.setIconSize(SEARCH_ICON_SIZE)
    search_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
    search_view.setMovement(QListView.Static)
    search_view.setUniformItemSizes(True)
    return search_view


class RoleRewardDialog(QDialog):

    def __init__(self, reward_model, hero_icons, team_tags, parent):
        super().__init__(parent)

        self.reward_model = reward_model
        self.hero_icons = hero_icons
        self.edit_reward = None

        self.hero_label = QLabel("Champion:") 
        self.hero = HeroBox(hero_icons)

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
        self.layout.addWidget(self.hero, 0, 1, Qt.AlignCenter)
        self.layout.addWidget(self.role_label, 1, 0)
        self.layout.addWidget(self.role_combobox, 1, 1)
        self.layout.addWidget(self.v_1_label, 2, 0)
        self.layout.addWidget(self.v_1_spinbox, 2, 1)
        self.layout.addWidget(self.v_2_label, 3, 0)
        self.layout.addWidget(self.v_2_spinbox, 3, 1)
        self.layout.addWidget(self.search_bar, 4, 0, 1, 2)
        self.layout.addWidget(self.search_view, 5, 0, 1, 2)
        self.layout.addWidget(dialog_buttonbox, 6, 0, 1, 2)

    def setup_hero_search(self):
        # source model
        self.search_model = QStandardItemModel(len(self.hero_icons), 1)
        for i, hero_name in enumerate(self.hero_icons):
            item = QStandardItem(self.hero_icons[hero_name], hero_name)
            self.search_model.setItem(i, item)

        # filter model
        self.search_f_model = QSortFilterProxyModel()
        self.search_f_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.search_f_model.setSourceModel(self.search_model)

        # list view
        self.search_view = init_search_list_view()
        self.search_view.setModel(self.search_f_model)
        self.search_view.clicked.connect(self.search_hero_clicked)

        # search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.textChanged.connect(self.search_f_model.setFilterRegularExpression)

    def update_role_combobox(self):
        hero_name = self.hero.name
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
        self.search_view.clearSelection()

    def set_inputs(self, reward):
        self.hero.set_hero(reward.name)
        self.update_role_combobox()
        self.role_combobox.setCurrentText(reward.role)
        self.v_1_spinbox.setValue(reward.team_1_value)
        self.v_2_spinbox.setValue(reward.team_2_value)
        self.search_view.clearSelection()

    @Slot()
    def search_hero_clicked(self, f_index):
        index = self.search_f_model.mapToSource(f_index)
        hero_name = self.search_model.itemFromIndex(index).text()
        self.hero.set_hero(hero_name)
        self.update_role_combobox()

    def open_add(self):
        if len(self.reward_model.rewards) == draft_ai.MAX_NUM_HEROES:
            msg_box = QMessageBox()
            msg_box.setText(MAX_ROLE_RS_ERROR_MSG.format(draft_ai.MAX_NUM_HEROES))
            msg_box.exec()
        else:
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
        hero_name = self.hero.name
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
