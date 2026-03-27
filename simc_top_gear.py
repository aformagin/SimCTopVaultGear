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
    all_dps_results = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ui_file = resource_path("simc_import.ui")
        uic.loadUi(ui_file, self)
        self.gatherVaultBtn.clicked.connect(self.on_gather_vault_click)
        self.removeItemBtn.clicked.connect(self.remove_vault_item)
        self.clearItemsBtn.clicked.connect(self.clear_vault_items)
        self.runSimBtn.clicked.connect(self.run_sim)
        self.detailsBtn.clicked.connect(self.show_dps_details)
        self.detailsBtn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
        self.threadpool = QThreadPool()  # Initialize thread pool

    def run_sim(self):
        """Runs SimC in a separate thread to keep the UI responsive."""
        if not self.rewards or not self.simc_import:
            self.bestItemLine.setText("Error: Missing parameters.")
            return

        self.bestItemLine.setText("Running Sim...")

        # Create worker and connect signals
        worker = SimWorker(self.rewards, self.simc_import)
        worker.signals.finished.connect(self.update_results)  # Update UI when done

        # Run the worker thread
        self.threadpool.start(worker)

    def update_results(self, result):
        """Updates the UI with the best item result and stores all DPS data."""
        best_item, all_results = result
        if best_item:
            self.bestItemLine.setText(f"{best_item[0]}")
            self.estDPSLine.setText(f"{'%.2f' % best_item[1]}")
        self.all_dps_results = all_results
        self.detailsBtn.setEnabled(True)

    def show_dps_details(self):
        """Opens a window listing every simmed item's mean DPS, greatest to least,
        with the baseline (currently equipped gear) shown at the top."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("DPS Breakdown")
        dialog.setMinimumWidth(420)

        layout = QtWidgets.QVBoxLayout(dialog)

        baseline = next((r for r in self.all_dps_results if r[0] == "Baseline"), None)
        items = sorted(
            [r for r in self.all_dps_results if r[0] != "Baseline"],
            key=lambda x: x[1], reverse=True
        )

        if baseline:
            baseline_label = QtWidgets.QLabel(f"Baseline (Equipped):  {baseline[1]:,.2f} DPS")
            baseline_label.setStyleSheet(
                "font-weight: bold; font-size: 12px; padding: 6px;"
                "background: #222; color: #ddd; border-radius: 4px;"
            )
            layout.addWidget(baseline_label)

        table = QtWidgets.QTableWidget(len(items), 3)
        table.setHorizontalHeaderLabels(["Item", "Mean DPS", "vs. Baseline"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.verticalHeader().setVisible(False)

        baseline_dps = baseline[1] if baseline else None
        for i, (name, mean, *_) in enumerate(items):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(name))
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{mean:,.2f}"))
            if baseline_dps is not None:
                diff = mean - baseline_dps
                diff_item = QtWidgets.QTableWidgetItem(f"{diff:+,.2f}")
                diff_item.setForeground(
                    QtGui.QColor("#00c000") if diff >= 0 else QtGui.QColor("#e03030")
                )
                table.setItem(i, 2, diff_item)

        table.resizeColumnsToContents()
        layout.addWidget(table)
        dialog.exec_()

    def clear_vault_items(self):
        self.rewards = []
        self.vaultItemList.clear()

    def remove_vault_item(self):
        row_num = self.vaultItemList.currentRow()
        if row_num < 0:
            return
        self.rewards.pop(row_num)
        self.vaultItemList.takeItem(row_num)

    def on_gather_vault_click(self):
        import_string = self.simcImportStringText.toPlainText()
        include_bags = self.includeBagsCheckBox.isChecked()
        vals = ggv.generate_vault_rewards_from_file(import_string, include_bags=include_bags)
        if vals == None:
            print("Empty string inputted")
            return
        if vals.count == 0:
            print("WR404-WR Not found or empty")
            return
        self.clear_vault_items()
        rewards = vals[0]
        self.simc_import = vals[1]
        self.start_end[0] = vals[2]
        self.start_end[1] = vals[3]
        self.rewards = rewards
        x = 0
        for reward in rewards:
            x = x + 1
            print(f"[{x}] {reward[0]}")
            self.vaultItemList.insertItem(x, reward[0])

# TODO Move to own class file                    
# Worker Signals
class WorkerSignals(QObject):
    finished = pyqtSignal(object)  # Carries (best_item, all_sorted_results) from the sim run

# Worker Thread Class
class SimWorker(QRunnable):
    def __init__(self, rewards, simc_import):
        super().__init__()
        self.signals = WorkerSignals()
        self.rewards = rewards
        self.simc_import = simc_import

    def run(self):
        """Runs SimC generation and best item calculation in the background."""
        ggv.generate_mod_simc_file(self.rewards, self.simc_import)
        result = sim.run_simc_against_vault()
        if result[0] is not None:
            self.signals.finished.emit(result)  # Send result back to the main thread

app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()