import sys
import os
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThreadPool, QRunnable, pyqtSignal, QObject

import simc_gv_generator as ggv
import simc_gv_sims as sim
from simc_gv_generator import parse_simc_addon
from profileset_generator import SimOptions, count_top_gear_combinations
from top_gear_engine import run_top_gear, TopGearConfig, run_simc_with_input
from result_parser import parse_results
from drop_finder_engine import (
    load_drop_sources,
    get_instances,
    get_encounters,
    get_encounter_items,
    get_ilvl_tracks,
    loot_items_to_parsed,
    generate_droptimizer_input as dfe_generate_input,
)


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

DARK_STYLESHEET = """
    QWidget { background-color: #1a1a1a; color: #d8d8d8; }
    QWidget#centralwidget { border: 1px solid #2e2e2e; }
    QGroupBox {
        color: #c0c0c0;
        border: 1px solid #272727;
        border-radius: 6px;
        margin-top: 10px;
        padding: 6px 4px 4px 4px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        color: #c0c0c0;
        padding: 0 6px;
        background: #1a1a1a;
    }
    QCheckBox { color: #b8b8b8; background: transparent; }
    QCheckBox::indicator {
        width: 13px; height: 13px;
        border: 1px solid #484848;
        border-radius: 3px;
        background: #222222;
    }
    QCheckBox::indicator:checked { background: #7a1515; border-color: #9e2020; }
    QCheckBox::indicator:hover { border-color: #666666; }
    QLineEdit {
        background: #222222; color: #d8d8d8;
        border: 1px solid #333333; border-radius: 4px; padding: 2px 6px;
    }
    QLineEdit:focus { border-color: #505050; }
    QTextEdit {
        background: #222222; color: #c0c0c0;
        border: 1px solid #333333; border-radius: 4px;
        selection-background-color: #1e3a6a;
    }
    QListWidget {
        background: #222222; color: #c0c0c0;
        border: 1px solid #333333; border-radius: 4px; outline: none;
    }
    QListWidget::item { padding: 3px 6px; border-radius: 2px; }
    QListWidget::item:selected { background: #1e3050; color: #e0e0e0; }
    QListWidget::item:hover:!selected { background: #272727; }
    QScrollBar:vertical {
        background: #1a1a1a; width: 6px; border-radius: 3px; margin: 0;
    }
    QScrollBar::handle:vertical { background: #3a3a3a; border-radius: 3px; min-height: 24px; }
    QScrollBar::handle:vertical:hover { background: #555555; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar:horizontal {
        background: #1a1a1a; height: 6px; border-radius: 3px; margin: 0;
    }
    QScrollBar::handle:horizontal { background: #3a3a3a; border-radius: 3px; min-width: 24px; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    QDialog { background: #1a1a1a; border: 1px solid #2e2e2e; }
    QTableWidget {
        background: #1e1e1e; color: #d8d8d8;
        gridline-color: #2a2a2a;
        border: 1px solid #2a2a2a; border-radius: 4px;
    }
    QHeaderView::section {
        background: #222222; color: #888888;
        border: none; border-bottom: 1px solid #2e2e2e; border-right: 1px solid #2e2e2e;
        padding: 5px 8px; font-weight: bold;
    }
    QTableWidget::item:selected { background: #1e3a6a; color: #ffffff; }
    QTableWidget { alternate-background-color: #202020; }
    QLabel { background: transparent; }
    QTabWidget::pane { border: 1px solid #272727; background: #1a1a1a; }
    QTabBar::tab {
        background: #1e1e1e; color: #777777;
        padding: 5px 20px;
        border: 1px solid #272727; border-bottom: none;
        border-radius: 4px 4px 0 0; margin-right: 2px;
    }
    QTabBar::tab:selected { background: #1a1a1a; color: #d0d0d0; }
    QTabBar::tab:hover:!selected { background: #272727; color: #aaaaaa; }
    QSpinBox, QDoubleSpinBox {
        background: #222222; color: #d8d8d8;
        border: 1px solid #333333; border-radius: 4px; padding: 2px 4px;
    }
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        background: #2a2a2a; border: none; width: 14px;
    }
    QComboBox {
        background: #222222; color: #d8d8d8;
        border: 1px solid #333333; border-radius: 4px; padding: 2px 6px;
    }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox QAbstractItemView {
        background: #222222; color: #d8d8d8;
        border: 1px solid #333333; selection-background-color: #1e3050;
    }
    QSplitter::handle { background: #272727; }
"""

BTN_RED = """
    QPushButton {color: #d8d8d8; background: #6e1212; border-radius: 4px; border: none; padding: 3px 8px;}
    QPushButton:hover {color: white; background: #922020;}
    QPushButton:disabled {color: #3a3a3a; background: #2a1a1a; border: 1px solid #2a2a2a;}
    QPushButton:hover:pressed {color: #bbbbbb; background: #4e0d0d;}
"""
BTN_GREEN = """
    QPushButton {color: #d8d8d8; background: #155228; border-radius: 5px; border: none; padding: 4px 14px;}
    QPushButton:hover {color: white; background: #1d7038;}
    QPushButton:disabled {color: #3a3a3a; background: #1e1e1e; border: 1px solid #2a2a2a;}
    QPushButton:hover:pressed {color: #bbbbbb; background: #0e3a1c;}
"""
BTN_BLUE = """
    QPushButton {color: #c0d0e8; background: #0e2444; border-radius: 4px; border: none; padding: 3px 8px;}
    QPushButton:hover {color: white; background: #163a70;}
    QPushButton:disabled {color: #303030; background: #1a1a1a; border: 1px solid #252525;}
    QPushButton:hover:pressed {color: #aaaaaa; background: #091830;}
"""


# ---------------------------------------------------------------------------
# Worker threads
# ---------------------------------------------------------------------------

class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)


class SimWorker(QRunnable):
    """Legacy Great Vault worker — runs one simc process per .simc file."""
    def __init__(self, rewards, simc_import):
        super().__init__()
        self.signals = WorkerSignals()
        self.rewards = rewards
        self.simc_import = simc_import

    def run(self):
        ggv.generate_mod_simc_file(self.rewards, self.simc_import)
        result = sim.run_simc_against_vault()
        if result[0] is not None:
            self.signals.finished.emit(result)


class TopGearWorker(QRunnable):
    """Worker for Top Gear — single simc run via profilesets."""
    def __init__(self, simc_text, config):
        super().__init__()
        self.signals = WorkerSignals()
        self.simc_text = simc_text
        self.config = config

    def run(self):
        try:
            result = run_top_gear(self.simc_text, self.config)
            self.signals.finished.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class DroptimizerWorker(QRunnable):
    """Worker for the real Drop Finder — sims loot-table items at a selected ilvl track."""
    def __init__(self, simc_text, parsed_items, options, exe):
        super().__init__()
        self.signals = WorkerSignals()
        self.simc_text = simc_text
        self.parsed_items = parsed_items
        self.options = options
        self.exe = exe

    def run(self):
        try:
            parse_result = parse_simc_addon(self.simc_text)
            simc_input, combo_meta = dfe_generate_input(
                parse_result, self.parsed_items, self.options
            )
            json_data = run_simc_with_input(simc_input, self.exe)
            sim_results = parse_results(json_data)
            self.signals.finished.emit((parse_result, sim_results, combo_meta))
        except Exception as exc:
            self.signals.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self._drag_pos = None
        self.threadpool = QThreadPool()

        # Shared parse state
        self._parse_result = None
        self._tg_bag_items = []

        # Real Drop Finder (Droptimizer) state
        try:
            self._dfe_sources = load_drop_sources()
        except FileNotFoundError:
            self._dfe_sources = None
        self._dfe_raw_items = []   # raw dicts from drop_sources.json
        self._dfe_items = []       # ParsedItem list for the current selection

        # Great Vault state
        self.rewards = []
        self.simc_import = ""
        self.start_end = [0, 0]
        self.all_dps_results = []

        self._build_ui()
        self._connect_signals()
        QtWidgets.QApplication.instance().setStyleSheet(DARK_STYLESHEET)

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        self.resize(860, 730)
        central = QtWidgets.QWidget()
        central.setObjectName("centralwidget")
        self.setCentralWidget(central)

        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_title_bar(root)

        body = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body)
        body_layout.setContentsMargins(10, 8, 10, 10)
        body_layout.setSpacing(6)
        root.addWidget(body)

        self._build_import_section(body_layout)

        self.tabs = QtWidgets.QTabWidget()
        body_layout.addWidget(self.tabs)

        self._build_great_vault_tab()
        self._build_drop_finder_tab()
        self._build_top_gear_tab()

    def _build_title_bar(self, layout):
        bar = QtWidgets.QWidget()
        bar.setFixedHeight(28)
        bar.setStyleSheet("background: #101010; border-bottom: 1px solid #272727;")

        lbl = QtWidgets.QLabel("VAULT GEAR SIM")
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setStyleSheet(
            "color: #d0d0d0; font-weight: bold; font-size: 8pt; background: transparent;"
        )

        self.exitBtn = QtWidgets.QPushButton("✕")
        self.exitBtn.setFixedSize(28, 20)
        self.exitBtn.setStyleSheet("""
            QPushButton {color: #484848; background: transparent; border: none; border-radius: 3px;}
            QPushButton:hover {color: white; background: #8b1515;}
            QPushButton:disabled {color: #242424; background: transparent;}
            QPushButton:hover:pressed {color: #aaaaaa; background: #5a0e0e;}
        """)

        bar_layout = QtWidgets.QHBoxLayout(bar)
        bar_layout.setContentsMargins(4, 0, 4, 0)
        bar_layout.addWidget(lbl, 1)
        bar_layout.addWidget(self.exitBtn, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        layout.addWidget(bar)

    def _build_import_section(self, layout):
        """Shared SimC import text area + simc executable path (used by all tabs)."""
        group = QtWidgets.QGroupBox("SimC Import String")
        gl = QtWidgets.QVBoxLayout(group)
        gl.setSpacing(4)

        self.simcImportStringText = QtWidgets.QTextEdit()
        self.simcImportStringText.setPlaceholderText(
            "Paste your SimC addon export string here (shared across all tabs)..."
        )
        self.simcImportStringText.setFixedHeight(110)
        gl.addWidget(self.simcImportStringText)

        exe_row = QtWidgets.QHBoxLayout()
        exe_row.addWidget(QtWidgets.QLabel("simc Executable:"))
        self.simcExeLine = QtWidgets.QLineEdit()
        self.simcExeLine.setPlaceholderText("Path to simc.exe  (auto-detected if blank)")
        detected = sim.find_simc_executable()
        if detected:
            self.simcExeLine.setText(detected)
        self.browseSimcBtn = QtWidgets.QPushButton("Browse…")
        self.browseSimcBtn.setFixedWidth(72)
        self.browseSimcBtn.setStyleSheet(BTN_BLUE)
        exe_row.addWidget(self.simcExeLine, 1)
        exe_row.addWidget(self.browseSimcBtn)
        gl.addLayout(exe_row)

        layout.addWidget(group)

    # -- Reusable widget factories -------------------------------------------

    def _make_options_group(self, prefix):
        """Create a Sim Options group box.

        Returns (group, fight_combo, terror_spin, threads_spin, maxtime_spin).
        """
        group = QtWidgets.QGroupBox("Sim Options")
        row = QtWidgets.QHBoxLayout(group)
        row.setSpacing(10)

        fight_combo = QtWidgets.QComboBox()
        fight_combo.addItems(["Patchwerk", "HecticAddCleave", "LightMovement", "HeavyMovement"])
        fight_combo.setFixedWidth(148)

        terror_spin = QtWidgets.QDoubleSpinBox()
        terror_spin.setRange(0.01, 5.0)
        terror_spin.setSingleStep(0.05)
        terror_spin.setValue(0.2)
        terror_spin.setDecimals(2)
        terror_spin.setFixedWidth(68)

        threads_spin = QtWidgets.QSpinBox()
        threads_spin.setRange(1, 64)
        threads_spin.setValue(4)
        threads_spin.setFixedWidth(52)

        maxtime_spin = QtWidgets.QSpinBox()
        maxtime_spin.setRange(60, 600)
        maxtime_spin.setSingleStep(30)
        maxtime_spin.setValue(300)
        maxtime_spin.setFixedWidth(68)

        for label_text, widget in (
            ("Fight Style:", fight_combo),
            ("Target Error:", terror_spin),
            ("Threads:", threads_spin),
            ("Max Time:", maxtime_spin),
        ):
            row.addWidget(QtWidgets.QLabel(label_text))
            row.addWidget(widget)
        row.addStretch()

        return group, fight_combo, terror_spin, threads_spin, maxtime_spin

    def _make_results_table(self):
        tbl = QtWidgets.QTableWidget(0, 5)
        tbl.setHorizontalHeaderLabels(["#", "Item / Combo", "DPS", "vs Baseline", "vs %"])
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        for col, width in ((0, 32), (2, 100), (3, 90), (4, 64)):
            hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)
            tbl.setColumnWidth(col, width)
        tbl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        tbl.verticalHeader().setVisible(False)
        tbl.setAlternatingRowColors(True)
        return tbl

    # -- Great Vault tab -----------------------------------------------------

    def _build_great_vault_tab(self):
        tab = QtWidgets.QWidget()
        self.tabs.addTab(tab, "Great Vault")
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        items_row = QtWidgets.QHBoxLayout()

        ctrl = QtWidgets.QVBoxLayout()
        self.gatherVaultBtn = QtWidgets.QPushButton("Gather Gear")
        self.gatherVaultBtn.setStyleSheet(BTN_RED)
        self.includeBagsCheckBox = QtWidgets.QCheckBox("Include Bag Items")
        self.removeItemBtn = QtWidgets.QPushButton("Remove Item")
        self.removeItemBtn.setStyleSheet(BTN_RED)
        self.clearItemsBtn = QtWidgets.QPushButton("Clear Items")
        self.clearItemsBtn.setStyleSheet(BTN_RED)
        for w in (self.gatherVaultBtn, self.includeBagsCheckBox,
                  self.removeItemBtn, self.clearItemsBtn):
            ctrl.addWidget(w)
        ctrl.addStretch()

        vault_col = QtWidgets.QVBoxLayout()
        vault_lbl = QtWidgets.QLabel("Vault Items")
        vault_lbl.setAlignment(QtCore.Qt.AlignCenter)
        vault_lbl.setStyleSheet(
            "color: #e0e0e0; background: #6e1212; border-radius: 3px; padding: 2px;"
        )
        self.vaultItemList = QtWidgets.QListWidget()
        vault_col.addWidget(vault_lbl)
        vault_col.addWidget(self.vaultItemList)

        items_row.addLayout(ctrl, 0)
        items_row.addLayout(vault_col, 1)
        layout.addLayout(items_row)

        results_group = QtWidgets.QGroupBox("Results")
        results_h = QtWidgets.QHBoxLayout(results_group)
        results_h.setSpacing(12)

        best_v = QtWidgets.QVBoxLayout()
        best_v.addWidget(QtWidgets.QLabel("Best Item"))
        self.bestItemLine = QtWidgets.QLineEdit("Awaiting...")
        self.bestItemLine.setReadOnly(True)
        best_v.addWidget(self.bestItemLine)

        dps_v = QtWidgets.QVBoxLayout()
        dps_v.addWidget(QtWidgets.QLabel("Estimated DPS"))
        self.estDPSLine = QtWidgets.QLineEdit()
        self.estDPSLine.setReadOnly(True)
        dps_v.addWidget(self.estDPSLine)

        self.detailsBtn = QtWidgets.QPushButton("DPS Details")
        self.detailsBtn.setEnabled(False)
        self.detailsBtn.setStyleSheet(BTN_BLUE)
        self.detailsBtn.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation)
        )

        results_h.addLayout(best_v, 2)
        results_h.addLayout(dps_v, 1)
        results_h.addWidget(self.detailsBtn, 0, QtCore.Qt.AlignVCenter)
        layout.addWidget(results_group)

        self.runSimBtn = QtWidgets.QPushButton("Run Gear Sim")
        self.runSimBtn.setStyleSheet(BTN_GREEN)
        self.runSimBtn.setFixedHeight(32)
        layout.addWidget(self.runSimBtn, 0, QtCore.Qt.AlignHCenter)

    # -- Real Drop Finder tab (Droptimizer — items from dungeons/raids) ------

    def _build_drop_finder_tab(self):
        tab = QtWidgets.QWidget()
        self.tabs.addTab(tab, "Drop Finder")
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ---- Sim Options ----
        (opts_group, self.dfe_fight_combo, self.dfe_terror_spin,
         self.dfe_threads_spin, self.dfe_maxtime_spin) = self._make_options_group("dfe")
        layout.addWidget(opts_group)

        # ---- Source selectors ----
        sel_row = QtWidgets.QHBoxLayout()
        sel_row.setSpacing(8)

        sel_row.addWidget(QtWidgets.QLabel("Source:"))
        self.dfe_source_type_combo = QtWidgets.QComboBox()
        self.dfe_source_type_combo.addItems(["M+ Dungeons", "Raids"])
        self.dfe_source_type_combo.setFixedWidth(120)
        sel_row.addWidget(self.dfe_source_type_combo)

        sel_row.addWidget(QtWidgets.QLabel("Instance:"))
        self.dfe_instance_combo = QtWidgets.QComboBox()
        self.dfe_instance_combo.setMinimumWidth(180)
        sel_row.addWidget(self.dfe_instance_combo, 1)

        sel_row.addWidget(QtWidgets.QLabel("Boss:"))
        self.dfe_encounter_combo = QtWidgets.QComboBox()
        self.dfe_encounter_combo.setMinimumWidth(160)
        sel_row.addWidget(self.dfe_encounter_combo, 1)

        sel_row.addWidget(QtWidgets.QLabel("Track:"))
        self.dfe_track_combo = QtWidgets.QComboBox()
        self.dfe_track_combo.setMinimumWidth(160)
        sel_row.addWidget(self.dfe_track_combo, 1)

        layout.addLayout(sel_row)

        # Populate instance/track combos from drop_sources.json
        self._dfe_populate_instances()
        self._dfe_populate_tracks()

        # ---- Splitter: item list | results ----
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter, 1)

        left = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 4, 0)
        ll.setSpacing(4)

        item_hdr = QtWidgets.QHBoxLayout()
        item_hdr.addWidget(QtWidgets.QLabel("Items"))
        item_hdr.addStretch()
        self.dfe_select_all_btn = QtWidgets.QPushButton("All")
        self.dfe_select_all_btn.setFixedWidth(36)
        self.dfe_select_all_btn.setStyleSheet(BTN_BLUE)
        self.dfe_select_none_btn = QtWidgets.QPushButton("None")
        self.dfe_select_none_btn.setFixedWidth(42)
        self.dfe_select_none_btn.setStyleSheet(BTN_BLUE)
        item_hdr.addWidget(self.dfe_select_all_btn)
        item_hdr.addWidget(self.dfe_select_none_btn)
        ll.addLayout(item_hdr)

        self.dfe_item_list = QtWidgets.QListWidget()
        ph = QtWidgets.QListWidgetItem("(parse import string to filter by class)")
        ph.setFlags(QtCore.Qt.NoItemFlags)
        ph.setForeground(QtGui.QColor("#555555"))
        self.dfe_item_list.addItem(ph)
        ll.addWidget(self.dfe_item_list)
        splitter.addWidget(left)

        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)
        rl.setSpacing(4)
        rl.addWidget(QtWidgets.QLabel("Results"))
        self.dfe_results_table = self._make_results_table()
        rl.addWidget(self.dfe_results_table)
        splitter.addWidget(right)

        splitter.setSizes([240, 590])

        # ---- Bottom controls ----
        bottom = QtWidgets.QHBoxLayout()
        self.dfe_status_label = QtWidgets.QLabel(
            "(no drop_sources.json found)" if self._dfe_sources is None else ""
        )
        self.dfe_status_label.setStyleSheet("color: #888888; font-size: 8pt;")
        self.dfe_refresh_btn = QtWidgets.QPushButton("Refresh Items")
        self.dfe_refresh_btn.setStyleSheet(BTN_BLUE)
        self.dfe_run_btn = QtWidgets.QPushButton("Run Drop Finder")
        self.dfe_run_btn.setStyleSheet(BTN_GREEN)
        self.dfe_run_btn.setFixedHeight(30)
        self.dfe_run_btn.setEnabled(self._dfe_sources is not None)
        bottom.addWidget(self.dfe_status_label, 1)
        bottom.addWidget(self.dfe_refresh_btn)
        bottom.addWidget(self.dfe_run_btn)
        layout.addLayout(bottom)

    # -- Top Gear tab --------------------------------------------------------

    def _build_top_gear_tab(self):
        tab = QtWidgets.QWidget()
        self.tabs.addTab(tab, "Top Gear")
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        (opts_group, self.tg_fight_combo, self.tg_terror_spin,
         self.tg_threads_spin, self.tg_maxtime_spin) = self._make_options_group("tg")
        layout.addWidget(opts_group)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter, 1)

        left = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 4, 0)
        ll.setSpacing(4)

        bag_hdr = QtWidgets.QHBoxLayout()
        bag_hdr.addWidget(QtWidgets.QLabel("Bag Items"))
        bag_hdr.addStretch()
        self.tg_select_all_btn = QtWidgets.QPushButton("All")
        self.tg_select_all_btn.setFixedWidth(36)
        self.tg_select_all_btn.setStyleSheet(BTN_BLUE)
        self.tg_select_none_btn = QtWidgets.QPushButton("None")
        self.tg_select_none_btn.setFixedWidth(42)
        self.tg_select_none_btn.setStyleSheet(BTN_BLUE)
        bag_hdr.addWidget(self.tg_select_all_btn)
        bag_hdr.addWidget(self.tg_select_none_btn)
        ll.addLayout(bag_hdr)

        self.tg_bag_list = QtWidgets.QListWidget()
        ph = QtWidgets.QListWidgetItem("(parse import string to load items)")
        ph.setFlags(QtCore.Qt.NoItemFlags)
        ph.setForeground(QtGui.QColor("#555555"))
        self.tg_bag_list.addItem(ph)
        ll.addWidget(self.tg_bag_list)

        self.tg_combo_label = QtWidgets.QLabel("Combinations: —")
        self.tg_combo_label.setStyleSheet("color: #888888; font-size: 8pt;")
        ll.addWidget(self.tg_combo_label)
        splitter.addWidget(left)

        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)
        rl.setSpacing(4)
        rl.addWidget(QtWidgets.QLabel("Results"))
        self.tg_results_table = self._make_results_table()
        rl.addWidget(self.tg_results_table)
        splitter.addWidget(right)

        splitter.setSizes([240, 590])

        bottom = QtWidgets.QHBoxLayout()
        self.tg_status_label = QtWidgets.QLabel("")
        self.tg_status_label.setStyleSheet("color: #888888; font-size: 8pt;")
        self.tg_parse_btn = QtWidgets.QPushButton("Parse Import")
        self.tg_parse_btn.setStyleSheet(BTN_BLUE)
        self.tg_run_btn = QtWidgets.QPushButton("Run Top Gear")
        self.tg_run_btn.setStyleSheet(BTN_GREEN)
        self.tg_run_btn.setFixedHeight(30)
        bottom.addWidget(self.tg_status_label, 1)
        bottom.addWidget(self.tg_parse_btn)
        bottom.addWidget(self.tg_run_btn)
        layout.addLayout(bottom)

    # -----------------------------------------------------------------------
    # Signal connections
    # -----------------------------------------------------------------------

    def _connect_signals(self):
        self.exitBtn.clicked.connect(self.close)
        self.browseSimcBtn.clicked.connect(self._browse_simc_exe)

        # Great Vault
        self.gatherVaultBtn.clicked.connect(self.on_gather_vault_click)
        self.removeItemBtn.clicked.connect(self.remove_vault_item)
        self.clearItemsBtn.clicked.connect(self.clear_vault_items)
        self.runSimBtn.clicked.connect(self.run_sim)
        self.detailsBtn.clicked.connect(self.show_dps_details)

        # Real Drop Finder (Droptimizer)
        self.dfe_source_type_combo.currentIndexChanged.connect(
            self._dfe_on_source_type_changed
        )
        self.dfe_instance_combo.currentIndexChanged.connect(
            self._dfe_on_instance_changed
        )
        self.dfe_refresh_btn.clicked.connect(self._dfe_refresh_items)
        self.dfe_run_btn.clicked.connect(self._run_droptimizer)
        self.dfe_select_all_btn.clicked.connect(
            lambda: self._set_all_checked(self.dfe_item_list, True)
        )
        self.dfe_select_none_btn.clicked.connect(
            lambda: self._set_all_checked(self.dfe_item_list, False)
        )

        # Top Gear
        self.tg_parse_btn.clicked.connect(self._parse_for_top_gear)
        self.tg_run_btn.clicked.connect(self._run_top_gear)
        self.tg_select_all_btn.clicked.connect(
            lambda: self._set_all_checked(self.tg_bag_list, True)
        )
        self.tg_select_none_btn.clicked.connect(
            lambda: self._set_all_checked(self.tg_bag_list, False)
        )
        self.tg_bag_list.itemChanged.connect(self._update_combo_count)

    # -----------------------------------------------------------------------
    # Frameless window drag
    # -----------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # -----------------------------------------------------------------------
    # Shared helpers
    # -----------------------------------------------------------------------

    def _browse_simc_exe(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select simc executable", "",
            "Executables (*.exe);;All Files (*)"
        )
        if path:
            self.simcExeLine.setText(path)

    def _get_simc_exe(self):
        path = self.simcExeLine.text().strip()
        if path:
            return path
        found = sim.find_simc_executable()
        if found:
            self.simcExeLine.setText(found)
        return found

    def _get_import_text(self):
        return self.simcImportStringText.toPlainText().strip()

    def _set_all_checked(self, list_widget, checked):
        state = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
        list_widget.blockSignals(True)
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.flags() & QtCore.Qt.ItemIsUserCheckable:
                item.setCheckState(state)
        list_widget.blockSignals(False)
        if list_widget is self.tg_bag_list:
            self._update_combo_count()

    def _populate_bag_list(self, list_widget, bag_items):
        list_widget.clear()
        for item in bag_items:
            ilvl = f"  ilvl {item.ilevel}" if item.ilevel else ""
            name = item.name or f"ID {item.item_id}"
            slot = item.slot.replace("_", " ")
            text = f"{name}  ({slot}{ilvl})"
            lw = QtWidgets.QListWidgetItem(text)
            lw.setFlags(lw.flags() | QtCore.Qt.ItemIsUserCheckable)
            lw.setCheckState(QtCore.Qt.Checked)
            list_widget.addItem(lw)

    def _get_selected_bag_items(self, list_widget, bag_items):
        selected = []
        for i in range(min(list_widget.count(), len(bag_items))):
            if list_widget.item(i).checkState() == QtCore.Qt.Checked:
                selected.append(bag_items[i])
        return selected

    def _make_sim_options(self, fight_combo, terror_spin, threads_spin, maxtime_spin):
        return SimOptions(
            fight_style=fight_combo.currentText(),
            target_error=terror_spin.value(),
            threads=threads_spin.value(),
            max_time=maxtime_spin.value(),
        )

    def _fill_results_table(self, table, sim_results, label_map=None):
        """Populate a results QTableWidget with SimResult objects.

        label_map: optional {simc_label -> display_string} for human-readable names.
        """
        table.setRowCount(0)
        if not sim_results:
            return

        baseline = next((r for r in sim_results if r.label == "Baseline"), None)
        non_baseline = [r for r in sim_results if r.label != "Baseline"]
        rows = ([baseline] if baseline else []) + non_baseline

        table.setRowCount(len(rows))
        rank = 1
        for i, result in enumerate(rows):
            is_baseline = result.label == "Baseline"

            rank_item = QtWidgets.QTableWidgetItem("—" if is_baseline else str(rank))
            rank_item.setTextAlignment(QtCore.Qt.AlignCenter)
            table.setItem(i, 0, rank_item)

            if label_map and result.label in label_map:
                display = label_map[result.label]
            else:
                display = result.label.replace("_", " ")
            table.setItem(i, 1, QtWidgets.QTableWidgetItem(display))

            dps_item = QtWidgets.QTableWidgetItem(f"{result.dps:,.1f}")
            dps_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            table.setItem(i, 2, dps_item)

            if not is_baseline:
                color = QtGui.QColor("#00c060") if result.delta >= 0 else QtGui.QColor("#e03030")
                delta_item = QtWidgets.QTableWidgetItem(f"{result.delta:+,.1f}")
                delta_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                delta_item.setForeground(color)
                table.setItem(i, 3, delta_item)
                pct_item = QtWidgets.QTableWidgetItem(f"{result.delta_pct:+.2f}%")
                pct_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                pct_item.setForeground(color)
                table.setItem(i, 4, pct_item)
                rank += 1
            else:
                table.setItem(i, 3, QtWidgets.QTableWidgetItem(""))
                table.setItem(i, 4, QtWidgets.QTableWidgetItem(""))

    # -----------------------------------------------------------------------
    # Real Drop Finder (Droptimizer) helpers
    # -----------------------------------------------------------------------

    def _dfe_current_instance_type(self) -> str:
        return "dungeon" if self.dfe_source_type_combo.currentIndex() == 0 else "raid"

    def _dfe_populate_instances(self):
        """Populate the instance combo from drop_sources.json."""
        self.dfe_instance_combo.blockSignals(True)
        self.dfe_instance_combo.clear()
        if self._dfe_sources:
            inst_type = self._dfe_current_instance_type()
            for inst in get_instances(self._dfe_sources, inst_type):
                self.dfe_instance_combo.addItem(inst["name"], userData=inst["id"])
        self.dfe_instance_combo.blockSignals(False)
        self._dfe_populate_encounters()

    def _dfe_populate_encounters(self):
        """Populate the encounter/boss combo for the current instance."""
        self.dfe_encounter_combo.blockSignals(True)
        self.dfe_encounter_combo.clear()
        self.dfe_encounter_combo.addItem("All Bosses", userData=None)
        if self._dfe_sources:
            inst_id = self.dfe_instance_combo.currentData()
            if inst_id is not None:
                for enc in get_encounters(self._dfe_sources, inst_id):
                    self.dfe_encounter_combo.addItem(enc["name"], userData=enc["id"])
        self.dfe_encounter_combo.blockSignals(False)

    def _dfe_populate_tracks(self):
        """Populate the track combo for the current instance type."""
        self.dfe_track_combo.blockSignals(True)
        self.dfe_track_combo.clear()
        if self._dfe_sources:
            inst_type = self._dfe_current_instance_type()
            for track in get_ilvl_tracks(self._dfe_sources, inst_type):
                label = f"{track['label']}  (ilvl {track['ilvl']})"
                self.dfe_track_combo.addItem(label, userData=track["ilvl"])
        self.dfe_track_combo.blockSignals(False)

    def _dfe_on_source_type_changed(self):
        self._dfe_populate_instances()
        self._dfe_populate_tracks()
        self._dfe_refresh_items()

    def _dfe_on_instance_changed(self):
        self._dfe_populate_encounters()
        self._dfe_refresh_items()

    def _dfe_refresh_items(self):
        """Re-load item list for the current instance/encounter/class selection."""
        if not self._dfe_sources:
            return

        inst_id = self.dfe_instance_combo.currentData()
        if inst_id is None:
            return
        enc_id = self.dfe_encounter_combo.currentData()  # None = all bosses

        # Try to get character class from current parse result
        char_class = None
        if self._parse_result:
            char_class = self._parse_result.character_class
        else:
            text = self._get_import_text()
            if text:
                try:
                    self._parse_result = parse_simc_addon(text)
                    char_class = self._parse_result.character_class
                except Exception:
                    pass

        self._dfe_raw_items = get_encounter_items(
            self._dfe_sources, inst_id,
            encounter_id=enc_id,
            character_class=char_class,
        )

        self.dfe_item_list.blockSignals(True)
        self.dfe_item_list.clear()
        for raw in self._dfe_raw_items:
            slot = raw["slot"].replace("_", " ")
            text = f"{raw['name']}  ({slot})"
            lw = QtWidgets.QListWidgetItem(text)
            lw.setFlags(lw.flags() | QtCore.Qt.ItemIsUserCheckable)
            lw.setCheckState(QtCore.Qt.Checked)
            self.dfe_item_list.addItem(lw)
        self.dfe_item_list.blockSignals(False)

        n = len(self._dfe_raw_items)
        cls_str = f" [{char_class}]" if char_class else ""
        self.dfe_status_label.setText(f"{n} item(s) loaded{cls_str}")

    def _run_droptimizer(self):
        text = self._get_import_text()
        if not text:
            self.dfe_status_label.setText("Paste an import string first.")
            return
        if not self._dfe_raw_items:
            self.dfe_status_label.setText("Select a dungeon/raid and click Refresh Items.")
            return
        exe = self._get_simc_exe()
        if not exe:
            self.dfe_status_label.setText("simc executable not found.")
            return

        ilvl = self.dfe_track_combo.currentData()
        if ilvl is None:
            self.dfe_status_label.setText("Select a track (ilvl) first.")
            return

        # Collect selected items
        selected_raw = []
        for i in range(min(self.dfe_item_list.count(), len(self._dfe_raw_items))):
            if self.dfe_item_list.item(i).checkState() == QtCore.Qt.Checked:
                selected_raw.append(self._dfe_raw_items[i])

        if not selected_raw:
            self.dfe_status_label.setText("No items selected.")
            return

        parsed_items = loot_items_to_parsed(selected_raw, ilvl)
        options = self._make_sim_options(
            self.dfe_fight_combo, self.dfe_terror_spin,
            self.dfe_threads_spin, self.dfe_maxtime_spin,
        )

        inst_name = self.dfe_instance_combo.currentText()
        self.dfe_status_label.setText(
            f"Running Drop Finder for {inst_name}  ({len(parsed_items)} items, ilvl {ilvl})…"
        )
        self.dfe_run_btn.setEnabled(False)
        self.dfe_refresh_btn.setEnabled(False)

        worker = DroptimizerWorker(text, parsed_items, options, exe)
        worker.signals.finished.connect(self._dfe_on_finished)
        worker.signals.error.connect(self._dfe_on_error)
        self.threadpool.start(worker)

    def _dfe_on_finished(self, result):
        _, sim_results, combo_meta = result
        label_map = {}
        for label, item in combo_meta.items():
            name = item.name or f"ID {item.item_id}"
            slot = item.slot.replace("_", " ").title()
            label_map[label] = f"{name}  ({slot})"
        self._fill_results_table(self.dfe_results_table, sim_results, label_map)
        n = len([r for r in sim_results if r.label != "Baseline"])
        self.dfe_status_label.setText(f"Done  —  {n} item(s) ranked")
        self.dfe_run_btn.setEnabled(True)
        self.dfe_refresh_btn.setEnabled(True)

    def _dfe_on_error(self, msg):
        self.dfe_status_label.setText(f"Error: {msg}")
        self.dfe_run_btn.setEnabled(True)
        self.dfe_refresh_btn.setEnabled(True)

    # -----------------------------------------------------------------------
    # Great Vault tab logic
    # -----------------------------------------------------------------------

    def on_gather_vault_click(self):
        import_string = self._get_import_text()
        include_bags = self.includeBagsCheckBox.isChecked()
        vals = ggv.generate_vault_rewards_from_file(import_string, include_bags=include_bags)
        if vals is None:
            print("Empty string inputted")
            return
        if vals.count == 0:
            print("WR404-WR Not found or empty")
            return
        self.clear_vault_items()
        self.rewards = vals[0]
        self.simc_import = vals[1]
        self.start_end[0] = vals[2]
        self.start_end[1] = vals[3]
        for i, reward in enumerate(self.rewards, 1):
            print(f"[{i}] {reward[0]}")
            self.vaultItemList.insertItem(i, reward[0])

    def clear_vault_items(self):
        self.rewards = []
        self.vaultItemList.clear()

    def remove_vault_item(self):
        row = self.vaultItemList.currentRow()
        if row < 0:
            return
        self.rewards.pop(row)
        self.vaultItemList.takeItem(row)

    def run_sim(self):
        if not self.rewards or not self.simc_import:
            self.bestItemLine.setText("Error: Missing parameters.")
            return
        self.bestItemLine.setText("Running Sim...")
        self.runSimBtn.setEnabled(False)
        self.exitBtn.setEnabled(False)
        worker = SimWorker(self.rewards, self.simc_import)
        worker.signals.finished.connect(self._gv_on_finished)
        self.threadpool.start(worker)

    def _gv_on_finished(self, result):
        best_item, all_results = result
        if best_item:
            self.bestItemLine.setText(f"{best_item[0]}")
            self.estDPSLine.setText(f"{'%.2f' % best_item[1]}")
        self.all_dps_results = all_results
        self.detailsBtn.setEnabled(True)
        self.runSimBtn.setEnabled(True)
        self.exitBtn.setEnabled(True)

    def show_dps_details(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("DPS Breakdown")
        dialog.setMinimumWidth(440)
        layout = QtWidgets.QVBoxLayout(dialog)

        baseline = next((r for r in self.all_dps_results if r[0] == "Baseline"), None)
        items = sorted(
            [r for r in self.all_dps_results if r[0] != "Baseline"],
            key=lambda x: x[1], reverse=True,
        )
        if baseline:
            lbl = QtWidgets.QLabel(f"Baseline (Equipped):  {baseline[1]:,.2f} DPS")
            lbl.setStyleSheet(
                "font-weight: bold; font-size: 12px; padding: 6px;"
                "background: #222; color: #ddd; border-radius: 4px;"
            )
            layout.addWidget(lbl)

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

    # -----------------------------------------------------------------------
    # Top Gear tab logic
    # -----------------------------------------------------------------------

    def _parse_for_top_gear(self):
        text = self._get_import_text()
        if not text:
            self.tg_status_label.setText("Paste an import string first.")
            return
        try:
            self._parse_result = parse_simc_addon(text)
            self._tg_bag_items = list(self._parse_result.bag_items)
            self.tg_bag_list.blockSignals(True)
            self._populate_bag_list(self.tg_bag_list, self._tg_bag_items)
            self.tg_bag_list.blockSignals(False)
            n = len(self._tg_bag_items)
            char = self._parse_result.character_name
            self.tg_status_label.setText(f"Parsed: {char}  —  {n} bag item(s) loaded")
            self._update_combo_count()
        except Exception as exc:
            self.tg_status_label.setText(f"Parse error: {exc}")

    def _update_combo_count(self):
        if not self._parse_result or not self._tg_bag_items:
            self.tg_combo_label.setText("Combinations: —")
            return
        selected = self._get_selected_bag_items(self.tg_bag_list, self._tg_bag_items)
        count = count_top_gear_combinations(
            self._parse_result, selected_bag_items=selected
        )
        if count > 10_000:
            self.tg_combo_label.setStyleSheet("color: #e03030; font-size: 8pt;")
            self.tg_combo_label.setText(
                f"Combinations: {count:,}  — too many, deselect items to reduce"
            )
        elif count > 1_000:
            self.tg_combo_label.setStyleSheet("color: #e08030; font-size: 8pt;")
            self.tg_combo_label.setText(f"Combinations: {count:,}  (may be slow)")
        else:
            self.tg_combo_label.setStyleSheet("color: #60b060; font-size: 8pt;")
            self.tg_combo_label.setText(f"Combinations: {count:,}")

    def _run_top_gear(self):
        text = self._get_import_text()
        if not text:
            self.tg_status_label.setText("Paste an import string first.")
            return
        if not self._tg_bag_items:
            self.tg_status_label.setText("Parse the import string first.")
            return
        exe = self._get_simc_exe()
        if not exe:
            self.tg_status_label.setText("simc executable not found — browse to set its path.")
            return
        selected = self._get_selected_bag_items(self.tg_bag_list, self._tg_bag_items)
        if not selected:
            self.tg_status_label.setText("No items selected.")
            return

        MAX_COMBOS = 50_000
        count = count_top_gear_combinations(
            self._parse_result, selected_bag_items=selected
        )
        if count > MAX_COMBOS:
            self.tg_status_label.setText(
                f"Too many combinations ({count:,} > {MAX_COMBOS:,}).  Deselect some items."
            )
            return

        options = self._make_sim_options(
            self.tg_fight_combo, self.tg_terror_spin,
            self.tg_threads_spin, self.tg_maxtime_spin,
        )
        config = TopGearConfig(
            simc_executable=exe,
            options=options,
            mode="top_gear",
            selected_bag_items=selected,
            max_combinations=MAX_COMBOS,
        )
        self.tg_status_label.setText(f"Running Top Gear  —  {count:,} combination(s)…")
        self.tg_run_btn.setEnabled(False)
        self.tg_parse_btn.setEnabled(False)

        worker = TopGearWorker(text, config)
        worker.signals.finished.connect(self._tg_on_finished)
        worker.signals.error.connect(self._tg_on_error)
        self.threadpool.start(worker)

    def _tg_on_finished(self, result):
        _, sim_results, meta = result
        # Build label map: combo_N -> "Item A + Item B (+ N more)"
        label_map = {}
        for label, items in meta.items():
            parts = [i.name or f"ID {i.item_id}" for i in items[:3]]
            display = " + ".join(parts)
            if len(items) > 3:
                display += f" +{len(items) - 3} more"
            label_map[label] = display
        self._fill_results_table(self.tg_results_table, sim_results, label_map)
        n = len([r for r in sim_results if r.label != "Baseline"])
        self.tg_status_label.setText(f"Done  —  {n} combination(s) ranked")
        self.tg_run_btn.setEnabled(True)
        self.tg_parse_btn.setEnabled(True)

    def _tg_on_error(self, msg):
        self.tg_status_label.setText(f"Error: {msg}")
        self.tg_run_btn.setEnabled(True)
        self.tg_parse_btn.setEnabled(True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()
