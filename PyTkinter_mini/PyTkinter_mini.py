# main.py
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import os, sys, time, threading, glob, math

# 効果音: pip install simpleaudio
try:
    import simpleaudio as sa
except Exception:
    sa = None


def resource_path(*relative):
    """開発時/pyinstaller双方で Resources を見つける"""
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base, "Resources", *relative)


class Mascot(tk.Tk):
    def __init__(self):
        super().__init__()
        # 無枠・最前面
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry("+100+300")

        # 音
        self.click_wav = resource_path("kirby_1.wav")
        if not os.path.exists(self.click_wav):
            self.click_wav = None

        # UI
        self.label = tk.Label(self, bd=0)
        self.label.pack()

        # 右クリックメニュー
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="ファイルのパスを作成", command=self.get_file_paths)
        self.menu.add_separator()
        self.menu.add_command(label="終了", command=self.destroy)
        self.bind("<Button-3>", self.show_menu)

        # 左クリック（音 + ドラッグ開始）
        self.bind("<Button-1>", self.on_left_down)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<Escape>", lambda e: self.destroy())

        # 画像フレーム（※ここで self を master にして読み込む）
        self.frames = self._load_frames_from_resources()

        # 移動関連
        self.dir = 0   # 0=右, 1=左
        self.idx = 0
        self.wave = 0.0
        self.center_y = 300
        self.update_idletasks()
        self.sw = self.winfo_screenwidth()

        # __init__ のどこか（移動関連の直前）に追加
        self.interval_ms = 100     # タイマー間隔（小さいほど滑らか/重い）
        self.wave_amp    = 30     # 上下幅
        self.wave_step   = 0.15   # 浮き沈みの速さ
        self.speed       = 3      # 横移動の速さ


        # ループ開始
        self.after(100, self.loop)

    # ====== 資源読み込み ======
    def _load_frames_from_resources(self):
        import glob
        candidates = sorted(glob.glob(resource_path("base*.png")))
        right_paths = [p for p in candidates if "_left" not in os.path.basename(p)]
        left_paths  = [p for p in candidates if "_left" in  os.path.basename(p)]

        if not right_paths:
            raise RuntimeError("Resources に base*.png が見つかりません。")

        right = [ImageTk.PhotoImage(Image.open(p), master=self) for p in right_paths]
        if left_paths:
            left = [ImageTk.PhotoImage(Image.open(p), master=self) for p in sorted(left_paths)]
        else:
            # 左向き画像が全く無い場合 → ミラーで自動生成
            left = [ImageTk.PhotoImage(ImageOps.mirror(Image.open(p)), master=self)
                    for p in right_paths]

        # フレーム枚数チェック
        if len(right) != len(left):
            raise RuntimeError(
                f"左右のフレーム枚数が一致しません: 右={len(right)}枚, 左={len(left)}枚"
            )

        print(f"[DEBUG] frames loaded: right={len(right)}, left={len(left)}")
        return [right, left]


    # ====== イベント ======
    def show_menu(self, e):
        self.menu.post(e.x_root, e.y_root)

    def on_left_down(self, e):
        if self.click_wav and sa:
            try:
                sa.WaveObject.from_wave_file(self.click_wav).play()
            except Exception as ex:
                print("sound error:", ex)
        self._offx, self._offy = e.x, e.y
        # ドラッグ開始時に中心Y更新
        geo = self.geometry().split("+")
        if len(geo) >= 3:
            try:
                self.center_y = int(geo[2])
            except ValueError:
                pass

    def on_drag(self, e):
        self.geometry(f"+{self.winfo_x()+e.x-self._offx}+{self.winfo_y()+e.y-self._offy}")

    # ====== メインループ ======
    def loop(self):
        # フレーム更新
        self.idx = (self.idx + 1) % len(self.frames[0])
        img = self.frames[self.dir][self.idx]
        self.label.configure(image=img)

        # 自動移動＆端で反転
        x = self.winfo_x() + (self.speed if self.dir == 0 else -self.speed)
        w = self.winfo_width() or img.width()
        if x + w >= self.sw or x <= 0:
            self.dir = 1 - self.dir

        # 波運動
        self.wave += 0.2
        y = self.center_y + int(math.sin(self.wave) * self.wave_amp)
        self.geometry(f"+{x}+{y}")

        self.after(100, self.loop)

    # ====== ファイル一覧 ======
    def get_file_paths(self):
        d = filedialog.askdirectory(title="ファイル一覧を作成するフォルダを選択してください")
        if not d:
            return
        file_list = []
        now = time.strftime("%Y/%m/%d %H:%M:%S")
        file_list += [f"フォルダ一覧: {d}", f"作成日時: {now}", "-"*80, ""]

        def walk():
            try:
                for root, dirs, files in os.walk(d):
                    try:
                        rel = os.path.relpath(root, d)
                        depth = 0 if rel == "." else rel.count(os.sep) + 1
                    except Exception:
                        depth = 0
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
                            size = self.format_size(st.st_size)
                            file_list.append(f"{indent}📄 {f} ({size}) - {ts}")
                        except Exception as ex:
                            file_list.append(f"{indent}⚠️ {f} - {ex}")

                self.after(0, lambda: self.save_list(file_list))
            except Exception as ex:
                self.after(0, lambda: messagebox.showerror("エラー", str(ex)))

        threading.Thread(target=walk, daemon=True).start()

    def save_list(self, file_list):
        fn = filedialog.asksaveasfilename(
            title="ファイル一覧を保存",
            defaultextension=".txt",
            filetypes=[("テキストファイル","*.txt")],
            initialfile=f"ファイル一覧_{time.strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if not fn:
            return
        with open(fn, "w", encoding="utf-8") as f:
            f.write("\n".join(file_list))
        messagebox.showinfo("成功", "ファイル一覧を保存しました。")

    @staticmethod
    def format_size(n):
        for unit in ["B","KB","MB","GB","TB"]:
            if n < 1024:
                return f"{n:.2f} {unit}"
            n /= 1024
        return f"{n:.2f} PB"


if __name__ == "__main__":
    app = Mascot()
    app.mainloop()
