# main_qt.py
# pip install PySide6
from PySide6.QtWidgets import (
    QApplication, QLabel, QMenu, QFileDialog, QMessageBox
)
from PySide6.QtGui import QPixmap, QAction
from PySide6.QtCore import Qt, QTimer, QPoint, Signal, QObject, QThread
from PySide6.QtGui import QGuiApplication
import sys, os, glob, math, time

# ---------- ユーティリティ ----------
def resource_path(*relative):
    """開発時/pyinstaller双方で Resources を見つける"""
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base, "Resources", *relative)


# ---------- バックグラウンドでディレクトリ走査 ----------
class WalkerWorker(QObject):
    finished = Signal(list)   # 完成した文字列リストをメインに返す
    error = Signal(str)

    def __init__(self, root_dir: str):
        super().__init__()
        self.root_dir = root_dir

    def run(self):
        try:
            d = self.root_dir
            now = time.strftime("%Y/%m/%d %H:%M:%S")
            file_list = [f"フォルダ一覧: {d}", f"作成日時: {now}", "-"*80, ""]
            for root, dirs, files in os.walk(d):
                rel = os.path.relpath(root, d)
                depth = 0 if rel == "." else rel.count(os.sep) + 1
                indent = "  " * depth

                if depth > 0:
                    try:
                        st = os.stat(root)
                        ts = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(st.st_mtime))
                        file_list.append(f"{indent}📁 {os.path.basename(root)} - {ts}")
                    except Exception as ex:
                        file_list.append(f"{indent}⚠️ {os.path.basename(root)} - {ex}")

                for f in sorted(files):
                    p = os.path.join(root, f)
                    try:
                        st = os.stat(p)
                        ts = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(st.st_mtime))
                        size = WalkerWorker.format_size(st.st_size)
                        file_list.append(f"{indent}📄 {f} ({size}) - {ts}")
                    except Exception as ex:
                        file_list.append(f"{indent}⚠️ {f} - {ex}")

            self.finished.emit(file_list)
        except Exception as e:
            self.error.emit(str(e))

    @staticmethod
    def format_size(n: int) -> str:
        units = ["B","KB","MB","GB","TB"]
        i = 0
        f = float(n)
        while f >= 1024 and i < len(units)-1:
            f /= 1024
            i += 1
        return f"{f:.2f} {units[i]}"


# ---------- マスコット本体（ラベルを窓として使用） ----------
class Mascot(QLabel):
    def __init__(self):
        super().__init__()

        # 透過・最前面・枠なし
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # アニメ関連パラメータ（好みに合わせて変更）
        self.interval_ms = 100    # タイマー間隔
        self.wave_amp    = 30     # 浮き沈みの幅
        self.wave_step   = 0.20   # 浮き沈みの速さ
        self.speed       = 2      # 横移動の速さ（ピクセル/tick）

        # 画像読み込み（右/左フレーム数チェック）
        self.frames_right, self.frames_left = self.load_frames_or_raise()
        self.frames = [self.frames_right, self.frames_left]  # 0=右,1=左

        # 初期状態
        self.dir = 0     # 0=右, 1=左
        self.idx = 0
        self.wave = 0.0
        self.center_y = 300
        self.move(100, self.center_y)

        # 初回表示
        self.setPixmap(self.frames[self.dir][self.idx])
        self.resize(self.pixmap().size())

        # 右クリックメニュー
        self.menu = QMenu(self)
        act_list = QAction("ファイルのパスを作成", self)
        act_quit = QAction("終了", self)
        act_list.triggered.connect(self.make_file_list)
        act_quit.triggered.connect(self.close)
        self.menu.addAction(act_list)
        self.menu.addSeparator()
        self.menu.addAction(act_quit)

        # アニメーションタイマー
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.loop)
        self.timer.start(self.interval_ms)

        # 画面幅（作業領域）取得
        self.screen_rect = QGuiApplication.primaryScreen().availableGeometry()

        # ドラッグ用
        self.drag_offset = QPoint()

    # ---------- 画像読み込み ----------
    def load_frames_or_raise(self):
        candidates = sorted(glob.glob(resource_path("base*.png")))
        right_paths = [p for p in candidates if "_left" not in os.path.basename(p)]
        left_paths  = [p for p in candidates if "_left" in  os.path.basename(p)]

        if not right_paths:
            raise RuntimeError("Resources に base*.png が見つかりません。")

        right = [QPixmap(p) for p in right_paths]
        if left_paths:
            left = [QPixmap(p) for p in sorted(left_paths)]
            # 左右の枚数が一致しなければエラー（起動時に検知）
            if len(right) != len(left):
                raise RuntimeError(f"左右のフレーム枚数が一致しません: 右={len(right)}枚, 左={len(left)}枚")
        else:
            # 左向きが全く無い場合は右をミラーして同数生成（色キー不要でPNG透過）
            left = [pixmap.transformed(
                        # X方向に反転
                        # QTransform の import いらずに scale を貼る
                        # ただし縦はそのまま
                        # PySide6 では QPixmap.transformed に QTransform を渡す必要があるため：
                        # from PySide6.QtGui import QTransform
                        # QTransform().scale(-1, 1)
                        # を使う
                        __import__("PySide6.QtGui").QtGui.QTransform().scale(-1, 1)
                    ) for pixmap in right]

        return right, left

    # ---------- アニメーション ----------
    def loop(self):
        # フレーム更新（向きごとの枚数で回すのが安全）
        cur_list = self.frames[self.dir]
        if not cur_list:
            return
        self.idx = (self.idx + 1) % len(cur_list)
        self.setPixmap(cur_list[self.idx])

        # 自動移動＆端で反転
        x = self.x() + (self.speed if self.dir == 0 else -self.speed)
        if x + self.width() >= self.screen_rect.right() or x <= self.screen_rect.left():
            self.dir = 1 - self.dir

        # 浮き沈み
        self.wave += self.wave_step
        y = self.center_y + int(math.sin(self.wave) * self.wave_amp)
        self.move(x, y)

    # ---------- 右クリックメニュー ----------
    def contextMenuEvent(self, event):
        self.menu.exec(event.globalPos())

    # ---------- ドラッグ移動 ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.pos()
            # ドラッグ開始時に中心Y更新
            self.center_y = self.y()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_offset
            self.move(new_pos)

    # ---------- ファイル一覧 ----------
    def make_file_list(self):
        directory = QFileDialog.getExistingDirectory(self, "ファイル一覧を作成するフォルダを選択してください")
        if not directory:
            return

        # バックグラウンドで走査
        self.worker = WalkerWorker(directory)
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_walk_finished)
        self.worker.error.connect(self._on_walk_error)
        # 後始末
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.error.connect(self.thread.quit)
        self.worker.error.connect(self.worker.deleteLater)

        self.thread.start()

    def _on_walk_finished(self, file_list):
        # 保存ダイアログはメインスレッドで
        fn, _ = QFileDialog.getSaveFileName(
            self,
            "ファイル一覧を保存",
            f"ファイル一覧_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            "テキストファイル (*.txt)"
        )
        if not fn:
            return
        try:
            with open(fn, "w", encoding="utf-8") as f:
                f.write("\n".join(file_list))
            QMessageBox.information(self, "成功", "ファイル一覧を保存しました。")
        except Exception as e:
            QMessageBox.critical(self, "エラー", str(e))

    def _on_walk_error(self, msg):
        QMessageBox.critical(self, "エラー", msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Mascot()
    w.show()
    sys.exit(app.exec())
