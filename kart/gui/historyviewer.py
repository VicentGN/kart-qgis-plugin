import os

from kart.kartapi import executeskart
from kart.gui.diffviewer import DiffViewerDialog

from qgis.core import Qgis
from qgis.utils import iface
from qgis.gui import QgsMessageBar

from qgis.PyQt.QtCore import Qt, QPoint, QRectF
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter, QColor, QPainterPath, QPen

from qgis.PyQt.QtWidgets import (
    QTreeWidget,
    QAbstractItemView,
    QAction,
    QMenu,
    QTreeWidgetItem,
    QWidget,
    QVBoxLayout,
    QDialog,
    QSizePolicy,
    QLabel,
    QInputDialog,
    QHeaderView,
)

COMMIT_GRAPH_HEIGHT = 20
RADIUS = 4
COL_SPACING = 20
PEN_WIDTH = 2
MARGIN = 50

COLORS = [
    QColor(Qt.red),
    QColor(Qt.green),
    QColor(Qt.blue),
    QColor(Qt.black),
    QColor(255, 166, 0),
    QColor(Qt.darkGreen),
    QColor(Qt.darkBlue),
    QColor(Qt.cyan),
    QColor(Qt.magenta),
]


def icon(f):
    return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), "img", f))


resetIcon = icon("reset.png")
diffIcon = icon("changes.png")
checkoutIcon = icon("checkout.png")
mergeIcon = icon("merge.png")
createBranchIcon = icon("createbranch.png")
deleteIcon = icon("delete.png")
createTagIcon = icon("label.png")
restoreIcon = icon("checkout.png")


class HistoryTree(QTreeWidget):
    def __init__(self, repo, parent):
        super(HistoryTree, self).__init__()
        self.repo = repo
        self.parent = parent
        self.initGui()

    def initGui(self):
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.header().setStretchLastSection(True)
        self.setHeaderLabels(
            ["Graph", "Refs", "Description", "Author", "Date", "CommitID"]
        )
        self.customContextMenuRequested.connect(self._showPopupMenu)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.populate()

    def _showPopupMenu(self, point):
        def _f(f, *args):
            def wrapper():
                f(*args)

            return wrapper

        point = self.mapToGlobal(point)
        selected = self.selectedItems()
        if selected and len(selected) == 1:
            item = self.currentItem()
            actions = {
                "Show changes for this commit...": (
                    _f(self.showChangesInCommit, item),
                    diffIcon,
                ),
                "Reset current branch to this commit": (
                    _f(self.resetBranch, item),
                    resetIcon,
                ),
                "Create branch at this commit...": (
                    _f(self.createBranch, item),
                    createBranchIcon,
                ),
                "Create tag at this commit...": (
                    _f(self.createTag, item),
                    createTagIcon,
                ),
                "Restore working tree layers to this version...": (
                    _f(self.restoreLayers, item),
                    restoreIcon,
                ),
            }

            for ref in item.commit["refs"]:
                if "HEAD" in ref:
                    continue
                elif "tag:" in ref:
                    tag = ref[4:].strip()
                    actions[f"Delete tag '{tag}'"] = (
                        _f(self.deleteTag, tag),
                        deleteIcon,
                    )
                else:
                    actions[f"Switch to branch '{ref}'"] = (
                        _f(self.switchBranch, ref),
                        checkoutIcon,
                    )
                    actions[f"Delete branch '{ref}'"] = (
                        _f(self.deleteBranch, ref),
                        deleteIcon,
                    )
        elif selected and len(selected) == 2:
            itema = selected[0]
            itemb = selected[1]
            actions = {
                "Show changes between these commits...": (
                    _f(self.showChangesBetweenCommits, itema, itemb),
                    diffIcon,
                )
            }
        else:
            actions = []
        menu = QMenu()
        for text in actions:
            func, icon = actions[text]
            action = QAction(icon, text, menu)
            action.triggered.connect(func)
            menu.addAction(action)
        if actions:
            menu.exec_(point)

    @executeskart
    def createTag(self, item):
        name, ok = QInputDialog.getText(
            self, "Create branch", "Enter name of branch to create"
        )
        if ok and name:
            self.repo.createTag(name, item.commit["commit"])
            self.message("Tag correctly created", Qgis.Info)
            self.populate()

    @executeskart
    def deleteTag(self, tag):
        self.repo.deleteTag(tag)
        self.message(f"Correctly deleted tag '{tag}'", Qgis.Info)
        self.populate()

    @executeskart
    def switchBranch(self, branch):
        self.repo.checkoutBranch(branch)
        self.message(f"Correctly switched to branch '{branch}'", Qgis.Info)
        self.populate()

    @executeskart
    def deleteBranch(self, branch):
        self.repo.deleteBranch(branch)
        self.message(f"Correctly deleted branch '{branch}'", Qgis.Info)
        self.populate()

    @executeskart
    def createBranch(self, item):
        name, ok = QInputDialog.getText(
            self, "Create branch", "Enter name of branch to create"
        )
        if ok and name:
            self.repo.createBranch(name, item.commit["commit"])
            self.message("Branch correctly created", Qgis.Info)
            self.populate()

    @executeskart
    def showChangesInCommit(self, item):
        refa = item.commit["commit"]
        parents = item.commit["parents"]
        refb = parents[0] if parents else "000000000"
        changes = self.repo.diff(refa, refb)
        dialog = DiffViewerDialog(self, changes)
        dialog.exec()

    @executeskart
    def showChangesBetweenCommits(self, itema, itemb):
        refa = itema.commit["commit"]
        refb = itemb.commit["commit"]
        changes = self.repo.diff(refa, refb)
        dialog = DiffViewerDialog(self, changes)
        dialog.exec()

    @executeskart
    def resetBranch(self, item):
        self.repo.reset(item.commit["commit"])
        self.message("Branch correctly reset to selected commit", Qgis.Info)
        self.populate()

    @executeskart
    def restoreLayers(self, item):
        ALL_LAYERS = "Restore all layers"
        layers = self.repo.layers()
        layers.insert(0, ALL_LAYERS)
        layer, ok = QInputDialog.getItem(
            iface.mainWindow(),
            "Restore",
            "Select layer to restore:",
            layers,
            editable=False,
        )
        if ok:
            if layer == ALL_LAYERS:
                layer = None
            self.repo.restore(item.commit["commit"], layer)
            self.message("Selected layer correctly restored in working tree", Qgis.Info)

    def message(self, text, level):
        self.parent.bar.pushMessage(text, level, duration=5)

    def populate(self):
        commits = self.repo.log()

        self.log = {c["commit"]: c for c in commits}
        self.clear()

        maxcol = max([c["commitColumn"] for c in commits])
        width = COL_SPACING * maxcol + 2 * RADIUS

        for i, commit in enumerate(commits):
            item = CommitTreeItem(commit, self)
            self.addTopLevelItem(item)
            img = self.graphImage(commit, width)
            w = GraphWidget(img)
            w.setFixedHeight(COMMIT_GRAPH_HEIGHT)
            self.setItemWidget(item, 0, w)

        for i in range(1, 6):
            self.resizeColumnToContents(i)
        self.setColumnWidth(0, width + MARGIN)
        self.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.header().setSectionResizeMode(1, QHeaderView.Fixed)

    def graphImage(self, commit, width):
        image = QPixmap(width, COMMIT_GRAPH_HEIGHT).toImage()
        qp = QPainter(image)
        qp.fillRect(QRectF(0, 0, width, COMMIT_GRAPH_HEIGHT), Qt.white)

        path = QPainterPath()
        for col in commit["graph"][0][r"\|"]:
            x = RADIUS + COL_SPACING * col
            path.moveTo(x, COMMIT_GRAPH_HEIGHT / 2)
            path.lineTo(x, 0)
        for col in commit["graph"][2][r"\|"]:
            x = RADIUS + COL_SPACING * col
            path.moveTo(x, COMMIT_GRAPH_HEIGHT / 2)
            path.lineTo(x, COMMIT_GRAPH_HEIGHT)
        for col in commit["graph"][0][r"/"]:
            x = RADIUS + COL_SPACING * col
            x2 = RADIUS + COL_SPACING * (col + 0.5)
            path.moveTo(x, COMMIT_GRAPH_HEIGHT / 2)
            path.lineTo(x2, 0)
        for col in commit["graph"][2][r"/"]:
            x = RADIUS + COL_SPACING * (col + 1)
            x2 = RADIUS + COL_SPACING * (col + 0.5)
            path.moveTo(x, COMMIT_GRAPH_HEIGHT / 2)
            path.lineTo(x2, COMMIT_GRAPH_HEIGHT)
        for col in commit["graph"][0][r"\\"]:
            x = RADIUS + COL_SPACING * (col + 1)
            x2 = RADIUS + COL_SPACING * (col + 0.5)
            path.moveTo(x, COMMIT_GRAPH_HEIGHT / 2)
            path.lineTo(x2, 0)
        for col in commit["graph"][2][r"\\"]:
            x = RADIUS + COL_SPACING * (col)
            x2 = RADIUS + COL_SPACING * (col + 0.5)
            path.moveTo(x, COMMIT_GRAPH_HEIGHT / 2)
            path.lineTo(x2, COMMIT_GRAPH_HEIGHT)
        pen = QPen()
        pen.setWidth(PEN_WIDTH)
        pen.setBrush(QColor(Qt.black))
        qp.setPen(pen)
        qp.drawPath(path)

        col = commit["commitColumn"]
        y = COMMIT_GRAPH_HEIGHT / 2
        x = RADIUS + COL_SPACING * col
        color = COLORS[col]
        qp.setPen(color)
        qp.setBrush(color)
        qp.drawEllipse(QPoint(x, y), RADIUS, RADIUS)
        qp.end()

        return image


class GraphWidget(QWidget):
    def __init__(self, img):
        QWidget.__init__(self)
        self.setFixedWidth(img.width())
        self.img = img

    def paintEvent(self, e):
        painter = QPainter(self)
        # painter.begin(self);
        painter.drawImage(0, 0, self.img)
        painter.end()


class CommitTreeItem(QTreeWidgetItem):
    def __init__(self, commit, parent):
        QTreeWidgetItem.__init__(self, parent)
        self.commit = commit
        if commit["refs"]:
            labelslist = []
            for label in commit["refs"]:
                if "HEAD ->" in label:
                    labelslist.append(
                        '<span style="background-color:crimson; color:white"> '
                        f'&nbsp;&nbsp;{label.split("->")[-1].strip()}&nbsp;&nbsp;</span>'
                    )
                elif "tag:" in label:
                    labelslist.append(
                        '<span style="background-color:yellow; color:black"> '
                        f"&nbsp;&nbsp;{label[4:].strip()}&nbsp;&nbsp;</span>"
                    )
                else:
                    labelslist.append(
                        '<span style="background-color:salmon; color:white"> '
                        f"&nbsp;&nbsp;{label}&nbsp;&nbsp;</span>"
                    )
            labels = " ".join(labelslist) + "&nbsp;&nbsp;"
        else:
            labels = ""
        qlabel = QLabel(labels)
        qlabel.setStyleSheet("QLabel {padding-left: 15px;}")
        parent.setItemWidget(self, 1, qlabel)
        self.setText(2, commit["message"].splitlines()[0])
        self.setText(3, commit["authorName"])
        self.setText(4, commit["authorTime"])
        self.setText(5, commit["commit"])


class HistoryDialog(QDialog):
    def __init__(self, repo):
        super(HistoryDialog, self).__init__(iface.mainWindow())
        self.setWindowFlags(Qt.Window)
        layout = QVBoxLayout()
        layout.setMargin(0)
        self.bar = QgsMessageBar()
        self.bar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        layout.addWidget(self.bar)
        self.history = HistoryTree(repo, self)
        layout.addWidget(self.history)
        self.setLayout(layout)
        self.setWindowTitle("History")
        self.resize(1024, 768)