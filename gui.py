"""CoverCraft desktop GUI - a thin Tkinter front-end over make_cover.generate_pdf().

This is what CoverCraftSetup.msi installs and points its Start Menu shortcut
at (via a private, bundled Python interpreter - see scripts/build-msi.ps1 and
installer/CoverCraft.wxs). Running it directly with the dev venv also works:

    .venv\\Scripts\\python.exe gui.py
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import tidalapi

import make_cover as mc

_SUCCESS_PREFIX = "__SUCCESS__"


class CoverCraftApp:
    def __init__(self, root):
        self.root = root
        root.title("CoverCraft")
        root.resizable(False, False)
        try:
            root.iconbitmap(default=str(mc.resource_path("assets/icon.ico")))
        except tk.TclError:
            pass  # icon missing (e.g. dev checkout without the asset) - non-fatal

        pad = {"padx": 10, "pady": 6}

        frm = ttk.Frame(root)
        frm.grid(row=0, column=0, sticky="nsew", **pad)

        ttk.Label(frm, text="Tidal Album ID:").grid(row=0, column=0, sticky="w")
        self.album_id_var = tk.StringVar()
        self.album_entry = ttk.Entry(frm, textvariable=self.album_id_var, width=30)
        self.album_entry.grid(row=0, column=1, sticky="we", padx=(6, 0))
        self.album_entry.focus_set()

        self.generate_btn = ttk.Button(frm, text="Generate PDF", command=self.on_generate)
        self.generate_btn.grid(row=1, column=0, columnspan=2, pady=(10, 4), sticky="we")

        self.status_text = tk.Text(frm, width=56, height=12, state="disabled", wrap="word")
        self.status_text.grid(row=2, column=0, columnspan=2, sticky="nsew")

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=3, column=0, columnspan=2, sticky="we", pady=(6, 0))
        ttk.Button(btn_row, text="Open output folder", command=self.open_output_folder).pack(side="left")

        self.log_queue = queue.Queue()
        self.worker = None
        self.root.bind("<Return>", lambda _e: self.on_generate())
        self.root.after(100, self._drain_log_queue)

    def log(self, message):
        # Called from the worker thread; hand off to the Tk main loop via the queue.
        self.log_queue.put(str(message))

    def _append_line(self, message):
        self.status_text.configure(state="normal")
        self.status_text.insert("end", message + "\n")
        self.status_text.see("end")
        self.status_text.configure(state="disabled")

    def _drain_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                if message.startswith(_SUCCESS_PREFIX):
                    pdf_path = message[len(_SUCCESS_PREFIX):]
                    messagebox.showinfo("CoverCraft", f"Done!\n{pdf_path}")
                else:
                    self._append_line(message)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log_queue)

    def on_generate(self):
        if self.worker and self.worker.is_alive():
            return

        raw_id = self.album_id_var.get().strip()
        if not raw_id.isdigit():
            messagebox.showerror("CoverCraft", "Enter a numeric Tidal album ID.")
            return
        album_id = int(raw_id)

        self.generate_btn.configure(state="disabled")
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.configure(state="disabled")

        self.worker = threading.Thread(target=self._run, args=(album_id,), daemon=True)
        self.worker.start()

    def _run(self, album_id):
        try:
            pdf_path = mc.generate_pdf(album_id, log=self.log)
            self.log_queue.put(f"{_SUCCESS_PREFIX}{pdf_path}")
        except tidalapi.exceptions.ObjectNotFound:
            self.log_queue.put("Album not found on Tidal.")
        except Exception as exc:  # noqa: BLE001 - surface any failure to the user
            self.log_queue.put(f"Error: {exc}")
        finally:
            self.root.after(0, lambda: self.generate_btn.configure(state="normal"))

    def open_output_folder(self):
        mc.DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(mc.DEFAULT_OUTPUT_DIR)  # noqa: S606 - Windows-only app


def main():
    root = tk.Tk()
    CoverCraftApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
