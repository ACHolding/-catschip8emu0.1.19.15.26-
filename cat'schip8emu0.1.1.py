#!/usr/bin/env python3
# ac's chip 8 emu 0.1.1 > $ PR
# Tkinter CHIP-8 emulator -- mGBA blue on black

import random
import tkinter as tk
from tkinter import filedialog, messagebox

# ---------------------------------------------------------------- theme
BLUE  = "#4a9eff"
BLACK = "#000000"
SCALE = 8                       # 64x32 * 8 = 512x256
FONT  = ("Courier New", 10, "bold")
FONT_S = ("Courier New", 9)

# ---------------------------------------------------------------- fontset
FONTSET = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
    0x20, 0x60, 0x20, 0x20, 0x70,  # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
    0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
    0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
    0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
    0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
    0xF0, 0x80, 0xF0, 0x80, 0x80,  # F
]

KEYMAP = {
    '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
    'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
    'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
    'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF,
}


# ================================================================ CPU
class Chip8:
    def __init__(self):
        self.reset()

    def reset(self):
        self.memory      = [0] * 4096
        self.V           = [0] * 16
        self.I           = 0
        self.PC          = 0x200
        self.stack       = []
        self.delay_timer = 0
        self.sound_timer = 0
        self.gfx         = [[0] * 64 for _ in range(32)]
        self.keys        = [0] * 16
        self.waiting     = False
        self.key_reg     = 0
        self.draw_flag   = True
        for i, b in enumerate(FONTSET):
            self.memory[0x50 + i] = b

    def load_rom(self, path):
        with open(path, "rb") as f:
            data = f.read()
        self.reset()
        for i, b in enumerate(data):
            if 0x200 + i < 4096:
                self.memory[0x200 + i] = b

    # ---------------------------------------------------------- opcodes
    def cycle(self):
        if self.waiting:
            return
        op = (self.memory[self.PC] << 8) | self.memory[self.PC + 1]
        self.PC = (self.PC + 2) & 0xFFF
        self.execute(op)

    def execute(self, op):
        vx  = (op & 0x0F00) >> 8
        vy  = (op & 0x00F0) >> 4
        n   = op & 0x000F
        nn  = op & 0x00FF
        nnn = op & 0x0FFF
        h   = op & 0xF000

        if h == 0x0000:
            if op == 0x00E0:
                self.gfx = [[0] * 64 for _ in range(32)]
                self.draw_flag = True
            elif op == 0x00EE:
                self.PC = self.stack.pop()
        elif h == 0x1000:
            self.PC = nnn
        elif h == 0x2000:
            self.stack.append(self.PC)
            self.PC = nnn
        elif h == 0x3000:
            if self.V[vx] == nn: self.PC += 2
        elif h == 0x4000:
            if self.V[vx] != nn: self.PC += 2
        elif h == 0x5000:
            if self.V[vx] == self.V[vy]: self.PC += 2
        elif h == 0x6000:
            self.V[vx] = nn
        elif h == 0x7000:
            self.V[vx] = (self.V[vx] + nn) & 0xFF
        elif h == 0x8000:
            self._alu(vx, vy, n)
        elif h == 0x9000:
            if self.V[vx] != self.V[vy]: self.PC += 2
        elif h == 0xA000:
            self.I = nnn
        elif h == 0xB000:
            self.PC = (nnn + self.V[0]) & 0xFFF
        elif h == 0xC000:
            self.V[vx] = random.randint(0, 255) & nn
        elif h == 0xD000:
            self._draw(vx, vy, n)
        elif h == 0xE000:
            if nn == 0x9E:
                if self.keys[self.V[vx] & 0xF]: self.PC += 2
            elif nn == 0xA1:
                if not self.keys[self.V[vx] & 0xF]: self.PC += 2
        elif h == 0xF000:
            self._misc(vx, nn)

        self.PC &= 0xFFF

    def _alu(self, vx, vy, n):
        if n == 0x0:
            self.V[vx] = self.V[vy]
        elif n == 0x1:
            self.V[vx] |= self.V[vy]
        elif n == 0x2:
            self.V[vx] &= self.V[vy]
        elif n == 0x3:
            self.V[vx] ^= self.V[vy]
        elif n == 0x4:
            s = self.V[vx] + self.V[vy]
            self.V[0xF] = 1 if s > 0xFF else 0
            self.V[vx] = s & 0xFF
        elif n == 0x5:
            self.V[0xF] = 1 if self.V[vx] >= self.V[vy] else 0
            self.V[vx] = (self.V[vx] - self.V[vy]) & 0xFF
        elif n == 0x6:
            self.V[0xF] = self.V[vx] & 1
            self.V[vx] >>= 1
        elif n == 0x7:
            self.V[0xF] = 1 if self.V[vy] >= self.V[vx] else 0
            self.V[vx] = (self.V[vy] - self.V[vx]) & 0xFF
        elif n == 0xE:
            self.V[0xF] = (self.V[vx] >> 7) & 1
            self.V[vx] = (self.V[vx] << 1) & 0xFF

    def _misc(self, vx, nn):
        if nn == 0x07:
            self.V[vx] = self.delay_timer
        elif nn == 0x0A:
            self.waiting = True
            self.key_reg = vx
        elif nn == 0x15:
            self.delay_timer = self.V[vx]
        elif nn == 0x18:
            self.sound_timer = self.V[vx]
        elif nn == 0x1E:
            self.I = (self.I + self.V[vx]) & 0xFFF
        elif nn == 0x29:
            self.I = 0x50 + (self.V[vx] & 0xF) * 5
        elif nn == 0x33:
            self.memory[self.I]     = self.V[vx] // 100
            self.memory[self.I + 1] = (self.V[vx] // 10) % 10
            self.memory[self.I + 2] = self.V[vx] % 10
        elif nn == 0x55:
            for i in range(vx + 1):
                self.memory[(self.I + i) & 0xFFF] = self.V[i]
        elif nn == 0x65:
            for i in range(vx + 1):
                self.V[i] = self.memory[(self.I + i) & 0xFFF]

    def _draw(self, vx, vy, n):
        x0 = self.V[vx] % 64
        y0 = self.V[vy] % 32
        rows = n if n else 16
        self.V[0xF] = 0
        for r in range(rows):
            py = (y0 + r) % 32
            bits = self.memory[(self.I + r) & 0xFFF]
            for c in range(8):
                if bits & (0x80 >> c):
                    px = (x0 + c) % 64
                    if self.gfx[py][px]:
                        self.V[0xF] = 1
                    self.gfx[py][px] ^= 1
        self.draw_flag = True


# ================================================================ GUI
class Emulator:
    CYCLES_PER_FRAME = 10

    def __init__(self, root):
        self.root = root
        self.cpu  = Chip8()
        self.running = False
        self.rom_name = "no rom"
        self.zoomed = None

        root.title("ac's chip 8 emu 0.1.1 > $ PR")
        root.geometry("600x400")
        root.resizable(False, False)
        root.configure(bg=BLACK)

        # ---- display -----------------------------------------------
        self.canvas = tk.Canvas(root, width=64 * SCALE, height=32 * SCALE,
                                bg=BLACK, highlightthickness=1,
                                highlightbackground=BLUE, bd=0)
        self.canvas.place(x=44, y=8)

        self.photo = tk.PhotoImage(width=64, height=32)
        self._blank()
        self.zoomed = self.photo.zoom(SCALE)
        self.img_id = self.canvas.create_image(0, 0, anchor="nw",
                                               image=self.zoomed)

        # ---- buttons -----------------------------------------------
        self.btn_load  = self._button("LOAD ROM", self.load_rom, 90)
        self.btn_pause = self._button("RUN",      self.toggle_pause, 235)
        self.btn_reset = self._button("RESET",    self.reset, 380)

        # ---- status / hints ----------------------------------------
        self.status = tk.Label(root, text="> $ PR  ready", bg=BLACK, fg=BLUE,
                               font=FONT_S, anchor="w")
        self.status.place(x=44, y=328, width=512)

        tk.Label(root,
                 text="keys  1 2 3 4  /  q w e r  /  a s d f  /  z x c v",
                 bg=BLACK, fg=BLUE, font=FONT_S, anchor="w"
                 ).place(x=44, y=350, width=512)

        tk.Label(root,
                 text="layout  123C / 456D / 789E / A0BF",
                 bg=BLACK, fg=BLUE, font=FONT_S, anchor="w"
                 ).place(x=44, y=372, width=512)

        # ---- input -------------------------------------------------
        root.bind("<KeyPress>",   self.on_press)
        root.bind("<KeyRelease>", self.on_release)
        root.focus_force()

        self.tick()

    # ------------------------------------------------------------ widgets
    def _button(self, text, cmd, x):
        b = tk.Button(self.root, text=text, command=cmd,
                      bg=BLACK, fg=BLUE,
                      activebackground=BLUE, activeforeground=BLACK,
                      highlightbackground=BLUE, highlightcolor=BLUE,
                      highlightthickness=1, bd=0, relief="flat",
                      font=FONT, cursor="hand2")
        b.place(x=x, y=282, width=130, height=32)
        return b

    # ------------------------------------------------------------ drawing
    def _blank(self):
        row = "{" + " ".join([BLACK] * 64) + "}"
        self.photo.put(" ".join([row] * 32))

    def render(self):
        rows = []
        for y in range(32):
            line = self.cpu.gfx[y]
            rows.append("{" + " ".join(BLUE if line[x] else BLACK
                                       for x in range(64)) + "}")
        self.photo.put(" ".join(rows))
        self.zoomed = self.photo.zoom(SCALE)
        self.canvas.itemconfig(self.img_id, image=self.zoomed)

    # ------------------------------------------------------------ control
    def load_rom(self):
        path = filedialog.askopenfilename(
            title="load chip-8 rom",
            filetypes=[("CHIP-8 ROMs", "*.ch8 *.rom *.bin *.c8"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            self.cpu.load_rom(path)
        except Exception as e:
            messagebox.showerror("ac's chip 8 emu", f"failed to load:\n{e}")
            return
        self.rom_name = path.split("/")[-1].split("\\")[-1]
        self.running = True
        self.btn_pause.config(text="PAUSE")
        self.status.config(text=f"> $ PR  running  {self.rom_name}")
        self.render()

    def toggle_pause(self):
        if self.rom_name == "no rom":
            return
        self.running = not self.running
        self.btn_pause.config(text="PAUSE" if self.running else "RUN")
        self.status.config(
            text=f"> $ PR  {'running' if self.running else 'paused'}  "
                 f"{self.rom_name}")

    def reset(self):
        self.cpu.load_rom.__self__  # noop, keeps linters quiet
        self.cpu.reset()
        self.running = False
        self.rom_name = "no rom"
        self.btn_pause.config(text="RUN")
        self.status.config(text="> $ PR  ready")
        self._blank()
        self.render()

    # ------------------------------------------------------------ input
    def on_press(self, event):
        k = event.char.lower()
        if k in KEYMAP:
            idx = KEYMAP[k]
            self.cpu.keys[idx] = 1
            if self.cpu.waiting:
                self.cpu.V[self.cpu.key_reg] = idx
                self.cpu.waiting = False

    def on_release(self, event):
        k = event.char.lower()
        if k in KEYMAP:
            self.cpu.keys[KEYMAP[k]] = 0

    # ------------------------------------------------------------ loop
    def tick(self):
        if self.running:
            for _ in range(self.CYCLES_PER_FRAME):
                self.cpu.cycle()
            if self.cpu.delay_timer > 0:
                self.cpu.delay_timer -= 1
            if self.cpu.sound_timer > 0:
                self.cpu.sound_timer -= 1
                # hook audio here if you want:
                #   winsound.Beep(440, 16)  /  self.root.bell()

        if self.cpu.draw_flag:
            self.render()
            self.cpu.draw_flag = False

        self.root.after(16, self.tick)      # ~60 Hz


# ================================================================ main
if __name__ == "__main__":
    root = tk.Tk()
    Emulator(root)
    root.mainloop()