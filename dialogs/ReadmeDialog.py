# GUI imports
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import Qt
import logging
import os


class ReadmeDialog(QMainWindow):
    """
    Dialog used to display README.md file from program root.
    """
    def __init__(self, basedir):
        self.basedir = basedir 
        super().__init__()
        logging.info("User opened ReadMeDialog")
        self.setWindowTitle("Read Me")
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarContextHelpButton))

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setMinimumSize(500, 500)
        self.setCentralWidget(self.text_edit)
        try:
            with open(os.path.join(basedir, "README.md"), "r") as readme_file:
                self.text_edit.setMarkdown(readme_file.read())
        except FileNotFoundError:  # gracefully fail if file not present
            self.text_edit.setText(f"Unable to locate README.md file in program root folder {basedir}.")
