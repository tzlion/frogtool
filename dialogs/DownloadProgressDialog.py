# GUI imports
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import Qt

class DownloadProgressDialog(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        grid_layout = self.layout()

        qt_msgboxex_icon_label = self.findChild(QLabel, "qt_msgboxex_icon_label")
        qt_msgboxex_icon_label.deleteLater()

        qt_msgbox_label = self.findChild(QLabel, "qt_msgbox_label")
        qt_msgbox_label.setAlignment(Qt.AlignCenter)
        grid_layout.removeWidget(qt_msgbox_label)

        qt_msgbox_buttonbox = self.findChild(QDialogButtonBox, "qt_msgbox_buttonbox")
        grid_layout.removeWidget(qt_msgbox_buttonbox)
        
        self.setStyleSheet("QLabel{min-width: 300px}")
        self.setWindowFlags(Qt.CustomizeWindowHint)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        # Create a dialog for progress
        self.progress = QProgressBar()
        self.progress.setFixedWidth(300)

        self.spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        grid_layout.addItem(self.spacer, 0, 0, 1, self.layout().columnCount())
        grid_layout.addWidget(qt_msgbox_label, 1, 0, alignment=Qt.AlignCenter)
        # Add the progress bar at the bottom (last row + 1) and first column with column span
        grid_layout.addWidget(self.progress,2, 0, 1, grid_layout.columnCount(), Qt.AlignCenter )
        grid_layout.addWidget(qt_msgbox_buttonbox, 3, 0, alignment=Qt.AlignCenter)
        qt_msgbox_buttonbox.hide()
    
    def setText(self, text):
        super().setText(text)
        
        longest = ""
        for part in text.split("\n"):
            if len(part) > len(longest):
                longest = part
        
        font_matrix = self.fontMetrics()
        width = font_matrix.boundingRect(longest).width() + 8 # Have to add ~20 as a buffer
        self.spacer = QSpacerItem(width, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.layout().addItem(self.spacer, 0, 0, 1, self.layout().columnCount())
        
    def showProgress(self, progressValue, refreshBoolean):
        #start_time = time.time()
        self.progress.setValue(progressValue)
        #TODO: This really is tough on long calls on performance, let's only do it when needed
        if refreshBoolean:
            QApplication.processEvents()

    def setDrive(self,drive):
        self.drive = drive
        self.setWindowTitle(f"Change System Shortcuts - {drive}") 
