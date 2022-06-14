from PySide6.QtCore import QSortFilterProxyModel, Slot, Qt, QSize
from PySide6.QtWidgets import (QWidget, QLineEdit, QGridLayout, QSizePolicy,
                               QGroupBox, QLabel, QPushButton, QHBoxLayout,
                               QToolTip, QFrame, QMessageBox, QDialog,
                               QLCDNumber)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QCursor, QColor

from hero_box import HeroBox, set_hero_box_layout_sizes
from reward_dialogs import init_search_list_view
from reward_models import TEAM_1, TEAM_2, TEAM_1_COLOR, TEAM_2_COLOR
from ai.draft_ai import DraftAI, RoleR, SynergyR, CounterR, A, B, PICK, BAN, INF


HERO_BOX_SIZE = QSize(100, 100)


# Changes the icon of the ban overlay for any hero box representing a ban
# based on whether it contains a hero or not.
def update_ban_icon(hero_box, ban_icons):
    if hasattr(hero_box, "ban_overlay"):
        if hero_box.name:
            hero_box.ban_overlay.setPixmap(ban_icons[1].pixmap(hero_box.size))
        else:
            hero_box.ban_overlay.setPixmap(ban_icons[0].pixmap(hero_box.size))


class DraftPage(QWidget):

    def __init__(self, hero_icons, ban_icons, roles, draft_format, team_tags, team_builder):
        super().__init__()
        
        self.hero_icons = hero_icons
        self.ban_icons = ban_icons
        self.roles = roles
        self.ai_roles = {role: i for i, role in enumerate(roles)}
        self.draft_format = draft_format
        self.team_tags = team_tags
        self.team_builder = team_builder

        self.curr_team_A = TEAM_1
        self.team_A_label = QLabel(team_tags[0])
        self.team_B_label = QLabel(team_tags[1])

        # initialise a hero box for each stage in the draft
        self.hero_boxes = []
        for i in range(len(draft_format)):
            hero_box = HeroBox(hero_icons, HERO_BOX_SIZE)
            self.hero_boxes.append(hero_box)
            hero_box.clicked.connect(self.hero_box_clicked)
            hero_box.index = i
            hero_box.value_label = ValueLabel(hero_box, self)
        self.hero_boxes[0].set_selected(True)

        self.setup_hero_search()

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_button_clicked)

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_button_clicked)

        self.switch_sides_button = QPushButton("Switch Sides")
        self.switch_sides_button.clicked.connect(self.switch_sides_button_clicked)

        self.copy_to_tb_button = QPushButton("Copy to TB")
        self.copy_to_tb_button.clicked.connect(self.copy_to_tb_button_clicked)

        # features for running AI
        self.run_search_button = QPushButton("Find optimal selection(s)")
        self.run_search_button.clicked.connect(self.run_search_button_clicked)
        self.optimal_hero_boxes = (HeroBox(hero_icons, HERO_BOX_SIZE), 
                                   HeroBox(hero_icons, HERO_BOX_SIZE)) 
        self.optimal_hero_boxes[0].clicked.connect(self.optimal_hero_box_clicked)
        self.optimal_hero_boxes[1].clicked.connect(self.optimal_hero_box_clicked)

        self.summary_dialog = SummaryDialog(self)

        self.init_layout()

        self.history_changed(-1)

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
    # for now that there won't be more than 5 bans.
    def init_layout(self):
        self.layout = QGridLayout(self)

        self.layout.addWidget(self.team_A_label, 0, 0, Qt.AlignCenter)
        self.layout.addWidget(self.team_B_label, 0, 1, Qt.AlignCenter)

        # separate hero boxes by selection type and initialise a BanOverlay for all bans
        boxes = {(A, PICK): [], (B, PICK): [], (A, BAN): [], (B, BAN): []}
        for hero_box, selection in zip(self.hero_boxes, self.draft_format):
            if selection[1] == BAN:
                hero_box.ban_overlay = BanOverlay(hero_box)
                update_ban_icon(hero_box, self.ban_icons)
            boxes[selection].append(hero_box)

        # add grouped selection type boxes to layout
        self.layout.addWidget(self.group_hero_boxes(boxes[(A, PICK)]), 1, 0)
        self.layout.addWidget(self.group_hero_boxes(boxes[(B, PICK)]), 1, 1)
        self.layout.addWidget(self.group_hero_boxes(boxes[(A, BAN)]), 2, 0)
        self.layout.addWidget(self.group_hero_boxes(boxes[(B, BAN)]), 2, 1)

        # group features related to running AI search
        ai_groupbox = self.init_ai_groupbox()

        controls_layout = QGridLayout()
        controls_layout.addWidget(self.switch_sides_button, 0, 0)
        controls_layout.addWidget(self.copy_to_tb_button, 0, 1)
        controls_layout.addWidget(self.remove_button, 0, 2)
        controls_layout.addWidget(self.clear_button, 0, 3)
        controls_layout.addWidget(self.search_bar, 1, 0, 1, 4)
        controls_layout.addWidget(self.search_view, 2, 0, 1, 4)
        controls_layout.addWidget(ai_groupbox, 0, 5, 3, 1)

        self.layout.addLayout(controls_layout, 3, 0, 1, 2)

    # Lays out the hero boxes of some selection type into a self
    # contained groupbox.
    def group_hero_boxes(self, hero_boxes):
        groupbox = QGroupBox()
        layout = QGridLayout(groupbox)
        for i, hero_box in enumerate(hero_boxes):
            layout.addWidget(hero_box, 0, i, Qt.AlignCenter)
            # add ban overlay for all bans
            if hasattr(hero_box, "ban_overlay"):
                layout.addWidget(hero_box.ban_overlay, 0, i, Qt.AlignCenter)
            # add value label to bottom left corner
            layout.addWidget(hero_box.value_label, 0, i, Qt.AlignLeft | Qt.AlignBottom)
        set_hero_box_layout_sizes(HERO_BOX_SIZE, layout, [0], list(range(len(hero_boxes))))
        groupbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return groupbox

    # Groups together the run ai search button and hero boxes to display the
    # optimal selections. @Later can contain total number of states and the
    # optimal value.
    def init_ai_groupbox(self):
        ai_groupbox = QGroupBox()
        layout = QGridLayout(ai_groupbox)
        layout.addWidget(self.run_search_button, 0, 0, 1, 2, Qt.AlignTop | Qt.AlignHCenter)
        layout.addWidget(self.optimal_hero_boxes[0], 1, 0, 10, 1, Qt.AlignCenter)
        layout.addWidget(self.optimal_hero_boxes[1], 1, 1, 10, 1, Qt.AlignCenter)
        return ai_groupbox

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

        # validate history with new rewards
        history = self.get_history()
        for hero_box in self.hero_boxes:
            hero_box.clear()
            if hero_box.selected:
                selected_index = hero_box.index
        stage = 0
        for hero in history:
            # check if hero is still selectable with history before it
            selectable = self.draft_ai.selectable_heroes(history[:stage])
            if hero not in selectable:
                break
            self.hero_boxes[stage].set_hero(hero)
            stage += 1
        # keep users old selection so long as it's either next one
        # needing entered or before that
        if selected_index <= stage:
            self.change_selected_box(self.hero_boxes[selected_index])
        else:
            self.change_selected_box(self.hero_boxes[stage])

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
        if self.curr_team_A == TEAM_1:
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

    # Returns the history as a list of hero names based on the heroes
    # input into the hero boxes.
    def get_history(self):
        history = []
        for hero_box in self.hero_boxes:
            if not hero_box.name:
                break
            history.append(hero_box.name)
        return history

    # History length is needed by the clicked methods so providing this
    # method to stop the unnecessary creation of list objects.
    def get_history_len(self):
        history_len = 0
        for hero_box in self.hero_boxes:
            if not hero_box.name:
                break
            history_len += 1
        return history_len

    # Deselects the currently selected box and selects the given box so
    # long as it is either the next box needing to be entered or one
    # before that. The heroes in search are then enabled/disabled based
    # on whether or not they can be selected for the box's stage in the
    # format given the history.
    def change_selected_box(self, hero_box):
        history = self.get_history()
        assert hero_box.index <= len(history)

        for box in self.hero_boxes:
            box.set_selected(False)
        hero_box.set_selected(True)

        # ensure only selectable heroes are enabled in search
        selectable = self.draft_ai.selectable_heroes(history, hero_box.index)
        for row in range(self.search_model.rowCount()):
            item = self.search_model.item(row)
            item.setEnabled(item.text() in selectable)

        # as users can also select a hero in either optimal hero display,
        # these should only be enabled if selectable in selected position
        self.optimal_hero_boxes[0].setDisabled(self.optimal_hero_boxes[0].name != '' and 
                                               self.optimal_hero_boxes[0].name not in selectable)
        self.optimal_hero_boxes[1].setDisabled(self.optimal_hero_boxes[1].name != '' and 
                                               self.optimal_hero_boxes[1].name not in selectable)

        # enable remove button if box contains a hero
        if hero_box.name:
            self.remove_button.setEnabled(True)
        else:
            self.remove_button.setEnabled(False)

    # To be called whenever the draft history changes in anyway (including the team
    # having selected the heroes), passing in the stage where the history is first
    # changed from what it previously was. Handles all the necessary logic for such
    # a change.
    def history_changed(self, change_stage, hero=None):
        self.update_optimal_boxes_next_selection_color()

        # Clear the value labels for all selections after the point where the draft
        # history changes because they are no longer valid. The value label for the
        # selection where a change first occurred is still valid because it depends
        # only on the history before its selection.
        for hero_box in self.hero_boxes[change_stage + 1:]:
            hero_box.value_label.clear()

        if hero is not None:
            self.update_next_value_label(change_stage, hero)

        # Unable to run search if draft history is full.
        selection_stage = self.get_history_len()
        if selection_stage == len(self.draft_format):
            self.run_search_button.setDisabled(True)
            self.optimal_hero_boxes[0].clear()
            self.optimal_hero_boxes[1].clear()
            return

        # If search has previously been run for the given history then display
        # optimal results and disable functionality to run search again, else
        # clear optimal displays and allow search to be run.
        search_result = self.hero_boxes[selection_stage].value_label.search_result
        if search_result is not None:
            self.run_search_button.setDisabled(True)
            self.optimal_hero_boxes[0].set_hero(search_result[1])
            if len(search_result) == 3:
                self.optimal_hero_boxes[1].set_hero(search_result[2])
            else:
                self.optimal_hero_boxes[1].clear()
        else:
            self.run_search_button.setEnabled(True)
            self.optimal_hero_boxes[0].clear()
            self.optimal_hero_boxes[1].clear()

    # Changes the colours of the optimal hero selection boxes to reflect which team
    # has the next selection(s) to highlight what the returned heroes from running
    # the AI would represent.
    def update_optimal_boxes_next_selection_color(self):
        stage = self.get_history_len()
        if stage == len(self.draft_format):
            # no more selections for either team 
            self.optimal_hero_boxes[0].setStyleSheet(None)
            self.optimal_hero_boxes[1].setStyleSheet(None)
            return
        side = self.draft_format[stage][0]
        if self.curr_team_A == TEAM_1:
            team_color = TEAM_1_COLOR if side == A else TEAM_2_COLOR
        else:
            team_color = TEAM_2_COLOR if side == A else TEAM_1_COLOR
        self.optimal_hero_boxes[0].setStyleSheet(f"background-color: {team_color.name()}")
        if side == self.draft_format[(stage + 1) % len(self.draft_format)][0]:
            # double selection
            self.optimal_hero_boxes[1].setStyleSheet(f"background-color: {team_color.name()}")
        else:
            # single selection
            self.optimal_hero_boxes[1].setStyleSheet(None)

    # Checks if the hero being selected is part of a double selection where the
    # optimal selections have been saved from running the AI and therefore updates
    # the optimal value (and selection) of the next selection as search does not
    # need to be run again.
    def update_next_value_label(self, stage, selected_hero):
        search_result = self.hero_boxes[stage].value_label.search_result
        if search_result is None or len(search_result) == 2:
            # no saved result or single selection so nothing to update
            return
        elif self.draft_format[stage][1] == self.draft_format[stage + 1][1]:
            # selecting team has two selections of the same type so either hero
            # could be selected
            if selected_hero == search_result[1]:
                next_result = (search_result[0], search_result[2])
                self.hero_boxes[stage + 1].value_label.set_search_result(next_result)
            elif selected_hero == search_result[2]:
                next_result = (search_result[0], search_result[1])
                self.hero_boxes[stage + 1].value_label.set_search_result(next_result)
        else:
            # selecting team has two selections of a different type so must be
            # selected in order
            if selected_hero == search_result[1]:
                next_result = (search_result[0], search_result[2])
                self.hero_boxes[stage + 1].value_label.set_search_result(next_result)

    # Change the selected box so long as it is next one needing entered
    # or one before that.
    @Slot()
    def hero_box_clicked(self, hero_name):
        clicked_box = self.sender()
        if clicked_box.index <= self.get_history_len():
            self.change_selected_box(clicked_box)

    @Slot()
    def search_hero_clicked(self, f_index):
        index = self.search_f_model.mapToSource(f_index)
        search_item = self.search_model.itemFromIndex(index)
        if not search_item.isEnabled():
            # display tool tip if disabled because of no open role
            hero_name = search_item.text()
            if hero_name not in self.get_history():
                QToolTip.showText(
                    QCursor.pos(),
                    f"{hero_name} has no available role for the selecting team.",
                )
            return

        # find the selected hero box and set its hero to clicked item
        for hero_box in self.hero_boxes:
            if hero_box.selected:
                selected_stage = hero_box.index
                # not using set_hero_from_search_item because the item should
                # not be disabled if selection stays on this box and if not
                # then change_selected_box will handle enabling and disabling
                hero_box.set_hero(search_item.text())
                update_ban_icon(hero_box, self.ban_icons)
                break
        self.search_view.clearSelection()

        self.history_changed(selected_stage, search_item.text())

        # move selection to next empty stage unless all have been entered
        history_len = self.get_history_len()
        if history_len < len(self.draft_format):
            self.change_selected_box(self.hero_boxes[history_len])
        else:
            self.change_selected_box(self.hero_boxes[history_len - 1])  # so remove button becomes enabled


    # Clears all hero boxes and sets the first box as the selected box.
    @Slot()
    def clear_button_clicked(self):
        for hero_box in self.hero_boxes:
            hero_box.clear()
            update_ban_icon(hero_box, self.ban_icons)
        self.change_selected_box(self.hero_boxes[0])  # handles the enabling/disabling of search items
        self.history_changed(0)

    # Find selected box and remove it and all heroes after it in the
    # draft history as it should not contain gaps.
    @Slot()
    def remove_button_clicked(self):
        remove = False
        for hero_box in self.hero_boxes:
            if hero_box.selected:
                selected_box = hero_box
                remove = True
            if remove:
                hero_box.clear()
                update_ban_icon(hero_box, self.ban_icons)
        self.change_selected_box(selected_box)  # selection is same, but legal search heroes need updated
        self.history_changed(selected_box.index)

    # Switches the team playing as A, updating the labels and calling
    # to update the draft ai. @Later this will need to check for a
    # saved TT to load the new draft ai with.
    @Slot()
    def switch_sides_button_clicked(self):
        if self.curr_team_A == TEAM_1:
            self.curr_team_A = TEAM_2
            self.team_A_label.setText(self.team_tags[1])
            self.team_B_label.setText(self.team_tags[0])
        else:
            self.curr_team_A = TEAM_1
            self.team_A_label.setText(self.team_tags[0])
            self.team_B_label.setText(self.team_tags[1])
        for hero_box in self.hero_boxes:
            hero_box.value_label.clear()
            hero_box.value_label.update_color()
        self.update_draft_ai()
        self.history_changed(-1)  # -1 to indicate that all value labels (including first) are
                                  # invalid and should be cleared

    # Has DraftAI determine current optimal roles for each hero in
    # both teams for the current point in history, sets them to the
    # team builder then automatically switches to that tab.
    @Slot()
    def copy_to_tb_button_clicked(self):
        history = self.get_history()
        if len(history) == 0:
            team_1 = []
            team_2 = []
        else:
            # ensure consistency with a possible returned AI search value and
            # the value displayed in TB by having role assignments chosen based
            # on the team to have selected last getting a guaranteed value
            unexploitable, _ = self.draft_format[len(history) - 1]
            team_A_asgmt, team_B_asgmt = self.draft_ai.optimal_role_asgmts(
                history,
                unexploitable,
            )

            def switch_ai_roles(asgmt):
                ui_asgmt = []
                for name, ai_role in asgmt:
                    ui_asgmt.append((name, self.roles[ai_role]))
                return ui_asgmt

            if self.curr_team_A == TEAM_1:
                team_1 = switch_ai_roles(team_A_asgmt)
                team_2 = switch_ai_roles(team_B_asgmt)
            else:
                team_1 = switch_ai_roles(team_B_asgmt)
                team_2 = switch_ai_roles(team_A_asgmt)
        self.team_builder.set_all_hero_boxes(team_1, team_2)
        self.parent().parent().setCurrentIndex(0)  # first parent gives stacked widget, second gives tab

    @Slot()
    def run_search_button_clicked(self):
        history = self.get_history()
        assert len(history) < len(self.draft_format)
        # move user selection to where search is being run from (next draft selection)
        if not self.hero_boxes[len(history)].selected:
            self.change_selected_box(self.hero_boxes[len(history)])
        search_result = self.draft_ai.run_search(history)
        # check for incomplete search
        if search_result[0] == INF or search_result[0] == -INF:
            msg_box = QMessageBox(self)
            msg_box.setText("Insufficient champions for finding the optimal selection(s).")
            msg_box.setInformativeText("There exists a selection of champions such that (at least) one" \
                                       " team cannot secure a champion for each role. Try adding more " \
                                       "role rewards.")
            msg_box.exec()
            return
        # scale the integer values between 0 and 1000 used by the AI to floats between 0 and 10
        updated_search_result = (search_result[0] / 100, search_result[1])
        updated_search_result += () if len(search_result) == 2 else (search_result[2],)
        # set optimal value for current selection
        self.hero_boxes[len(history)].value_label.set_search_result(updated_search_result)
        # display optimal selection(s)
        self.optimal_hero_boxes[0].set_hero(updated_search_result[1])
        if len(updated_search_result) == 3:
            self.optimal_hero_boxes[1].set_hero(updated_search_result[2])
        self.run_search_button.setDisabled(True)

    @Slot()
    def optimal_hero_box_clicked(self, hero_name):
        if not hero_name:
            return
        # @CopyPaste
        # find selected draft hero box and set to hero in clicked optimal display
        for hero_box in self.hero_boxes:
            if hero_box.selected:
                selected_stage = hero_box.index
                hero_box.set_hero(hero_name)
                update_ban_icon(hero_box, self.ban_icons)
                break
        self.history_changed(selected_stage, hero_name)
        # move selection to next empty stage unless all have been entered
        history_len = self.get_history_len()
        if history_len < len(self.draft_format):
            self.change_selected_box(self.hero_boxes[history_len])
        else:
            self.change_selected_box(self.hero_boxes[history_len - 1])  # so remove button becomes enabled


class SummaryDialog(QDialog):
    """
    A dialog displaying the optimal value and selection(s) returned form
    an AI search for a given draft history.
    """

    def __init__(self, draft_page):
        super().__init__()

        self.draft_page = draft_page

        self.hero_boxes = []
        for i in range(len(draft_page.draft_format)):
            hero_box = HeroBox(draft_page.hero_icons, HERO_BOX_SIZE * 0.5)
            self.hero_boxes.append(hero_box)
            hero_box.index = i

        # separate hero boxes by selection type and initialise a BanOverlay for all bans
        boxes = {(A, PICK): [], (B, PICK): [], (A, BAN): [], (B, BAN): []}
        for hero_box, selection in zip(self.hero_boxes, draft_page.draft_format):
            if selection[1] == BAN:
                hero_box.ban_overlay = BanOverlay(hero_box)
                update_ban_icon(hero_box, draft_page.ban_icons)
            boxes[selection].append(hero_box)

        self.description = "Optimal selection(s) for {} in the current draft that will secure " \
                           "the most reward in the worst case scenario (that is, no matter how" \
                           " the opponents responsd):" 
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.value_lcd = QLCDNumber(6)
        self.optimal_hero_boxes = (HeroBox(draft_page.hero_icons, HERO_BOX_SIZE), 
                                   HeroBox(draft_page.hero_icons, HERO_BOX_SIZE)) 

        layout = QGridLayout(self)
        layout.addWidget(self.group_display_hero_boxes(boxes[(A, PICK)]), 1, 0)
        layout.addWidget(self.group_display_hero_boxes(boxes[(B, PICK)]), 1, 1)
        layout.addWidget(self.group_display_hero_boxes(boxes[(A, BAN)]), 2, 0)
        layout.addWidget(self.group_display_hero_boxes(boxes[(B, BAN)]), 2, 1)
        summary_layout = QHBoxLayout()
        summary_layout.addWidget(self.description_label)
        summary_layout.addWidget(self.value_lcd)
        summary_layout.addWidget(self.optimal_hero_boxes[0])
        summary_layout.addWidget(self.optimal_hero_boxes[1])
        summary_layout.setStretch(0, 4)
        summary_layout.setStretch(1, 5)
        summary_layout.setStretch(2, 2)
        summary_layout.setStretch(3, 2)
        layout.addLayout(summary_layout, 3, 0, 1, 2)

        self.setWindowFlags(Qt.Popup)

    def group_display_hero_boxes(self, hero_boxes):
        groupbox = QGroupBox()
        layout = QGridLayout(groupbox)
        for i, hero_box in enumerate(hero_boxes):
            layout.addWidget(hero_box, 0, i, Qt.AlignCenter)
            # add ban overlay for all bans
            if hasattr(hero_box, "ban_overlay"):
                layout.addWidget(hero_box.ban_overlay, 0, i, Qt.AlignCenter)
        groupbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return groupbox

    # Set the desired information and then show dialog to display summary.
    def display(self, stage, search_result):
        # Find selecting team's colour and tag.
        selecting_side = self.draft_page.draft_format[stage][0]
        if self.draft_page.curr_team_A == TEAM_1:
            if selecting_side == A:
                color = TEAM_1_COLOR
                tag = self.draft_page.team_tags[0]
            else:
                color = TEAM_2_COLOR
                tag = self.draft_page.team_tags[1]
        else:
            if selecting_side == A:
                color = TEAM_2_COLOR
                tag = self.draft_page.team_tags[1]
            else:
                color = TEAM_1_COLOR
                tag = self.draft_page.team_tags[0]

        # Copy history up to the stage where search was run.
        for i, hero_box in enumerate(self.hero_boxes):
            if i < stage:
                hero_box.set_hero(self.draft_page.hero_boxes[i].name)
                update_ban_icon(hero_box, self.draft_page.ban_icons)
            else:
                hero_box.clear()
                update_ban_icon(hero_box, self.draft_page.ban_icons)
            hero_box.setStyleSheet(None)

        # Set description to include the selecting team's tag.
        self.description_label.setText(self.description.format(tag))

        # Highlight next selection boxes.
        self.hero_boxes[stage].setStyleSheet(f"background-color: {color.name()}")
        if len(search_result) == 3:
            self.hero_boxes[stage + 1].setStyleSheet(f"background-color: {color.name()}")

        # Set optimal value.
        self.value_lcd.display(search_result[0]) 
        palette = self.value_lcd.palette()
        palette.setColor(palette.WindowText, color)
        self.value_lcd.setPalette(palette)

        # Set optimal selection(s).
        self.optimal_hero_boxes[0].set_hero(search_result[1])
        self.optimal_hero_boxes[0].setStyleSheet(f"background-color: {color.name()}")
        if len(search_result) == 3:
            self.optimal_hero_boxes[1].set_hero(search_result[2])
            self.optimal_hero_boxes[1].setStyleSheet(f"background-color: {color.name()}")
        else:
            self.optimal_hero_boxes[1].clear()
            self.optimal_hero_boxes[1].setStyleSheet(None)

        self.show()


class BanOverlay(QLabel):
    """
    Used to display a ban indicator on top of a hero box where all clicks
    redirect to the hero box being overlaid.
    """

    def __init__(self, hero_box):
        super().__init__()

        self.hero_box = hero_box

    def mousePressEvent(self, event):
        self.hero_box.clicked.emit(self.hero_box.name)

    def mouseDoubleClickEvent(self, event):
        self.hero_box.doubleClicked.emit(self.hero_box.name)

    def sizeHint(self):
        return self.hero_box.sizeHint()


class ValueLabel(QLabel):
    """
    Used to hold an optimal value (returned by AI) that is possible to achieve
    for the slecting team in the displayed draft (held in draft_page) at the
    given hero box's corresponding stage in the draft.
    """

    def __init__(self, hero_box, draft_page):
        super().__init__()

        self.hero_box = hero_box
        self.draft_page = draft_page
        self.side = draft_page.draft_format[hero_box.index][0]
        self.search_result = None  # the optimal value and selection(s) returned from running AI search
                                   # for the selection that this value label is associated with
        self.setAlignment(Qt.AlignCenter)
        self.setFrameStyle(QFrame.Panel | QFrame.Plain)
        self.setLineWidth(1)
        self.setFixedSize(HERO_BOX_SIZE * 0.40)
        self.margin = hero_box.frameWidth() * 2  # add margin so it doesn't overlap with hero box frame
        self.update_color()

    def set_search_result(self, search_result):
        self.search_result = search_result
        self.setText(str(search_result[0]))

    def clear(self):
        self.search_result = None
        self.setText(None)

    def update_color(self):
        if self.draft_page.curr_team_A == TEAM_1:
            color = TEAM_1_COLOR if self.side == A else TEAM_2_COLOR
        else:
            color = TEAM_2_COLOR if self.side == A else TEAM_1_COLOR
        self.setStyleSheet(f"background-color: {color.name()}; margin: {self.margin}px")

    def mousePressEvent(self, event):
        if self.search_result is not None:
            self.draft_page.summary_dialog.display(self.hero_box.index, self.search_result)
        else:
            # display tool tip describing the purpose of the value label
            QToolTip.showText(
                QCursor.pos(),
                "After search is run from the current position this will store the minimum " \
                "guaranteed reward for the selecting team if selecting optimally.",
            )
