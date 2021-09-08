import itertools

from PySide6.QtCore import Qt, QSize, QSortFilterProxyModel
from PySide6.QtWidgets import (QWidget, QLabel, QGridLayout, QDialog, QLineEdit,
                               QDialogButtonBox, QVBoxLayout)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from hero_box import HeroBox
from reward_dialogs import init_search_list_view


HERO_BOX_SIZE = QSize(72, 72)
ROLE_LABEL_SIZE = QSize(32, 32)


class TeamBuilder(QWidget):

    def __init__(self, hero_icons, role_icons, team_tags):
        super().__init__()

        self.roles = list(role_icons)

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

        layout = QGridLayout(self)
        layout.addWidget(team_1_label, 0, 0, Qt.AlignCenter)
        layout.addWidget(team_2_label, 0, 2, Qt.AlignCenter)
        for i in range(len(self.roles)):
            layout.addWidget(self.team_1_boxes[i], i + 1, 0)
            layout.addWidget(role_labels[i], i + 1, 1, Qt.AlignCenter)
            layout.addWidget(self.team_2_boxes[i], i + 1, 2)

    # Switch hero box contents if there is an already selected box and
    # if not set the box to being selected.
    def hero_box_clicked(self, hero_name):
        clicked_box = self.sender()
        for hero_box in itertools.chain(self.team_1_boxes, self.team_2_boxes):
            if hero_box.selected:
                clicked_box.switch_with_selected(hero_box)
                return
        clicked_box.set_selected(True)

    # Stores box that was double clicked and opens up the hero selector.
    def hero_box_double_clicked(self, hero_name):
        self.dbl_clicked_box = self.sender()
        for hero_box in itertools.chain(self.team_1_boxes, self.team_2_boxes):
            hero_box.set_selected(False)
        self.dbl_clicked_box.set_selected(True)
        self.select_dialog.open()

    # Sets the selected hero to the hero box that was double clicked and
    # opened the select dialog in the first place.
    def search_item_clicked(self, f_index):
        search_item = self.select_dialog.get_item(f_index)
        if search_item.isEnabled():
            self.select_dialog.accept()
            self.dbl_clicked_box.set_hero_from_search_item(search_item)


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

    # Returns the search item corresponding to the filter index.
    def get_item(self, f_index):
        index = self.search_f_model.mapToSource(f_index)
        search_item = self.search_model.itemFromIndex(index)
        return search_item
