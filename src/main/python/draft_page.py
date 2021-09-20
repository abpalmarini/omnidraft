from PySide6.QtCore import QSortFilterProxyModel, Slot, Qt, QSize
from PySide6.QtWidgets import (QWidget, QLineEdit, QLabel, QGridLayout,
                               QGroupBox, QSizePolicy)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from hero_box import HeroBox, set_hero_box_layout_sizes
from reward_dialogs import init_search_list_view
from reward_models import TEAM_1, TEAM_2
from ai.draft_ai import DraftAI, A, B, PICK, BAN


HERO_BOX_SIZE = QSize(100, 100)


class DraftPage(QWidget):

    def __init__(self, hero_icons, draft_format, team_tags):
        super().__init__()
        
        self.draft_format = draft_format
        self.team_tags = team_tags
        self.team_A = TEAM_1

        self.team_A_label = QLabel(team_tags[0])
        self.team_B_label = QLabel(team_tags[1])

        # initialise a hero box for each stage in the draft
        self.hero_boxes = []
        for i in range(len(draft_format)):
            hero_box = HeroBox(hero_icons, HERO_BOX_SIZE)
            self.hero_boxes.append(hero_box)
            hero_box.clicked.connect(self.hero_box_clicked)

        self.setup_hero_search()
        self.init_layout()

    # @CopyPaste from reward_dialogs.py
    def setup_hero_search(self):
        # source model (only heroes with role reward will be used and
        # will be set by the set_rewards method)
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

    # For now the layout simply consists of the team headers side by side.
    # Underneath that is a row of the 5 picks for each team side by side
    # and underneath that a row for however many bans needed. Assuming
    # for now that there won't be more than 5 bans. Providing a label for
    # the picks and bans, but @Later it may be better to use a ban icon.
    def init_layout(self):
        self.layout = QGridLayout(self)

        self.layout.addWidget(self.team_A_label, 0, 1, Qt.AlignCenter)
        self.layout.addWidget(self.team_B_label, 0, 2, Qt.AlignCenter)

        self.layout.addWidget(QLabel("Picks:"), 1, 0)
        self.layout.addWidget(QLabel("Bans:"), 2, 0)

        # separate hero boxes by selection type
        boxes = {(A, PICK): [], (B, PICK): [], (A, BAN): [], (B, BAN): []}
        for hero_box, selection in zip(self.hero_boxes, self.draft_format):
            boxes[selection].append(hero_box)

        # add grouped selection type boxes to layout
        self.layout.addWidget(self.group_hero_boxes(boxes[(A, PICK)]), 1, 1)
        self.layout.addWidget(self.group_hero_boxes(boxes[(B, PICK)]), 1, 2)
        self.layout.addWidget(self.group_hero_boxes(boxes[(A, BAN)]), 2, 1)
        self.layout.addWidget(self.group_hero_boxes(boxes[(B, BAN)]), 2, 2)

        # search
        self.layout.addWidget(self.search_bar, 3, 1, 1, 2)
        self.layout.addWidget(self.search_view, 4, 1, 1, 2)

    # Lays out the hero boxes of some selection type into a self
    # contained groupbox.
    def group_hero_boxes(self, hero_boxes):
        groupbox = QGroupBox()
        layout = QGridLayout(groupbox)
        for i, hero_box in enumerate(hero_boxes):
            layout.addWidget(hero_box, 0, i, Qt.AlignCenter)
        set_hero_box_layout_sizes(HERO_BOX_SIZE, layout, [0], list(range(len(hero_boxes))))
        groupbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return groupbox

    @Slot()
    def hero_box_clicked(self, hero_name):
        clicked_box = self.sender()
        pass

    @Slot()
    def search_hero_clicked(self, f_index):
        pass
