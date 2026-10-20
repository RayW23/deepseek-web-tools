"""Native desktop UI. All widget access stays on the Tk main thread."""

import os
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from .client import Cancelled, DeepSeekClient, validate_url
from .output import render
from .config import config_path, resolve_api_key, save_api_key


class App:
    def __init__(self, root):
        self.root = root
        root.title("DeepSeek Web · 搜索与抓取")
        root.geometry("1120x780")
        root.minsize(850, 620)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.result = None
        self.export_data = None
        try:
            initial_key = resolve_api_key()
        except ValueError as exc:
            initial_key = ""
            root.after(0, lambda message=str(exc): messagebox.showerror("配置错误", message))
        self.key = tk.StringVar(value=initial_key)
        self.query = tk.StringVar()
        self.url = tk.StringVar()
        self.count = tk.StringVar(value="10")
        self.original = tk.StringVar()
        self.local = tk.StringVar()
        self.need_content = tk.BooleanVar()
        self.status = tk.StringVar(value="就绪 · 点击“保存配置”可将 API Key 写入本地文件")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f3f6fc")
        style.configure("TLabel", background="#f3f6fc", font=("Microsoft YaHei UI", 10))
        style.configure("TButton", padding=(12, 7))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 22, "bold"), foreground="#254edb")
        style.configure("Treeview", rowheight=30, font=("Microsoft YaHei UI", 10))
        outer = ttk.Frame(root, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="DeepSeek Web", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="原生网页搜索与 Markdown 抓取工作台").pack(anchor="w", pady=(0, 12))
        auth = ttk.Frame(outer)
        auth.pack(fill="x", pady=(0, 10))
        ttk.Label(auth, text="API Key").pack(side="left", padx=(0, 12))
        ttk.Entry(auth, textvariable=self.key, show="●", width=48).pack(side="left", fill="x", expand=True)
        ttk.Button(auth, text="保存配置", command=self.save_config).pack(side="left", padx=8)

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="x")
        search = ttk.Frame(notebook, padding=12)
        fetch = ttk.Frame(notebook, padding=12)
        notebook.add(search, text="  网页搜索  ")
        notebook.add(fetch, text="  URL 抓取  ")
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="搜索词").grid(row=0, column=0, sticky="w", padx=(0, 12))
        entry = ttk.Entry(search, textvariable=self.query)
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind("<Return>", lambda _: self.search())
        self.search_button = ttk.Button(search, text="搜索", command=self.search)
        self.search_button.grid(row=0, column=2, padx=(10, 0))
        ttk.Label(search, text='支持 site:github.com、lang:zh,en、after:2026-01-01、"精确短语"；最多 128 字符').grid(
            row=1, column=0, columnspan=3, sticky="w", pady=6)
        options = ttk.Frame(search)
        options.grid(row=2, column=0, columnspan=3, sticky="ew")
        ttk.Label(options, text="条数").pack(side="left")
        ttk.Spinbox(options, from_=1, to=50, textvariable=self.count, width=5).pack(side="left", padx=8)
        ttk.Checkbutton(options, text="包含正文", variable=self.need_content).pack(side="left")
        ttk.Label(options, text="  本地化 IP").pack(side="left", padx=8)
        ttk.Entry(options, textvariable=self.local, width=20).pack(side="left")
        ttk.Label(search, text="原始问题（可选）").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(search, textvariable=self.original).grid(row=3, column=1, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Label(fetch, text="网页 URL").pack(side="left", padx=(0, 12))
        url_entry = ttk.Entry(fetch, textvariable=self.url)
        url_entry.pack(side="left", fill="x", expand=True)
        url_entry.bind("<Return>", lambda _: self.fetch_url())
        self.fetch_button = ttk.Button(fetch, text="抓取正文", command=self.fetch_url)
        self.fetch_button.pack(side="left", padx=(10, 0))

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=10)
        self.selected_button = ttk.Button(toolbar, text="抓取选中结果", command=self.fetch_selected)
        self.selected_button.pack(side="left")
        ttk.Button(toolbar, text="浏览器打开", command=self.open_selected).pack(side="left", padx=6)
        ttk.Button(toolbar, text="导出当前内容…", command=self.export).pack(side="left")
        self.cancel_button = ttk.Button(toolbar, text="取消", command=self.stop, state="disabled")
        self.cancel_button.pack(side="right")
        self.progress = ttk.Progressbar(toolbar, mode="indeterminate", length=110)
        self.progress.pack(side="right", padx=12)

        panes = ttk.Panedwindow(outer, orient="vertical")
        panes.pack(fill="both", expand=True)
        results_frame = ttk.Frame(panes)
        panes.add(results_frame, weight=1)
        self.tree = ttk.Treeview(results_frame, columns=("title", "site", "score", "authority", "date"), show="headings", height=6)
        for name, title, width in [("title", "标题", 430), ("site", "站点", 150),
                                   ("score", "相关性", 70), ("authority", "权威性", 70), ("date", "日期", 160)]:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, minwidth=50)
        scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.tree.bind("<Double-1>", lambda _: self.fetch_selected())
        self.preview = ScrolledText(panes, wrap="word", font=("Microsoft YaHei UI", 10),
                                    background="#ffffff", relief="flat", padx=14, pady=12, height=12)
        panes.add(self.preview, weight=2)
        self.show("输入搜索词开始探索。\n\n搜索结果可预览摘要、查看原始 JSON、抓取正文并导出。\n"
                  "导出搜索结果时包含全部条目；抓取后导出当前网页。\n\n正文以 Markdown 源文本显示，不执行网页脚本。")
        ttk.Label(outer, textvariable=self.status).pack(anchor="w", pady=(10, 0))
        ttk.Button(outer, text="查看当前原始 JSON", command=self.show_json).pack(anchor="e")
        self.root.after(80, self.poll)

    def save_config(self):
        try:
            key = self.key.get().strip()
            if not key:
                raise ValueError("API Key 不能为空")
            path = save_api_key(key)
            self.status.set("已保存到本地明文配置：" + str(path))
        except (OSError, ValueError) as exc:
            messagebox.showerror("保存失败", str(exc))

    def show(self, text):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def run(self, kind, payload):
        if self.busy:
            return
        try:
            client = DeepSeekClient(self.key.get())
        except ValueError as exc:
            messagebox.showerror("设置错误", str(exc))
            return
        self.cancel = threading.Event()
        cancel = self.cancel
        self.busy = True
        for button in (self.search_button, self.fetch_button, self.selected_button):
            button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.status.set("正在搜索…" if kind == "search" else "正在抓取…")
        self.progress.start()

        def worker():
            try:
                data = getattr(client, kind)(**payload, cancel=cancel)
                self.events.put((kind, data))
            except Exception as exc:
                self.events.put(("error", exc))
        threading.Thread(target=worker, daemon=True).start()

    def search(self):
        try:
            count = int(self.count.get())
        except ValueError:
            messagebox.showerror("参数错误", "条数必须是 1～50 的整数")
            return
        self.run("search", dict(query=self.query.get(), count=count, need_content=self.need_content.get(),
                                ori_question=self.original.get() or None, localization=self.local.get()))

    def fetch_url(self):
        self.run("fetch", {"url": self.url.get()})

    def selected(self):
        selection = self.tree.selection()
        return self.result["results"][int(selection[0])] if selection and self.result else None

    def fetch_selected(self):
        row = self.selected()
        if row:
            self.url.set(row["url"])
            self.fetch_url()
        else:
            self.status.set("请先选择一条搜索结果")

    def open_selected(self):
        row = self.selected()
        if row:
            try:
                webbrowser.open(validate_url(row["url"]))
            except ValueError as exc:
                messagebox.showerror("链接错误", str(exc))

    def select(self, _=None):
        row = self.selected()
        if row:
            self.export_data = self.result
            self.show(render({"results": [row]}, "markdown"))

    def show_json(self):
        if self.export_data is not None:
            self.show(render(self.export_data))

    def export(self):
        if self.export_data is None:
            self.status.set("还没有可导出的内容")
            return
        path = filedialog.asksaveasfilename(defaultextension=".md", filetypes=[("Markdown", "*.md"), ("JSON", "*.json")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(render(self.export_data, "json" if path.lower().endswith(".json") else "markdown"))
                self.status.set("已导出：" + path)
            except OSError as exc:
                messagebox.showerror("导出失败", str(exc))

    def stop(self):
        self.cancel.set()
        self.status.set("正在取消，等待当前网络请求返回（最多一个请求超时周期）…")

    def poll(self):
        try:
            kind, data = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.progress.stop()
            for button in (self.search_button, self.fetch_button, self.selected_button):
                button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            if self.cancel.is_set() or isinstance(data, Cancelled):
                self.status.set("已取消")
            elif kind == "error":
                self.status.set("请求失败：" + str(data))
                messagebox.showerror("请求失败", str(data))
            else:
                self.export_data = data
                if kind == "search":
                    self.result = data
                    self.tree.delete(*self.tree.get_children())
                    for i, row in enumerate(data["results"]):
                        self.tree.insert("", "end", iid=str(i), values=(row["title"], row.get("site_name") or "—",
                            row.get("rerank_score", "—"), row.get("authority", "—"), row.get("date") or "—"))
                    self.status.set(f"找到 {len(data['results'])} 条结果 · 选择结果预览，双击抓取正文")
                else:
                    # Clear selection so the displayed fetched page and export stay in sync.
                    self.tree.selection_remove(*self.tree.selection())
                    self.status.set("抓取完成 · 可导出 Markdown / JSON")
                self.show(render(data, "markdown"))
        self.root.after(80, self.poll)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
