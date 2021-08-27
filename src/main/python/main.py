from fbs_runtime.application_context.PySide6 import ApplicationContext
from PySide6.QtWidgets import QMainWindow, QTableView, QWidget, QVBoxLayout, QLineEdit, QPushButton, QAbstractItemView
from PySide6.QtCore import Slot, QItemSelectionModel

import sys
import random

from rewards import RoleRewardsModel


# @Temp heroes while I focus on building main structure. Will need a
# way to select game and load in all heroes @Later.
all_heroes = [
    'Aatrox', 'Ahri', 'Akali', 'Akshan',
    'Alistar', 'Amumu', 'Anivia', 'Annie',
    'Aphelios', 'Ashe', 'AurelionSol', 'Azir',
    'Bard', 'Blitzcrank', 'Brand', 'Braum',
]


class TestWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.role_model = RoleRewardsModel(all_heroes, 'FNC', 'G2')
        self.role_view = QTableView()
        self.role_view.setModel(self.role_model)
        self.role_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.role_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.addWidget(self.role_view)

        # test sorting
        self.role_view.setSortingEnabled(True)

        # test filtering
        self.filter_bar = QLineEdit()
        self.main_layout.addWidget(self.filter_bar)
        self.filter_bar.textChanged.connect(self.role_model.filter_rewards)

        # test adding
        self.add_button = QPushButton("add random reward")
        self.main_layout.addWidget(self.add_button)
        self.add_button.clicked.connect(self.add_random_reward)

        # test deleting
        self.delete_button = QPushButton("delete selected rewards")
        self.main_layout.addWidget(self.delete_button)
        self.delete_button.clicked.connect(self.delete)

    @Slot()
    def add_random_reward(self):
        self.role_model.add_reward(
            random.choice(all_heroes),
            random.choice(('Top', 'Jungle', 'Mid', 'Support', 'Bot')),
            random.randrange(0, 1000) / 100,
            random.randrange(0, 1000) / 100,
        )

    @Slot()
    def delete(self):
        selection_model = self.role_view.selectionModel()
        indexes = selection_model.selectedRows()
        self.role_model.delete_rewards(indexes)

if __name__ == '__main__':
    appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext
    window = TestWindow()
    window.resize(1600, 800)
    window.show()
    exit_code = appctxt.app.exec()      # 2. Invoke appctxt.app.exec()
    sys.exit(exit_code)
