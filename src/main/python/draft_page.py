from PySide6.QtCore import QSortFilterProxyModel, Slot, Qt, QSize
from PySide6.QtWidgets import (QWidget, QLineEdit, QLabel, QGridLayout,
                               QGroupBox, QSizePolicy)
from PySide6.QtGui import QStandardItemModel, QStandardItem

from hero_box import HeroBox, set_hero_box_layout_sizes
from reward_dialogs import init_search_list_view
from reward_models import TEAM_1, TEAM_2
from ai.draft_ai import DraftAI, RoleR, SynergyR, CounterR, A, B, PICK, BAN


HERO_BOX_SIZE = QSize(100, 100)


class DraftPage(QWidget):

    def __init__(self, hero_icons, roles, draft_format, team_tags):
        super().__init__()
        
        self.hero_icons = hero_icons
        self.ai_roles = {role: i for i, role in enumerate(roles)}
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
    # for now that there won't be more than 5 bans. Could be useful to
    # have ban icons @Later to avoid confusion.
    def init_layout(self):
        self.layout = QGridLayout(self)

        self.layout.addWidget(self.team_A_label, 0, 0, Qt.AlignCenter)
        self.layout.addWidget(self.team_B_label, 0, 1, Qt.AlignCenter)

        # separate hero boxes by selection type
        boxes = {(A, PICK): [], (B, PICK): [], (A, BAN): [], (B, BAN): []}
        for hero_box, selection in zip(self.hero_boxes, self.draft_format):
            boxes[selection].append(hero_box)

        # add grouped selection type boxes to layout
        self.layout.addWidget(self.group_hero_boxes(boxes[(A, PICK)]), 1, 0)
        self.layout.addWidget(self.group_hero_boxes(boxes[(B, PICK)]), 1, 1)
        self.layout.addWidget(self.group_hero_boxes(boxes[(A, BAN)]), 2, 0)
        self.layout.addWidget(self.group_hero_boxes(boxes[(B, BAN)]), 2, 1)

        # search
        self.layout.addWidget(self.search_bar, 3, 0, 1, 2)
        self.layout.addWidget(self.search_view, 4, 0, 1, 2)

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

    # Updates the DraftAI object used for creating histories and
    # running searches using the reward attributes and the team A flag
    # attibute. (Should be called after any of these change). Method
    # also ensures that any existing history is compatible with the new
    # DraftAI object.
    def update_draft_ai(self):
        self.draft_ai = DraftAI(
            self.draft_format,
            [self.ai_reward(r, 'role') for r in self.role_rs],
            [self.ai_reward(r, 'synergy') for r in self.synergy_rs],
            [self.ai_reward(r, 'counter') for r in self.counter_rs],
        )

        # check and update history in hero boxes
        # TODO

    # Rewards constructed by the user are not directly useable with the
    # engine and must be adjusted. Firstly, the user creates values for
    # specific teams that could play as either A or B. The AI expects
    # values for A and B and so uses the team_A flag to create the
    # correct reward. Secondly, the values are expected to be integers
    # not floats. Lastly, the AI expects each role to be an integer
    # between 0 and 4.
    def ai_reward(self, reward, reward_type):

        # scaled by 100 because users use 2 decimal places
        def ai_value(value): 
            return int(value * 100)

        # maps applicable roles to ai ones for heroes in a combo reward
        def ai_heroes(heroes):
            _ai_heroes = []
            for hero_name, appl_roles in heroes:
                ai_appl_roles = [self.ai_roles[role] for role in appl_roles]
                _ai_heroes.append((hero_name, ai_appl_roles))
            return _ai_heroes

        # find A/B values
        if self.team_A == TEAM_1:
            A_value = ai_value(reward.team_1_value)
            B_value = ai_value(reward.team_2_value)
        else:
            A_value = ai_value(reward.team_2_value)
            B_value = ai_value(reward.team_1_value)

        if reward_type == 'role':
            role = self.ai_roles[reward.role]
            return RoleR(reward.name, role, A_value, B_value)
        elif reward_type == 'synergy':
            heroes = ai_heroes(reward.heroes)
            return SynergyR(heroes, A_value, B_value)
        elif reward_type == 'counter':
            heroes = ai_heroes(reward.heroes)
            foes = ai_heroes(reward.foes)
            return CounterR(heroes, foes, A_value, B_value)
        else:
            raise ValueError

    # Updates the search model to only include heroes that have a
    # defined role reward, sets the reward attributes, then calls
    # to have the draft ai updated.
    def set_rewards(self, role_rs, synergy_rs, counter_rs):
        # set search heroes
        valid_heroes = sorted({role_r.name for role_r in role_rs})
        self.search_model.clear()
        for name in valid_heroes:
            item = QStandardItem(self.hero_icons[name], name)
            self.search_model.appendRow(item)

        self.role_rs = role_rs
        self.synergy_rs = synergy_rs
        self.counter_rs = counter_rs

        self.update_draft_ai()

    @Slot()
    def hero_box_clicked(self, hero_name):
        clicked_box = self.sender()
        pass

    @Slot()
    def search_hero_clicked(self, f_index):
        pass
