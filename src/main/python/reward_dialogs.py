from PySide6.QtWidgets import QDialog


class RoleRewardDialog(QDialog):

    def __init__(self, model, hero_icons, team_tags, parent):
        super().__init__(parent)

    def open_add(self):
        QDialog.open(self)
