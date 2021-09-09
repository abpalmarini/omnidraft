import itertools

from PySide6.QtCore import Qt, Signal, Slot, QSize, QSortFilterProxyModel
from PySide6.QtWidgets import (QWidget, QLabel, QGridLayout, QDialog, QLineEdit,
                               QDialogButtonBox, QVBoxLayout, QPushButton,
                               QCheckBox, QGroupBox, QLCDNumber, QFrame)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from hero_box import HeroBox
from reward_dialogs import init_search_list_view
from reward_models import TEAM_1, TEAM_2, NO_TEAM, TEAM_1_COLOR, TEAM_2_COLOR


HERO_BOX_SIZE = QSize(72, 72)
ROLE_LABEL_SIZE = QSize(32, 32)


class TeamBuilder(QWidget):

    teams_changed = Signal(list, list)

    def __init__(self, hero_icons, role_icons, team_tags):
        super().__init__()

        self.roles = list(role_icons)
        self.team_1 = []
        self.team_2 = []

        team_1_label = QLabel(team_tags[0])
        team_2_label = QLabel(team_tags[1])

        self.team_1_boxes = []
        self.team_2_boxes = []
        for i in range(2 * len(self.roles)):
            team_boxes = self.team_1_boxes if i < len(self.roles) else self.team_2_boxes
            hero_box = HeroBox(hero_icons, HERO_BOX_SIZE)
            hero_box.clicked.connect(self.hero_box_clicked)
            hero_box.doubleClicked.connect(self.hero_box_double_clicked)
            team_boxes.append(hero_box)

        role_labels = []
        for role, role_icon in role_icons.items():
            role_label = QLabel()
            role_label.setPixmap(role_icon.pixmap(ROLE_LABEL_SIZE))
            role_labels.append(role_label)

        self.select_dialog = HeroSelectDialog(hero_icons, self)
        self.select_dialog.search_view.clicked.connect(self.search_item_clicked)

        self.remove_hero_button = QPushButton("Remove")
        self.remove_hero_button.clicked.connect(self.remove_hero)
        self.remove_hero_button.setEnabled(False)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_all_hero_boxes)

        self.hide_non_granted_checkbox = QCheckBox("Hide non-granted rewards")

        layout = QGridLayout(self)
        layout.addWidget(team_1_label, 0, 0, Qt.AlignCenter)
        layout.addWidget(team_2_label, 0, 2, Qt.AlignCenter)
        for i in range(len(self.roles)):
            layout.addWidget(self.team_1_boxes[i], i + 1, 0)
            layout.addWidget(role_labels[i], i + 1, 1, Qt.AlignCenter)
            layout.addWidget(self.team_2_boxes[i], i + 1, 2)
        layout.addWidget(self.remove_hero_button, 6, 0, 1, 3)
        layout.addWidget(self.clear_button, 7, 0, 1, 3)
        layout.addWidget(self.hide_non_granted_checkbox, 8, 0, 1, 3)

    # Creates a list of hero-role tuples using the non-empty hero boxes
    # for each team. The teams_changed signal is emitted so that the
    # reward models can check which of their rewards should be granted
    # based on the teams.
    def update_teams(self):

        def get_team(team_hero_boxes):
            team = []
            for hero_box, role in zip(team_hero_boxes, self.roles):
                if hero_box.name:
                    team.append((hero_box.name, role))
            return team

        self.team_1 = get_team(self.team_1_boxes)
        self.team_2 = get_team(self.team_2_boxes)
        self.teams_changed.emit(self.team_1, self.team_2)

    # Switch hero box contents if there is an already selected box and
    # if not set the box to being selected.
    @Slot()
    def hero_box_clicked(self, hero_name):
        clicked_box = self.sender()
        for hero_box in itertools.chain(self.team_1_boxes, self.team_2_boxes):
            if hero_box.selected:
                clicked_box.switch_with_selected(hero_box)
                if hero_box != clicked_box:
                    self.update_teams()  # no point in updating if switching box with itself
                self.remove_hero_button.setEnabled(False)
                return
        # select the clicked box if no other hero box is selected
        clicked_box.set_selected(True)
        if clicked_box.name:
            self.remove_hero_button.setEnabled(True)

    # Stores box that was double clicked and opens up the hero selector.
    @Slot()
    def hero_box_double_clicked(self, hero_name):
        self.dbl_clicked_box = self.sender()
        for hero_box in itertools.chain(self.team_1_boxes, self.team_2_boxes):
            hero_box.set_selected(False)
        self.dbl_clicked_box.set_selected(True)
        if self.dbl_clicked_box.name:
            self.remove_hero_button.setEnabled(True)
        self.select_dialog.open()

    # Sets the selected hero to the hero box that was double clicked and
    # opened the select dialog in the first place.
    @Slot()
    def search_item_clicked(self, f_index):
        search_item = self.select_dialog.get_item(f_index)
        if search_item.isEnabled():
            self.select_dialog.accept()
            self.dbl_clicked_box.set_hero_from_search_item(search_item)
            self.update_teams()
            self.remove_hero_button.setEnabled(False)

    @Slot()
    def remove_hero(self):
        for hero_box in itertools.chain(self.team_1_boxes, self.team_2_boxes):
            if hero_box.selected:
                assert hero_box.name
                # re-enable search item if removing it from box
                search_item = self.select_dialog.get_item(hero_box.name)
                search_item.setEnabled(True)
                hero_box.set_selected(False)
                hero_box.clear()
                self.update_teams()
                self.remove_hero_button.setEnabled(False)
                return

    @Slot()
    def clear_all_hero_boxes(self):
        for hero_box in itertools.chain(self.team_1_boxes, self.team_2_boxes):
            if hero_box.name:
                # re-enable search item if box to be cleared contains a hero
                search_item = self.select_dialog.get_item(hero_box.name)
                search_item.setEnabled(True)
            hero_box.set_selected(False)
            hero_box.clear()
            self.remove_hero_button.setEnabled(False)
        self.update_teams()


class HeroSelectDialog(QDialog):
    """
    Simple dialog that when opened presents a list of all heroes that
    can be searched.
    """

    def __init__(self, hero_icons, parent):
        super().__init__(parent)

        # source model
        self.search_model = QStandardItemModel(len(hero_icons), 1)
        for i, hero_name in enumerate(hero_icons):
            item = QStandardItem(hero_icons[hero_name], hero_name)
            self.search_model.setItem(i, item)

        # filter model
        self.search_f_model = QSortFilterProxyModel()
        self.search_f_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.search_f_model.setSourceModel(self.search_model)

        # list view
        self.search_view = init_search_list_view()
        self.search_view.setModel(self.search_f_model)

        # search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.textChanged.connect(self.search_f_model.setFilterFixedString)

        dialog_buttonbox = QDialogButtonBox(QDialogButtonBox.Close)
        dialog_buttonbox.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_bar)
        layout.addWidget(self.search_view)
        layout.addWidget(dialog_buttonbox)

    def open(self):
        self.search_bar.clear()
        self.search_view.clearSelection()
        self.search_view.scrollToTop()
        QDialog.open(self)
        self.search_bar.setFocus(Qt.PopupFocusReason)

    # Returns the search item corresponding to the name or filter index.
    def get_item(self, name_or_f_index):
        if isinstance(name_or_f_index, str):
            search_item = self.search_model.findItems(name_or_f_index)[0]
        else:
            index = self.search_f_model.mapToSource(name_or_f_index)
            search_item = self.search_model.itemFromIndex(index)
        return search_item


# For now this simply displays each team's total value and the overall
# overall value from team 1's perspective. More can be added @Later.
class RewardInfo(QGroupBox):
    """Displays group of information on the rewards granted in team builder."""

    def __init__(self, role_model, synergy_model, counter_model, team_tags):
        super().__init__()

        self.role_model = role_model
        self.synergy_model = synergy_model
        self.counter_model = counter_model
        self.reward_models = (role_model, synergy_model, counter_model)

        self.team_1_value_lcd = self.init_lcd(TEAM_1_COLOR)
        self.team_2_value_lcd = self.init_lcd(TEAM_2_COLOR)
        self.overall_value_lcd = self.init_lcd()

        self.update()  # ensure correct starting values

        layout = QGridLayout(self)
        layout.addWidget(self.team_1_value_lcd, 0, 0)
        layout.addWidget(self.team_2_value_lcd, 0, 1)
        layout.addWidget(self.overall_value_lcd, 1, 0, 2, 2)

    def init_lcd(self, color=None):
        lcd = QLCDNumber(6)
        lcd.setSegmentStyle(QLCDNumber.Flat)
        if color is not None:
            palette = lcd.palette()
            palette.setColor(palette.WindowText, color)
            lcd.setPalette(palette)
        return lcd

    # Find relevant info on all granted rewards and update displays.
    def update(self):
        team_1_value = 0
        team_2_value = 0

        for model in self.reward_models:
            for reward in model.rewards:
                if reward.status == TEAM_1:
                    team_1_value += reward.team_1_value
                elif reward.status == TEAM_2:
                    team_2_value += reward.team_2_value

        self.team_1_value_lcd.display(team_1_value)
        self.team_2_value_lcd.display(team_2_value)
        self.overall_value_lcd.display(team_1_value - team_2_value)
