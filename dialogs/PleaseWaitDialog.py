# GUI imports
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

class PleaseWaitDialog(QMainWindow):
    """
    Dialog used to stop interaction while something is happening from program root.
    """
    def __init__(self, message: str = ""):
        super().__init__()

        self.setWindowTitle("Please Wait")
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        
        self.lbl = QLabel(self)
        #self.text_edit.setFixedSize(500, 500)
        self.setCentralWidget(self.lbl)
        self.lbl.setText(message)
        
    def setMessage(self, message: str = ""):
        self.lbl.setText(message)