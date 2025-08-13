import sys
import os
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThreadPool, QRunnable, pyqtSignal, QObject
from PyQt5 import uic
import simc_gv_generator as ggv
import simc_gv_sims as sim

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class MainWindow(QtWidgets.QMainWindow):
    rewards = []
    simc_import = ""
    start_end = [0, 0]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ui_file = resource_path("simc_import.ui")
        uic.loadUi(ui_file, self)
        self.gatherVaultBtn.clicked.connect(self.on_gather_vault_click)
        self.removeItemBtn.clicked.connect(self.remove_vault_item)
        self.runSimBtn.clicked.connect(self.run_sim)
        self.threadpool = QThreadPool()  # Initialize thread pool

    def run_sim(self):
        """Runs SimC in a separate thread to keep the UI responsive."""
        if not self.rewards or not self.simc_import or not self.start_end:
            self.bestItemLine.setText("Error: Missing parameters.")
            return

        self.bestItemLine.setText("Running Sim...")

        # Create worker and connect signals
        worker = SimWorker(self.rewards, self.simc_import, self.start_end[0], self.start_end[1])
        worker.signals.finished.connect(self.update_results)  # Update UI when done

        # Run the worker thread
        self.threadpool.start(worker)

    def update_results(self, best_item):
        """Updates the UI with the best item result."""
        self.bestItemLine.setText(f"{best_item[0]}")
        self.estDPSLine.setText(f"{'%.2f' % best_item[1]}")

    def remove_vault_item(self):
        row_num = self.vaultItemList.currentRow()
        if row_num < 0:
            return
        self.rewards.pop(row_num)
        self.vaultItemList.takeItem(row_num)

    def on_gather_vault_click(self):
        import_string = self.simcImportStringText.toPlainText()
        vals = ggv.generate_vault_rewards_from_file(import_string)
        if vals == None:
            print("Empty string inputted")
            return
        if vals.count == 0:
            print("WR404-WR Not found or empty")
            return
        rewards = []
        rewards = vals[0]
        self.simc_import = vals[1]
        self.start_end[0] = vals[2]
        self.start_end[1] = vals[3]
        self.rewards = rewards
        x = 0
        for reward in rewards:
            x = x + 1
            print(f"[{x}] {reward[0]}")
            self.vaultItemList.insertItem(x,reward[0])

# TODO Move to own class file                    
# Worker Signals
class WorkerSignals(QObject):
    finished = pyqtSignal(tuple)  # Signal to send best item results back

# Worker Thread Class
class SimWorker(QRunnable):
    def __init__(self, rewards, simc_import, start_idx, end_idx):
        super().__init__()
        self.signals = WorkerSignals()
        self.rewards = rewards
        self.simc_import = simc_import
        self.start_idx = start_idx
        self.end_idx = end_idx

    def run(self):
        """Runs SimC generation and best item calculation in the background."""
        ggv.generate_mod_simc_file(self.rewards, self.simc_import, self.start_idx, self.end_idx)
        best_item = sim.run_simc_against_vault()
        self.signals.finished.emit(best_item)  # Send result back to the main thread

app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()