import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from PIL import ImageTk
from core import ROOT, SkinStore, compose, compose_single, export_icon, create_sample, skin_layout, fit_icon_content, icon_bytes
from windows_size import default_folder_bounds

COLORS = {'紫色': '#9973df', '蓝色': '#6aaee8', '黄色': '#f1c94f', '橙色': '#ee9b55', '绿色': '#79bc92', '白色': '#e7e8ef'}

class App:
    def __init__(self, window):
        self.window = window
        window.title('Folder Skin · 文件夹换肤')
        window.geometry('940x840')
        window.minsize(880, 820)
        self.store = SkinStore()
        for name in ('assets', 'generated_icons'):
            (ROOT / name).mkdir(exist_ok=True)
        sample = ROOT / 'assets' / 'sample_ghost.png'
        if not sample.exists():
            create_sample(sample)
        self.folder = tk.StringVar()
        self.character = tk.StringVar(value=str(sample))
        self.mode = tk.StringVar(value='角色 + 文件夹')
        self.folder_skin = tk.StringVar()
        self.skin_scale = tk.DoubleVar(value=1)
        self.skin_offset = tk.DoubleVar(value=0)
        self.character_x = tk.DoubleVar(value=0)
        self.skin_x = tk.DoubleVar(value=0)
        self.folder_bounds = None
        self.fill_icon = tk.BooleanVar(value=True)
        self.output_zoom = tk.DoubleVar(value=1.0)
        self.zoom_label = tk.StringVar(value='成品放大：100%')
        self.depth = tk.BooleanVar(value=True)
        self.opening_left = tk.DoubleVar(value=.35)
        self.opening_right = tk.DoubleVar(value=.25)
        self.shadow = tk.DoubleVar(value=.35)
        self.guide = tk.BooleanVar(value=False)
        self.color = '#9973df'
        self.scale = tk.DoubleVar(value=1)
        self.offset = tk.DoubleVar(value=0)
        self.status = tk.StringVar(value='先预览，再选择需要换肤的文件夹。')
        self.pending = None
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', padding=8)
        outer = ttk.Frame(window, padding=22)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='给文件夹换一件新衣服', font=('Microsoft YaHei UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='角色 PNG + 文件夹皮肤 PNG · 本地生成 · 随时恢复', padding=(0, 7, 0, 18)).pack(anchor='w')
        middle = ttk.Frame(outer)
        middle.pack(fill='both', expand=True)
        left = ttk.Frame(middle, width=430)
        left.pack(side='left', fill='both', expand=True)
        right = ttk.Frame(middle, padding=(20, 0, 0, 0))
        right.pack(side='right', fill='y')
        mode_row = ttk.Frame(left)
        mode_row.pack(fill='x', pady=(0, 4))
        ttk.Label(mode_row, text='制作模式：').pack(side='left')
        ttk.Combobox(mode_row, textvariable=self.mode, state='readonly',
                     values=('角色 + 文件夹', '仅角色 PNG', '仅文件夹 PNG'), width=18).pack(side='left')
        self.row(left, '1. 目标文件夹（仅应用时需要）', self.folder, self.pick_folder)
        self.row(left, '2. 角色 PNG', self.character, self.pick_character)
        self.row(left, '3. 文件夹皮肤 PNG（可选）', self.folder_skin, self.pick_skin)
        ttk.Button(left, text='清除皮肤，使用纯色文件夹', command=lambda: self.folder_skin.set('')).pack(anchor='w', pady=5)
        ttk.Label(left, text='纯色文件夹颜色（未选择皮肤 PNG 时生效）').pack(anchor='w', pady=(6, 6))
        palette = ttk.Frame(left)
        palette.pack(anchor='w')
        for name, color in COLORS.items():
            tk.Button(palette, text=name, bg=color, relief='flat', width=4, command=lambda c=color: self.set_color(c)).pack(side='left', padx=2)
        ttk.Button(left, text='自定义颜色 / RGB', command=self.custom_color).pack(anchor='w', pady=7)
        ttk.Label(left, text='角色大小').pack(anchor='w')
        ttk.Scale(left, from_=.5, to=1.5, variable=self.scale, command=self.schedule).pack(fill='x')
        ttk.Label(left, text='角色上下位置').pack(anchor='w', pady=(9, 0))
        ttk.Scale(left, from_=-95, to=95, variable=self.offset, command=self.schedule).pack(fill='x')
        ttk.Label(left, text='角色左右位置').pack(anchor='w', pady=(9, 0))
        ttk.Scale(left, from_=-180, to=180, variable=self.character_x, command=self.schedule).pack(fill='x')
        ttk.Button(left, text='匹配 Windows 默认文件夹大小', command=lambda: self.run(self.match_default_size)).pack(anchor='w', pady=(12, 3))
        ttk.Button(left, text='恢复原构图尺寸', command=self.reset_folder_size).pack(anchor='w', pady=3)
        ttk.Checkbutton(left, text='放大成品，去除四周留白（推荐）', variable=self.fill_icon, command=self.schedule).pack(anchor='w', pady=6)
        ttk.Label(left, text='单图模式只读取对应 PNG，不合成另一张图。\n立体遮挡仅在「角色 + 文件夹」模式生效。', foreground='#666666').pack(anchor='w', pady=10)
        self.preview = tk.Canvas(right, width=300, height=300, highlightthickness=0)
        self.preview.pack()
        ttk.Label(right, text='透明背景预览', anchor='center').pack(fill='x', pady=8)
        tabs = ttk.Notebook(right)
        tabs.pack(fill='x')
        placement = ttk.Frame(tabs, padding=6)
        depth_panel = ttk.Frame(tabs, padding=6)
        tabs.add(depth_panel, text='立体遮挡')
        tabs.add(placement, text='皮肤位置')
        output_panel = ttk.Frame(tabs, padding=6)
        tabs.add(output_panel, text='成品大小')
        system_panel = ttk.Frame(tabs, padding=6)
        tabs.add(system_panel, text='系统默认')
        self.system_busy = False
        self.system_icon = tk.StringVar()
        icon_row = ttk.Frame(system_panel)
        icon_row.pack(fill='x', pady=3)
        ttk.Entry(icon_row, textvariable=self.system_icon, width=20).pack(side='left', fill='x', expand=True)
        ttk.Button(icon_row, text='导入 ICO', command=lambda: self.run(self.pick_system_icon)).pack(side='right', padx=(4, 0))
        self.system_buttons = []
        for title, operation in [('设为系统默认文件夹图标', 'apply'), ('恢复系统默认图标', 'restore')]:
            button = ttk.Button(system_panel, text=title, command=lambda op=operation: self.run(lambda: self.system_action(op)))
            button.pack(fill='x', pady=5)
            self.system_buttons.append(button)
        ttk.Button(system_panel, text='刷新当前桌面图标', command=lambda: self.run(self.refresh_system_icons)).pack(fill='x', pady=3)
        ttk.Label(system_panel, text='使用导入的 ICO，独立于当前构图。\n需要管理员权限；保留恢复备份。\n部分缩略图和自定义文件夹不受影响。\n未更新时请注销后重新登录。', wraplength=280).pack(anchor='w', pady=5)
        ttk.Label(output_panel, textvariable=self.zoom_label).pack(anchor='w')
        ttk.Scale(output_panel, from_=1, to=1.6, variable=self.output_zoom, command=self.change_zoom).pack(fill='x')
        ttk.Button(output_panel, text='放大到 120%', command=lambda: self.set_zoom(1.2)).pack(fill='x', pady=5)
        ttk.Button(output_panel, text='恢复完整显示', command=lambda: self.set_zoom(1)).pack(fill='x', pady=5)
        ttk.Label(output_panel, text='超过 100% 可能裁掉顶部或两侧。\n预览与应用结果一致。').pack(anchor='w', pady=5)
        ttk.Label(placement, text='文件夹大小（纯色 / PNG）').pack(anchor='w')
        ttk.Scale(placement, from_=.5, to=1.3, variable=self.skin_scale, command=self.schedule).pack(fill='x')
        ttk.Label(placement, text='文件夹上下位置').pack(anchor='w', pady=(6, 0))
        ttk.Scale(placement, from_=-100, to=35, variable=self.skin_offset, command=self.schedule).pack(fill='x')
        ttk.Label(placement, text='文件夹左右位置').pack(anchor='w', pady=(6, 0))
        ttk.Scale(placement, from_=-180, to=180, variable=self.skin_x, command=self.schedule).pack(fill='x')
        ttk.Checkbutton(depth_panel, text='角色进入文件夹', variable=self.depth, command=self.schedule).pack(anchor='w')
        for label, variable in [('开口左端高度', self.opening_left), ('开口右端高度', self.opening_right), ('开口阴影强度', self.shadow)]:
            ttk.Label(depth_panel, text=label).pack(anchor='w')
            ttk.Scale(depth_panel, from_=0, to=1, variable=variable, command=self.schedule).pack(fill='x')
        ttk.Checkbutton(depth_panel, text='显示开口辅助线（不导出）', variable=self.guide, command=self.schedule).pack(anchor='w')
        ttk.Button(right, text='手动保存 PNG + ICO', command=lambda: self.run(self.export)).pack(fill='x', pady=4)
        ttk.Button(right, text='应用皮肤', command=lambda: self.run(self.apply)).pack(fill='x', pady=4)
        actions = ttk.Frame(outer)
        actions.pack(fill='x', pady=(16, 10))
        ttk.Button(actions, text='恢复所选文件夹', command=lambda: self.run(self.restore)).pack(side='left')
        ttk.Button(actions, text='恢复全部已换肤文件夹', command=lambda: self.run(self.restore_all)).pack(side='left', padx=8)
        ttk.Button(actions, text='打开输出目录', command=lambda: os.startfile(ROOT / 'generated_icons')).pack(side='right')
        ttk.Label(outer, textvariable=self.status, wraplength=800, foreground='#514078').pack(anchor='w')
        self.character.trace_add('write', self.schedule)
        self.folder_skin.trace_add('write', self.schedule)
        self.mode.trace_add('write', self.schedule)
        self.draw()

    def row(self, parent, title, variable, command):
        ttk.Label(parent, text=title).pack(anchor='w', pady=(9, 5))
        row = ttk.Frame(parent)
        row.pack(fill='x')
        ttk.Entry(row, textvariable=variable).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='选择', command=command).pack(side='right', padx=(6, 0))

    def pick_folder(self):
        path = filedialog.askdirectory(title='选择要换肤的普通文件夹')
        if path:
            self.folder.set(path)

    def pick_character(self):
        path = filedialog.askopenfilename(title='选择透明背景角色', filetypes=[('PNG 图片', '*.png')], initialdir=ROOT / 'assets')
        if path:
            self.character.set(path)

    def custom_color(self):
        _, color = colorchooser.askcolor(self.color)
        if color:
            self.set_color(color)

    def pick_skin(self):
        path = filedialog.askopenfilename(title='选择文件夹皮肤 PNG', filetypes=[('PNG 图片', '*.png')], initialdir=ROOT / 'assets')
        if path:
            self.folder_skin.set(path)

    def set_color(self, color):
        self.color = color
        self.schedule()

    def match_default_size(self):
        self.folder_bounds = default_folder_bounds()
        self.skin_scale.set(1)
        self.skin_offset.set(0)
        self.skin_x.set(0)
        self.schedule()
        self.status.set('已按本机默认文件夹轮廓等比例匹配并居中。宽高比不同的素材会留白；屏幕大小仍由桌面视图控制。')

    def reset_folder_size(self):
        self.folder_bounds = None
        self.skin_scale.set(1)
        self.skin_offset.set(0)
        self.skin_x.set(0)
        self.schedule()
        self.status.set('已恢复原构图的文件夹尺寸和位置。')

    def schedule(self, *_):
        if self.pending:
            self.window.after_cancel(self.pending)
        self.pending = self.window.after(100, self.draw)

    def change_zoom(self, *_):
        self.fill_icon.set(True)
        self.zoom_label.set(f'成品放大：{self.output_zoom.get():.0%}')
        self.schedule()

    def set_zoom(self, value):
        self.output_zoom.set(value)
        self.change_zoom()

    def render(self):
        if self.mode.get() == '仅角色 PNG':
            result = compose_single(self.character.get().strip(), self.scale.get(), self.character_x.get(), self.offset.get())
        elif self.mode.get() == '仅文件夹 PNG':
            result = compose_single(self.folder_skin.get().strip(), self.skin_scale.get(), self.skin_x.get(), self.skin_offset.get())
        else:
            result = compose(self.character.get(), self.color, self.scale.get(), self.offset.get(),
                       folder_skin=self.folder_skin.get().strip() or None,
                       skin_scale=self.skin_scale.get(), skin_offset=self.skin_offset.get(),
                       depth=self.depth.get(), opening_left=self.opening_left.get(),
                       opening_right=self.opening_right.get(), shadow=self.shadow.get(),
                       character_x=self.character_x.get(), skin_x=self.skin_x.get(),
                       folder_bounds=self.folder_bounds)
        return fit_icon_content(result, zoom=self.output_zoom.get()) if self.fill_icon.get() else (result, (1, 1, 0, 0))

    def image(self):
        return self.render()[0]

    def draw(self):
        self.pending = None
        self.preview.delete('all')
        for y in range(0, 300, 15):
            for x in range(0, 300, 15):
                self.preview.create_rectangle(x, y, x+15, y+15, fill='#f3f1f7' if (x+y)//15 % 2 else '#ffffff', outline='')
        try:
            result, (sx, sy, tx, ty) = self.render()
            self.photo = ImageTk.PhotoImage(result.resize((300, 300)))
            self.preview.create_image(150, 150, image=self.photo)
            if self.mode.get() == '角色 + 文件夹' and self.guide.get() and self.depth.get() and self.folder_skin.get().strip():
                skin, x, y = skin_layout(self.folder_skin.get().strip(), self.skin_scale.get(), self.skin_offset.get(),
                                         self.skin_x.get(), self.folder_bounds)
                factor = 300 / 512
                self.preview.create_line((x * sx + tx) * factor, ((y + skin.height * self.opening_left.get()) * sy + ty) * factor,
                                         ((x + skin.width) * sx + tx) * factor, ((y + skin.height * self.opening_right.get()) * sy + ty) * factor,
                                         fill='#00a6c8', width=2, dash=(5, 3))
        except Exception as exc:
            self.status.set(str(exc))

    def run(self, action):
        try:
            action()
        except Exception as exc:
            self.status.set('未完成：' + str(exc))
            messagebox.showerror('操作未完成', str(exc))

    def export(self):
        from datetime import datetime
        name = datetime.now().strftime('skin_%Y%m%d_%H%M%S.png')
        chosen = filedialog.asksaveasfilename(title='保存 PNG 和同名 ICO',
                    initialdir=ROOT / 'generated_icons', initialfile=name,
                    defaultextension='.png', filetypes=[('PNG 图片（同时保存 ICO）', '*.png')],
                    confirmoverwrite=False)
        if not chosen:
            return
        destination = Path(chosen)
        existing = [p for p in (destination.with_suffix('.png'), destination.with_suffix('.ico')) if p.exists()]
        if existing and not messagebox.askyesno('覆盖已有文件？', '以下文件已存在：\n' + '\n'.join(map(str, existing)) + '\n是否覆盖？'):
            return
        ico = export_icon(self.image(), destination)
        self.status.set('已手动保存 PNG 和 ICO：' + str(ico.parent))
        return ico

    def apply(self):
        if not self.folder.get().strip():
            raise ValueError('请先选择目标文件夹。')
        self.store.target(self.folder.get())
        self.store.apply(self.folder.get(), icon_bytes(self.image()))
        self.status.set('已应用皮肤。若未立即显示，请在桌面或文件夹窗口按 F5。')

    def restore(self):
        if not self.folder.get().strip():
            raise ValueError('请先选择需要恢复的文件夹。')
        self.store.restore(self.folder.get())
        self.status.set('已恢复换肤前的图标和设置，其他文件保持不变。')

    def restore_all(self):
        count, failures = self.store.restore_all()
        self.status.set(f'已恢复 {count} 个文件夹；{len(failures)} 个未完成。')
        if failures:
            messagebox.showwarning('部分文件夹保留待恢复记录', '\n'.join(failures))

    def pick_system_icon(self):
        from system_skin import validate_icon
        chosen = filedialog.askopenfilename(title='导入系统默认文件夹 ICO',
                    initialdir=ROOT / 'generated_icons', filetypes=[('Windows 图标', '*.ico')])
        if not chosen:
            return
        sizes = validate_icon(Path(chosen).read_bytes())
        self.system_icon.set(chosen)
        self.status.set('已导入系统图标：' + Path(chosen).name + '（' + '、'.join(str(w) for w, h in sizes) + ' 像素）')

    def refresh_system_icons(self):
        from system_skin import refresh_current_session
        refresh_current_session()
        self.status.set('已请求当前桌面刷新；若新建普通空文件夹仍未更新，请注销后重新登录。已有单独皮肤和内容缩略图可能覆盖系统默认图标。')

    def system_payload(self):
        from system_skin import validate_icon
        path = self.system_icon.get().strip()
        if not path:
            raise ValueError('请先在「系统默认」页导入一个 .ico 文件。')
        payload = Path(path).read_bytes()
        validate_icon(payload)
        return payload

    def system_action(self, operation):
        if self.system_busy:
            return
        import queue
        import tempfile
        import threading
        from system_skin import run_elevated, prepare_request
        payload = self.system_payload() if operation == 'apply' else None
        results = queue.Queue()
        self.system_busy = True
        for button in self.system_buttons:
            button.state(['disabled'])
        self.status.set('正在执行系统图标操作，请处理 Windows 管理员权限提示…')

        def worker():
            try:
                with tempfile.TemporaryDirectory(prefix='folder_skin_system_') as directory:
                    prepare_request(directory, payload)
                    run_elevated(operation, directory)
                results.put(None)
            except Exception as exc:
                results.put(str(exc))

        def completed():
            try:
                error = results.get_nowait()
            except queue.Empty:
                self.window.after(150, completed)
                return
            self.system_busy = False
            for button in self.system_buttons:
                button.state(['!disabled'])
            if error:
                self.status.set('系统图标操作未完成：' + error)
                messagebox.showerror('系统图标操作未完成', error)
            else:
                default_folder_bounds.cache_clear()
                self.status.set(('系统图标设置已写入并校验。' if operation == 'apply' else '已恢复系统图标原设置。') + '已请求桌面刷新；若新建空文件夹仍未更新，请注销后重新登录。')

        threading.Thread(target=worker, daemon=False).start()
        self.window.after(150, completed)

if __name__ == '__main__':
    window = tk.Tk()
    App(window)
    window.mainloop()
