"""
Dialogs for constructing each reward type that ensure the UI doesn't
allow the user to have rewards incompatible with the draft AI engine.
"""

from PySide6.QtCore import QSortFilterProxyModel, Slot, Qt, QSize
from PySide6.QtWidgets import (QDialog, QAbstractItemView, QListView, QLineEdit,
                               QVBoxLayout, QLabel, QComboBox, QGridLayout,
                               QDoubleSpinBox, QDialogButtonBox, QMessageBox,
                               QPushButton, QCheckBox)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from ai import draft_ai
from hero_box import HeroBox, set_hero_box_layout_sizes
from reward_models import RoleReward, SynergyReward, CounterReward


SEARCH_ICON_SIZE = QSize(64, 64)
HERO_BOX_SIZE = QSize(64, 64)


roles = ("Top Laner", "Jungler", "Mid Laner", "Bot Laner", "Support")


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


def display_message(parent, text, info_text=None, detailed_text=None, icon=None):
    msg_box = QMessageBox(parent)
    msg_box.setText(text)
    if info_text:
        msg_box.setInformativeText(info_text)
    if detailed_text:
        msg_box.setDetailedText(detailed_text)
    if icon:
        msg_box.setIcon(icon)
    msg_box.exec()


def confirm_delete(parent, n_rewards, reward_type):
    text = "Are you sure you want to delete the {} selected {} rewards?"
    confirm_box = QMessageBox(parent)
    confirm_box.setText(text.format(n_rewards, reward_type))
    confirm_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    return confirm_box.exec()


class RoleRewardDialog(QDialog):

    def __init__(self, reward_model, hero_icons, team_tags, parent):
        super().__init__(parent)

        self.reward_model = reward_model
        self.hero_icons = hero_icons
        self.edit_reward = None

        self.hero_label = QLabel("Champion:") 
        self.hero_box = HeroBox(hero_icons, HERO_BOX_SIZE)
        self.hero_box.set_selected(True)

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
        self.layout.addWidget(self.hero_box, 0, 1, Qt.AlignCenter)
        set_hero_box_layout_sizes(HERO_BOX_SIZE, self.layout, [0], [1])
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
        self.search_bar.textChanged.connect(self.search_f_model.setFilterFixedString)

    def update_role_combobox(self):
        hero_name = self.hero_box.name
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
        self.hero_box.clear()
        self.update_role_combobox()
        self.v_1_spinbox.setValue(0.00)
        self.v_2_spinbox.setValue(0.00)
        self.search_bar.clear()
        self.search_view.clearSelection()

    def set_inputs(self, reward):
        self.hero_box.set_hero(reward.name)
        self.update_role_combobox()
        self.role_combobox.setCurrentText(reward.role)
        self.v_1_spinbox.setValue(reward.team_1_value)
        self.v_2_spinbox.setValue(reward.team_2_value)
        self.search_bar.clear()
        self.search_view.clearSelection()

    @Slot()
    def search_hero_clicked(self, f_index):
        index = self.search_f_model.mapToSource(f_index)
        hero_name = self.search_model.itemFromIndex(index).text()
        self.hero_box.set_hero(hero_name)
        self.update_role_combobox()

    def open_add(self):
        if len(self.reward_model.rewards) == draft_ai.MAX_NUM_HEROES:
            display_message(
                self.parentWidget(),
                f"The current engine only supports {draft_ai.MAX_NUM_HEROES}" \
                " role rewards. Extending it to support double has not been a" \
                " priority, but is on the roadmap.",
            )
        else:
            self.edit_reward = None
            self.clear_inputs()
            QDialog.open(self)
            self.search_bar.setFocus(Qt.PopupFocusReason)

    # For editing the reward is deleted from model first to allow for
    # same logic when creating a new reward. The original reward is
    # saved so it can be added back if the dialog is rejected.
    def open_edit(self, reward_index, synergy_model, counter_model):
        self.edit_reward = self.reward_model.data(reward_index, Qt.UserRole)

        # must check if role reward is used in synergy/counter rewards
        # and if so ensure user can only change the team values
        synergies = synergy_model.uses_role_reward(self.edit_reward)
        counters_h, counters_f = counter_model.uses_role_reward(self.edit_reward)
        num_roles = len(self.reward_model.get_hero_roles(self.edit_reward.name))
        if synergies or counters_h:
            self.disable_hero_role_selections()
            self.setToolTip("Unable to edit champion or role because this role" \
                            " reward is used in other synergy/counter rewards.")
        elif counters_f and num_roles == 1:
            # if used as a foe in a counter and is the only existing reward
            # for this hero then users can't edit hero, but can edit the role
            self.disable_hero_role_selections()
            self.role_combobox.setEnabled(True)
            self.setToolTip("Unable to edit champion because they are used as an" \
                            " adversary in a counter reward and no other role rewards" \
                            f" are defined for {self.edit_reward.name}.")

        self.reward_model.delete_reward(self.edit_reward)
        self.set_inputs(self.edit_reward)
        QDialog.open(self)
        self.search_bar.setFocus(Qt.PopupFocusReason)

    def disable_hero_role_selections(self):
        self.role_combobox.setDisabled(True)
        self.search_f_model.setFilterFixedString("**")  # filter out all heroes
        self.search_bar.setDisabled(True)
        self.search_bar.setPlaceholderText(None)

    def enable_hero_role_selections(self):
        self.role_combobox.setEnabled(True)
        self.search_f_model.setFilterFixedString("")
        self.search_bar.setEnabled(True)
        self.search_bar.setPlaceholderText("Search...")
        self.setToolTip(None)

    # A role reward can't be deleted if it is contained in a synergy,
    # counter team or is used in a counter foes when it is the only
    # defined role reward for some hero. For now just displaying the
    # number of other rewards, but @Later I could present a list that
    # they can directly edit.
    def open_delete(self, reward_indexes, synergy_model, counter_model):
        if not reward_indexes:
            return
        ret = confirm_delete(self.parentWidget(), len(reward_indexes), "role")
        if ret == QMessageBox.No:
            return False

        start_error_text = "Unable to delete {} as {} because they are used "
        info_text = "Delete or select a different role for {} in these rewards first."

        rewards = [self.reward_model.data(i, Qt.UserRole) for i in reward_indexes]
        for reward in rewards:
            synergies = synergy_model.uses_role_reward(reward)
            counters_h, counters_f = counter_model.uses_role_reward(reward)
            num_roles = len(self.reward_model.get_hero_roles(reward.name))
            if synergies and counters_h:
                display_message(
                    self.parentWidget(),
                    start_error_text.format(reward.name, reward.role) +
                    f"in {len(synergies)} synergy and {len(counters_h)} counter rewards.",
                    info_text.format(reward.name),
                    icon=QMessageBox.Warning,
                )
            elif synergies:
                display_message(
                    self.parentWidget(),
                    start_error_text.format(reward.name, reward.role) +
                    f"in {len(synergies)} synergy rewards.",
                    info_text.format(reward.name),
                    icon=QMessageBox.Warning,
                )
            elif counters_h:
                display_message(
                    self.parentWidget(),
                    start_error_text.format(reward.name, reward.role) +
                    f"in {len(counters_h)} counter rewards.",
                    info_text.format(reward.name),
                    icon=QMessageBox.Warning,
                )
            elif counters_f and num_roles == 1:
                display_message(
                    self.parentWidget(),
                    start_error_text.format(reward.name, reward.role) +
                    f"as an adversary in {len(counters_f)} counter rewards " \
                    f"and there are no other role rewards defined for {reward.name}.",
                    icon=QMessageBox.Warning,
                )
            else:
                self.reward_model.delete_reward(reward)
        self.accepted.emit()  # important for stats widget to know rewards have changed
        return True

    # Create role reward and add to model if everything has been input
    # before closing the dialog.
    @Slot()
    def accept(self):
        # only check needed as duplicate roles are disabled for each hero
        # and a hero must be selected before you can select a role
        if self.role_combobox.currentIndex() == -1:
            return
        hero_name = self.hero_box.name
        role = self.role_combobox.currentText()
        team_1_value = self.v_1_spinbox.value()
        team_2_value = self.v_2_spinbox.value()
        reward = RoleReward(hero_name, role, team_1_value, team_2_value)
        self.reward_model.add_reward(reward)
        if self.edit_reward is not None:
            self.enable_hero_role_selections()  # enable just in case it was disabled
        QDialog.accept(self)

    @Slot()
    def reject(self):
        if self.edit_reward is not None:
            self.reward_model.add_reward(self.edit_reward)
            self.enable_hero_role_selections()  # enable just in case it was disabled
        QDialog.reject(self)


# @Important: The counter reward dialog subclasses this. I didn't
# implement it with that in mind, but it happens to work out. If I make
# changes to this class I must make sure it doesn't break anything in
# the counter reward dialog.
class SynergyRewardDialog(QDialog):

    def __init__(self, hero_roles, reward_model, hero_icons, team_tags, parent):
        super().__init__(parent)

        self.hero_roles = hero_roles
        self.reward_model = reward_model
        self.hero_icons = hero_icons
        self.edit_reward = None
        self.type = 'synergy'

        self.heroes_label = QLabel("Champions:") 
        self.hero_boxes = []
        for i in range(len(roles)):
            hero_box = HeroBox(hero_icons, HERO_BOX_SIZE)
            self.hero_boxes.append(hero_box)
            hero_box.clicked.connect(self.hero_box_clicked)
            hero_box.index = i

        self.hero_role_checkboxes = []
        for _ in range(len(self.hero_boxes)):
            role_checkboxes = [QCheckBox() for _ in range(len(roles))]
            self.hero_role_checkboxes.append(role_checkboxes)

        self.remove_hero_button = QPushButton("Remove")
        self.remove_hero_button.clicked.connect(self.remove_hero)
        self.remove_hero_button.setEnabled(False)

        self.v_1_label = QLabel(team_tags[0] + " value:")
        self.v_2_label = QLabel(team_tags[1] + " value:")
        self.v_1_spinbox = init_value_spinbox()
        self.v_2_spinbox = init_value_spinbox()

        self.setup_hero_search()

        self.dialog_buttonbox = QDialogButtonBox(QDialogButtonBox.Save |
                                                 QDialogButtonBox.Cancel)
        self.dialog_buttonbox.accepted.connect(self.accept)
        self.dialog_buttonbox.rejected.connect(self.reject)

        self.init_layout()

    def setup_hero_search(self):
        # source model (only heroes with role reward will be used)
        self.search_model = QStandardItemModel(0, 1)

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
        self.search_bar.textChanged.connect(self.search_f_model.setFilterFixedString)

    def init_layout(self):
        self.layout = QGridLayout(self)

        # hero boxes
        self.layout.addWidget(self.heroes_label, 0, 0)
        for i in range(len(roles)):
            self.layout.addWidget(self.hero_boxes[i], 0, i + 1, Qt.AlignCenter)

            # role checkboxes
            self.layout.addWidget(QLabel(roles[i] + ":"), i + 1, 0)
            role_checkboxes = self.hero_role_checkboxes[i]
            for j in range(len(roles)):
                # checkboxes for hero box i are placed in the rows underneath
                self.layout.addWidget(role_checkboxes[j], j + 1, i + 1, Qt.AlignCenter)
        set_hero_box_layout_sizes(HERO_BOX_SIZE, self.layout, [0], [1, 2, 3, 4, 5])

        # counter rewards will need to insert the foe hero boxes at this point
        offset = 7 if isinstance(self, CounterRewardDialog) else 6

        # spin boxes
        self.layout.addWidget(self.v_1_label, offset, 0)
        self.layout.addWidget(self.v_1_spinbox, offset, 1, 1, 5)
        self.layout.addWidget(self.v_2_label, offset + 1, 0)
        self.layout.addWidget(self.v_2_spinbox, offset + 1, 1, 1, 5)

        # search
        self.layout.addWidget(self.search_bar, offset + 2, 0, 1, 4)
        self.layout.addWidget(self.search_view, offset + 3, 0, 1, 6)

        self.layout.addWidget(self.remove_hero_button, offset + 2, 4, 1, 2)  # placed beside search bar

        self.layout.addWidget(self.dialog_buttonbox, offset + 4, 0, 1, 6)

    # Only allow heroes with a role reward to be searched for.
    def set_search_heroes(self):
        self.search_model.clear()
        for name, roles in self.hero_roles.items():
            if roles:
                item = QStandardItem(self.hero_icons[name], name)
                self.search_model.appendRow(item)

    @Slot()
    def hero_box_clicked(self, hero_name):
        clicked_box = self.sender()
        
        # check if some other box is selected
        for hero_box in self.hero_boxes:
            if hero_box.selected:
                selected_box_roles = self.get_checked_roles(hero_box)   # save checked roles before switching
                clicked_box_roles = self.get_checked_roles(clicked_box) # so they can be restored after
                clicked_box.switch_with_selected(hero_box)
                self.update_role_checkboxes(hero_box, clicked_box_roles)
                self.update_role_checkboxes(clicked_box, selected_box_roles)
                self.remove_hero_button.setEnabled(False)
                return

        # check if a hero in search view is selected 
        selected_search_indexes = self.search_view.selectedIndexes()
        if not selected_search_indexes:
            # then no other box or search hero are selected
            clicked_box.set_selected(True)
            if clicked_box.name:
                self.remove_hero_button.setEnabled(True)  # enable delete button if box contains hero
        else:
            index = self.search_f_model.mapToSource(selected_search_indexes[0])
            search_item = self.search_model.itemFromIndex(index)
            clicked_box.set_hero_from_search_item(search_item)
            self.search_view.clearSelection()
            self.update_role_checkboxes(clicked_box)
            self.remove_hero_button.setEnabled(False)

    @Slot()
    def search_hero_clicked(self, f_index):
        index = self.search_f_model.mapToSource(f_index)
        search_item = self.search_model.itemFromIndex(index)
        if not search_item.isEnabled():
            return

        # check if a hero box is selected and if so set its contents
        for hero_box in self.hero_boxes:
            if hero_box.selected:
                hero_box.set_hero_from_search_item(search_item)
                self.search_view.clearSelection()
                self.update_role_checkboxes(hero_box)
                self.remove_hero_button.setEnabled(False)
                return

    @Slot()
    def remove_hero(self):
        for hero_box in self.hero_boxes:
            if hero_box.selected:
                assert hero_box.name  # button should not be enabled if box is empty
                item = self.search_model.findItems(hero_box.name)[0]
                item.setEnabled(True)
                hero_box.set_selected(False)
                hero_box.clear()
                self.remove_hero_button.setEnabled(False)
                self.update_role_checkboxes(hero_box)
                return

    # Hides all checkboxes corresponding to roles that the hero in a
    # box has no role reward for. Default is to have all non hidden
    # checkboxes checked or you can proivde optional reduced set.
    def update_role_checkboxes(self, hero_box, check_if_allowed=roles):
        role_checkboxes = self.hero_role_checkboxes[hero_box.index]
        if not hero_box.name:
            for checkbox in role_checkboxes:
                checkbox.hide()
                checkbox.setChecked(False)
        else:
            for checkbox, role in zip(role_checkboxes, roles):
                if role in self.hero_roles[hero_box.name]:
                    checkbox.show()
                    checkbox.setChecked(role in check_if_allowed)
                else:
                    checkbox.hide()
                    checkbox.setChecked(False)

    def get_checked_roles(self, hero_box):
        checked_roles = []
        role_checkboxes = self.hero_role_checkboxes[hero_box.index]
        for checkbox, role in zip(role_checkboxes, roles):
            if checkbox.isChecked():
                checked_roles.append(role)
        return checked_roles

    def clear_heroes(self, hero_boxes):
        for hero_box in hero_boxes:
            hero_box.set_selected(False)
            hero_box.clear()
            self.update_role_checkboxes(hero_box)

    def clear_inputs(self):
        self.clear_heroes(self.hero_boxes)
        self.v_1_spinbox.setValue(0.00)
        self.v_2_spinbox.setValue(0.00)
        self.search_bar.clear()
        self.search_view.clearSelection()

    def set_inputs(self, reward):
        for hero, hero_box in zip(reward.heroes, self.hero_boxes):
            name, used_roles = hero
            hero_box.set_selected(False)
            hero_box.set_hero(name)
            self.update_role_checkboxes(hero_box, used_roles)
            search_item = self.search_model.findItems(name)[0]
            search_item.setEnabled(False)
        self.clear_heroes(self.hero_boxes[len(reward.heroes):])  # clear any boxes not used for synergy
        self.v_1_spinbox.setValue(reward.team_1_value)
        self.v_2_spinbox.setValue(reward.team_2_value)
        self.search_bar.clear()
        self.search_view.clearSelection()

    def open_add(self):
        self.set_search_heroes()
        self.edit_reward = None
        self.clear_inputs()
        QDialog.open(self)
        self.search_bar.setFocus(Qt.PopupFocusReason)

    # For editing the reward is deleted from model first to allow for
    # same logic when creating a new reward. The original reward is
    # saved so it can be added back if the dialog is rejected.
    def open_edit(self, reward_index):
        self.set_search_heroes()
        self.edit_reward = self.reward_model.data(reward_index, Qt.UserRole)
        self.reward_model.delete_reward(self.edit_reward)
        self.set_inputs(self.edit_reward)
        QDialog.open(self)
        self.search_bar.setFocus(Qt.PopupFocusReason)

    def open_delete(self, reward_indexes):
        if not reward_indexes:
            return
        ret = confirm_delete(self.parentWidget(), len(reward_indexes), self.type)
        if ret == QMessageBox.Yes:
            self.reward_model.delete_rewards(reward_indexes)
            self.accepted.emit()
            return True
        return False

    @Slot()
    def accept(self):
        heroes = {}
        for hero_box in self.hero_boxes:
            if hero_box.name:
                checked_roles = self.get_checked_roles(hero_box)
                if not checked_roles:
                    return  # all synergy heroes must have at least one applicable role
                heroes[hero_box.name] = checked_roles

        if len(heroes) < 2:
            display_message(
                self,
                "A valid synergy must contain at least two champions.",
                icon=QMessageBox.Critical,
            )
            return

        team_1_value = self.v_1_spinbox.value()
        team_2_value = self.v_2_spinbox.value()
        reward = SynergyReward(heroes, team_1_value, team_2_value)

        if not reward.hero_role_asgmts:
            display_message(
                self,
                "Impossible to play each champion in a unique role.",
                icon=QMessageBox.Critical,
            )
            return 

        clashes = reward.hero_role_asgmts & self.reward_model.hero_role_asgmts
        if clashes:
            display_message(
                self,
                "Reward values already exist for playing these champions" \
                " in certain role combinations. (See details).",
                info_text="Deselect the clashing roles to assign different values for" \
                          " synergies between the same champions in different roles.",
                detailed_text=self.format_clashes(clashes),
                icon=QMessageBox.Critical
            )
            return

        self.reward_model.add_reward(reward)
        QDialog.accept(self)

    @Slot()
    def reject(self):
        if self.edit_reward is not None:
            self.reward_model.add_reward(self.edit_reward)
        QDialog.reject(self)

    def format_clashes(self, clashes):
        text = ""
        for i, clash in enumerate(clashes):
            text += f"{str(i + 1)}:\n"
            for name, role in clash:
                text += f"  * {name} - {role}\n"
            text += "\n"
        return text


# Constructing a counter reward is very similar to a synergy reward with
# the difference of also needing to supply a set of adversaries.
class CounterRewardDialog(SynergyRewardDialog):

    def __init__(self, hero_roles, reward_model, hero_icons, team_tags, parent):
        super().__init__(hero_roles, reward_model, hero_icons, team_tags, parent)

        self.type = 'counter'

        self.foes_label = QLabel("Adversaries:")

        # add 5 hero boxes for the foes (same list is used to allow
        # updating methods in synergy dialog to still work)
        for i in range(len(roles)):
            hero_box = HeroBox(hero_icons, HERO_BOX_SIZE)
            self.hero_boxes.append(hero_box)
            hero_box.clicked.connect(self.hero_box_clicked)
            hero_box.index = len(roles) + i

        # add foe boxes to layout
        self.layout.addWidget(self.foes_label, 6, 0)
        for i in range(len(roles)):
            self.layout.addWidget(self.hero_boxes[len(roles) + i], 6, i + 1, Qt.AlignCenter)
        set_hero_box_layout_sizes(HERO_BOX_SIZE, self.layout, [6], [1, 2, 3, 4, 5])

    # Only the team heroes have applicable roles selected so there are
    # no role checkboxes for the foe hero boxes.
    def update_role_checkboxes(self, hero_box, check_if_allowed=roles):
        if hero_box.index < 5:
            SynergyRewardDialog.update_role_checkboxes(self, hero_box, check_if_allowed)

    # There are no roles or checkboxes for the foes. All roles are
    # returned so that hero_box_clicked initially checks all role boxes
    # when switching a hero from a foe box to a hero box.
    def get_checked_roles(self, hero_box):
        if hero_box.index < 5:
            return SynergyRewardDialog.get_checked_roles(self, hero_box)
        else:
            return roles

    # The synergy set_inputs method will handle setting the team heroes
    # and clearing all remaining boxes which means all thats left to do
    # is set the foe heroes.
    def set_inputs(self, reward):
        SynergyRewardDialog.set_inputs(self, reward)
        for name, hero_box in zip(reward.foes, self.hero_boxes[len(roles):]):
            hero_box.set_hero(name)  # box has already been deselected
            search_item = self.search_model.findItems(name)[0]
            search_item.setEnabled(False)

    @Slot()
    def accept(self):
        heroes = {}
        for hero_box in self.hero_boxes[:len(roles)]:
            if hero_box.name:
                checked_roles = self.get_checked_roles(hero_box)
                if not checked_roles:
                    return  # all team heroes must have at least one applicable role
                heroes[hero_box.name] = checked_roles
        if not heroes:
            return  # must be at least one chosen team hero

        foes = []
        for hero_box in self.hero_boxes[len(roles):]:
            if hero_box.name:
                foes.append(hero_box.name)
        if not foes:
            return  # must be at least one chosen foe

        team_1_value = self.v_1_spinbox.value()
        team_2_value = self.v_2_spinbox.value()
        reward = CounterReward(heroes, foes, team_1_value, team_2_value)

        if not reward.hero_role_asgmts:
            display_message(
                self,
                "Impossible to play each champion in a unique role.",
                icon=QMessageBox.Critical,
            )
            return 

        clashes = reward.hero_role_asgmts & self.reward_model.hero_role_asgmts
        if clashes:
            display_message(
                self,
                "Reward values already exist for playing these champions in" \
                " certain role combinations vs the selected adversaries. (See details).",
                info_text="Deselect the clashing roles to assign different values for" \
                          " counters between the same champions in different roles.",
                detailed_text=self.format_clashes(clashes),
                icon=QMessageBox.Critical,
            )
            return

        self.reward_model.add_reward(reward)
        QDialog.accept(self)

    def format_clashes(self, clashes):
        text = ""
        for i, clash in enumerate(clashes):
            heroes, foes = clash
            text += f"{str(i + 1)}:\n"
            for name, role in heroes:
                text += f"  * {name} - {role}\n"
            text += "  VS\n"
            for name in foes:
                text += f"  * {name}\n"
            text += "\n"
        return text
