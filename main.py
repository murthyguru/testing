import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WireTap Application")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("http://0.0.0.0:5010"))  # Flask app URL
        self.browser.setZoomFactor(2.0)
        layout.addWidget(self.browser)

        self.setCentralWidget(central_widget)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

