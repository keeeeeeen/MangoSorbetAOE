import pygame
import sys
import random
import math
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import threading

import serial
import serial.tools.list_ports

def pytime_ms():
    return int(time.perf_counter() * 1000)

pygame.mixer.init()
pygame.mixer.music.load("Stateside.mp3")

# ── Constants ──────────────────────────────────────────────────────────────────
W, H = 1280, 720
FPS  = 60

# Colors
BG        = (8, 5, 20)
NEON_CYAN = (0, 255, 220)
NEON_PINK = (255, 30, 120)
NEON_YELL = (255, 220, 0)
NEON_PURP = (180, 0, 255)
WHITE     = (255, 255, 255)
GRAY      = (80, 80, 100)
DARK_GRAY = (20, 18, 40)
GREEN     = (0, 255, 100)
RED_NEG   = (255, 60, 60)

ARROW_COLORS = {
    "LEFT":  NEON_CYAN,
    "RIGHT": NEON_PINK,
    "UP":    NEON_YELL,
    "DOWN":  NEON_PURP,
}
DIRECTIONS = ["LEFT", "RIGHT", "UP", "DOWN"]

# Timing windows (ms)
PERFECT_WINDOW = 150
GOOD_WINDOW    = 300
OK_WINDOW      = 500

POINTS = {
    "PERFECT": 300,
    "GOOD":    150,
    "OK":      60,
    "MISS":    0,
    "WRONG":   -50,
}

class SerialReader(threading.Thread):
    def __init__(self, port: str = "COM5", baud: int = 9600):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self._events: list[tuple[str, int]] = []
        self._lock = threading.Lock()
        self.connected = False

    def run(self):
        import serial
        try:
            ser = serial.Serial("COM5", 9600, timeout=1)
            print("Connected")
            self.connected = True

            while True:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                direction = line.strip().upper()

                if direction in ("LEFT", "RIGHT", "UP", "DOWN"):
                    with self._lock:
                        self._events.append(direction)

        except Exception:
            self.connected = False
            print("NOT connected")

    def get_pending_slices(self):
        with self._lock:
            evs = self._events[:]
            self._events.clear()
        return evs

# ── Game Data Classes ──────────────────────────────────────────────────────────
class SliceState(Enum):
    WAITING = "waiting"
    ACTIVE  = "active"
    HIT     = "hit"
    MISS    = "miss"

@dataclass
class SliceTarget:
    direction:   str
    spawn_time:  float
    target_time: float
    x: float
    y: float
    radius:          int        = 70
    state:           SliceState = SliceState.WAITING
    hit_label:       str        = ""
    hit_label_alpha: int        = 255
    scale:           float      = 0.0
    slice_anim:      float      = 0.0

    def time_to_target(self) -> float:
        return self.target_time - pytime_ms()

@dataclass
class Particle:
    x: float; y: float
    vx: float; vy: float
    life: float; max_life: float
    color: tuple
    size: float

@dataclass
class ScorePopup:
    text: str
    x: float; y: float
    color: tuple
    life: float = 1.2
    age:  float = 0.0


# ── Drawing Helpers ────────────────────────────────────────────────────────────
def draw_arrow(surface, direction, cx, cy, size, color, alpha=255):
    s    = pygame.Surface((size*2+4, size*2+4), pygame.SRCALPHA)
    half = size
    tip  = size // 2
    pts  = {
        "RIGHT": [(half-size+tip, half-tip//2), (half+tip, half),     (half-size+tip, half+tip//2)],
        "LEFT":  [(half+size-tip, half-tip//2), (half-tip, half),     (half+size-tip, half+tip//2)],
        "UP":    [(half-tip//2,   half+size-tip),(half,    half-tip),  (half+tip//2,  half+size-tip)],
        "DOWN":  [(half-tip//2,   half-size+tip),(half,    half+tip),  (half+tip//2,  half-size+tip)],
    }
    shaft_pts = {
        "RIGHT": [(half-size, half-4),(half+tip//2, half-4),(half+tip//2, half+4),(half-size, half+4)],
        "LEFT":  [(half-tip//2,half-4),(half+size,  half-4),(half+size,  half+4),(half-tip//2,half+4)],
        "UP":    [(half-4, half-tip//2),(half-4, half+size),(half+4, half+size),(half+4, half-tip//2)],
        "DOWN":  [(half-4, half-size),(half-4, half+tip//2),(half+4, half+tip//2),(half+4, half-size)],
    }
    col = (*color, alpha)
    pygame.draw.polygon(s, col, pts[direction])
    pygame.draw.polygon(s, col, shaft_pts[direction])
    surface.blit(s, (int(cx - half - 2), int(cy - half - 2)))

def glow_circle(surface, color, cx, cy, r, width=3, layers=3):
    for i in range(layers, 0, -1):
        col = (*color, 60 // i)
        s   = pygame.Surface((r*2+layers*4, r*2+layers*4), pygame.SRCALPHA)
        pygame.draw.circle(s, col, (r+layers*2, r+layers*2), r+i*2, width+i*2)
        surface.blit(s, (cx-r-layers*2, cy-r-layers*2))
    pygame.draw.circle(surface, color, (cx, cy), r, width)


# ── Level Generator ────────────────────────────────────────────────────────────
def generate_level(difficulty: int) -> list[dict]:
    bpm      = 123 + difficulty * 5
    beat_ms  = int(60000 / bpm)
    n_beats  = 15 + difficulty * 5
    lead_in  = 2700
    beats    = []
    for i in range(n_beats):
        beats.append({
            "direction": random.choice(DIRECTIONS),
            "target_ms": lead_in + i * beat_ms + random.randint(-beat_ms//8, beat_ms//8),
        })
    beats.sort(key=lambda b: b["target_ms"])
    return beats


# ── Main Game Class ────────────────────────────────────────────────────────────
class WandSlicer:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("WandSlicer — Keyboard Edition")
        self.screen = pygame.display.set_mode((W, H))
        self.clock  = pygame.time.Clock()

        self.font_big   = pygame.font.SysFont("monospace", 72, bold=True)
        self.font_med   = pygame.font.SysFont("monospace", 36, bold=True)
        self.font_small = pygame.font.SysFont("monospace", 22)

        self.difficulty = 1
        self.state      = "MENU"   # MENU | PLAYING | PAUSED | GAMEOVER
        self._init_game_vars()

        self.stars        = [(random.randint(0,W), random.randint(0,H),
                               random.uniform(0.3, 1.5)) for _ in range(200)]
        self.scanline_surf = self._make_scanlines()

        try:
            # Try default port first
            self._serial = SerialReader("COM5")
            self._serial.start()
        except Exception:
            # Fallback: scan ports
            for p in serial.tools.list_ports.comports():
                try:
                    self._serial = SerialReader(p.device)
                    self._serial.start()
                    break
                except Exception:
                    pass

    # ── Init ───────────────────────────────────────────────────────────────────
    def _init_game_vars(self):
        self.targets:       list[SliceTarget] = []
        self.particles:     list[Particle]    = []
        self.popups:        list[ScorePopup]  = []
        self.beat_schedule: list[dict]        = []
        self.next_beat_idx  = 0
        self.level_start_ms = 0
        self.score     = 0
        self.combo     = 0
        self.max_combo = 0
        self.lives     = 3
        self.level_done = False

    def _make_scanlines(self) -> pygame.Surface:
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 4):
            pygame.draw.line(s, (0, 0, 0, 35), (0, y), (W, y))
        return s

    # ── Game State ─────────────────────────────────────────────────────────────
    def start_level(self):
        self.level_start_ms = pytime_ms()
        pygame.mixer.music.play()

        self._init_game_vars()
        self.beat_schedule  = generate_level(self.difficulty)
        self.level_start_ms = pytime_ms()
        self.state = "PLAYING"

    def elapsed_ms(self) -> int:
        return pytime_ms() - self.level_start_ms

    # ── Spawning ───────────────────────────────────────────────────────────────
    def spawn_target(self, beat: dict):
        margin   = 150
        x        = random.randint(margin, W - margin)
        y        = random.randint(120, H - 120)

        now = pytime_ms()
        target_abs = self.level_start_ms + beat["target_ms"]

        self.targets.append(SliceTarget(
            direction=beat["direction"],
            spawn_time=now,
            target_time=target_abs,
            x=x, y=y,
        ))

    # ── Slice Scoring ──────────────────────────────────────────────────────────
    def handle_slice(self, direction: str):

        pytime_ms() == time.perf_counter()

        # Find the closest active target
        best:    Optional[SliceTarget] = None
        best_dt: float = float("inf")
        for t in self.targets:
            if t.state != SliceState.ACTIVE:
                continue
            dt = abs(pytime_ms() - t.target_time)
            if dt < best_dt:
                best_dt, best = dt, t

        if best is None:
            return

        dt = pytime_ms() - best.target_time   # positive = late

        if best.direction == direction:
            if   abs(dt) <= PERFECT_WINDOW: label, pts, col = "PERFECT!", POINTS["PERFECT"], NEON_YELL
            elif abs(dt) <= GOOD_WINDOW:    label, pts, col = "GOOD",     POINTS["GOOD"],    GREEN
            elif abs(dt) <= OK_WINDOW:      label, pts, col = "OK",       POINTS["OK"],      NEON_CYAN
            else:                           label, pts, col = "LATE",     POINTS["OK"]//2,   GRAY

            self.combo    += 1
            self.max_combo = max(self.max_combo, self.combo)
            mult           = 1 + (self.combo // 5) * 0.5
            final_pts      = int(pts * mult)
            self.score    += final_pts

            best.state     = SliceState.HIT
            best.hit_label = label
            best.slice_anim = 0.0
            self._spawn_hit_particles(best, col)
            self.popups.append(ScorePopup(f"+{final_pts} {label}", best.x, best.y - 40, col))
            if self.combo > 1:
                self.popups.append(ScorePopup(f"x{self.combo} COMBO", best.x, best.y - 80, NEON_PINK))
        else:
            self.combo     = 0
            self.score     = max(0, self.score + POINTS["WRONG"])
            best.state     = SliceState.MISS
            best.hit_label = "WRONG!"
            self.lives    -= 1
            self._spawn_miss_particles(best)
            self.popups.append(ScorePopup("WRONG DIR!", best.x, best.y - 40, RED_NEG))

    def _spawn_hit_particles(self, t: SliceTarget, color):
        for _ in range(30):
            a = random.uniform(0, math.tau)
            spd = random.uniform(2, 9)
            self.particles.append(Particle(
                x=t.x, y=t.y, vx=math.cos(a)*spd, vy=math.sin(a)*spd,
                life=random.uniform(0.4, 1.0), max_life=1.0,
                color=color, size=random.uniform(3, 8)))

    def _spawn_miss_particles(self, t: SliceTarget):
        for _ in range(15):
            a = random.uniform(0, math.tau)
            spd = random.uniform(1, 5)
            self.particles.append(Particle(
                x=t.x, y=t.y, vx=math.cos(a)*spd, vy=math.sin(a)*spd,
                life=random.uniform(0.3, 0.7), max_life=0.7,
                color=RED_NEG, size=random.uniform(2, 5)))

    # ── Update ─────────────────────────────────────────────────────────────────
    def update(self, dt_s: float):
        if self.state != "PLAYING":
            return

        now = pytime_ms()
        elapsed = now - self.level_start_ms

        # Spawn beats 2s before their target time
        while self.next_beat_idx < len(self.beat_schedule):
            beat = self.beat_schedule[self.next_beat_idx]
            if beat["target_ms"] - elapsed <= 3300:
                self.spawn_target(beat)
                self.next_beat_idx += 1
            else:
                break

        # Waiting → Active transition
        for t in self.targets:
            if t.state == SliceState.WAITING:
                t.scale = min(1.0, t.scale + dt_s * 3)
                if t.time_to_target() < 800:
                    t.state = SliceState.ACTIVE

        # Auto-miss overdue targets
        for t in self.targets:
            if t.state == SliceState.ACTIVE and now - t.target_time > OK_WINDOW:
                t.state     = SliceState.MISS
                t.hit_label = "MISS"
                self.combo  = 0
                self.lives -= 1
                self._spawn_miss_particles(t)
                self.popups.append(ScorePopup("MISS", t.x, t.y - 40, RED_NEG))

        # Animate hit/miss
        for t in self.targets:
            if t.state == SliceState.HIT:
                t.slice_anim     = min(1.0, t.slice_anim + dt_s * 4)
                t.hit_label_alpha = max(0, t.hit_label_alpha - int(dt_s * 300))
            elif t.state == SliceState.MISS:
                t.hit_label_alpha = max(0, t.hit_label_alpha - int(dt_s * 250))

        self.targets = [t for t in self.targets
                        if not (t.state in (SliceState.HIT, SliceState.MISS)
                                and t.hit_label_alpha == 0)]

        # Particles
        for p in self.particles:
            p.x += p.vx; p.y += p.vy; p.vy += 0.15
            p.life = max(0.0, p.life - dt_s)
        self.particles = [p for p in self.particles if p.life > 0]

        # Popups
        for pop in self.popups:
            pop.age += dt_s; pop.y -= 60 * dt_s
        self.popups = [p for p in self.popups if p.age < p.life]

        # Scroll stars
        for i, (sx, sy, spd) in enumerate(self.stars):
            self.stars[i] = ((sx - spd * 0.3) % W, sy, spd)

        # Level complete / game over
        if self.next_beat_idx >= len(self.beat_schedule) and not self.targets:
            self.level_done = True
        if self.lives <= 0 or self.level_done:
            self.lives = max(0, self.lives)
            self.state = "GAMEOVER"

    # ── Draw ───────────────────────────────────────────────────────────────────
    def draw(self):
        self.screen.fill(BG)
        self._draw_stars()

        if self.state == "MENU":
            self._draw_menu()
        elif self.state in ("PLAYING", "PAUSED"):
            self._draw_game()
            if self.state == "PAUSED":
                self._draw_pause()
        elif self.state == "GAMEOVER":
            self._draw_game()
            self._draw_gameover()

        self.screen.blit(self.scanline_surf, (0, 0))
        pygame.display.flip()

    def _draw_stars(self):
        for sx, sy, spd in self.stars:
            b = int(100 + spd * 50)
            pygame.draw.circle(self.screen, (b,b,b), (int(sx), int(sy)), max(1, int(spd)))

    def _draw_menu(self):
        shadow = self.font_big.render("WAND SLICER", True, NEON_PINK)
        title  = self.font_big.render("WAND SLICER", True, NEON_CYAN)
        tx = W//2 - title.get_width()//2
        self.screen.blit(shadow, (tx+4, H//3+4))
        self.screen.blit(title,  (tx,   H//3))

        sub = self.font_med.render("Keyboard Edition", True, NEON_YELL)
        self.screen.blit(sub, (W//2 - sub.get_width()//2, H//3 + 90))

        diff_s = self.font_med.render(
            f"Difficulty: {'★'*self.difficulty + '☆'*(5-self.difficulty)}", True, WHITE)
        self.screen.blit(diff_s, (W//2 - diff_s.get_width()//2, H//2 + 20))

        kb = self.font_small.render("● Keyboard Active — Arrow Keys to Slice", True, NEON_YELL)
        self.screen.blit(kb, (W//2 - kb.get_width()//2, H//2 + 75))

        for i, line in enumerate([
            "ENTER / SPACE — Start",
            "← → on this screen — Change difficulty",
            "P — Pause   ESC — Quit",
        ]):
            s = self.font_small.render(line, True, GRAY)
            self.screen.blit(s, (W//2 - s.get_width()//2, H//2 + 130 + i*32))

        for i, d in enumerate(DIRECTIONS):
            col = ARROW_COLORS[d]
            draw_arrow(self.screen, d, 200 + i*250, H - 100, 30, col)
            lbl = self.font_small.render(d, True, col)
            self.screen.blit(lbl, (200 + i*250 - lbl.get_width()//2, H - 55))

    def _draw_game(self):
        self._draw_hud()
        now = pytime_ms()
        for t in self.targets:
            self._draw_target(t, now)
        for p in self.particles:
            alpha = int(255 * (p.life / p.max_life))
            s = pygame.Surface((int(p.size*2)+2, int(p.size*2)+2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*p.color, alpha), (int(p.size)+1, int(p.size)+1), int(p.size))
            self.screen.blit(s, (int(p.x-p.size), int(p.y-p.size)))
        for pop in self.popups:
            alpha = int(255 * (1 - (pop.age/pop.life)**2))
            s = self.font_med.render(pop.text, True, pop.color)
            surf = pygame.Surface(s.get_size(), pygame.SRCALPHA)
            surf.blit(s, (0,0)); surf.set_alpha(alpha)
            self.screen.blit(surf, (int(pop.x - s.get_width()//2), int(pop.y)))

    def _draw_target(self, t: SliceTarget, now: int):
        cx, cy = int(t.x), int(t.y)
        color  = ARROW_COLORS[t.direction]

        if t.state in (SliceState.WAITING, SliceState.ACTIVE):
            r = int(t.radius * t.scale)
            if t.state == SliceState.ACTIVE:
                ratio      = max(0.0, min(1.0, t.time_to_target() / 800))
                approach_r = int(r * (1 + ratio * 1.5))
                glow_circle(self.screen, color, cx, cy, approach_r, 2, 2)
                # Pulse
                _ = abs(math.sin(now * 0.006))
                glow_circle(self.screen, color, cx, cy, r + 8, 2, 1)
            glow_circle(self.screen, color, cx, cy, r, 3, 3)
            dark = tuple(max(0, c//6) for c in color)
            pygame.draw.circle(self.screen, dark, (cx, cy), max(1, r-3))
            if t.scale > 0.5:
                draw_arrow(self.screen, t.direction, cx, cy,
                           int(r * 0.7), color, int(255 * t.scale))

        elif t.state == SliceState.HIT:
            burst_r = int(t.radius * (1 + t.slice_anim * 2))
            alpha   = int(255 * (1 - t.slice_anim))
            s = pygame.Surface((burst_r*2+4, burst_r*2+4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*color, alpha//2), (burst_r+2, burst_r+2), burst_r)
            pygame.draw.circle(s, (*color, alpha),    (burst_r+2, burst_r+2), burst_r, 3)
            self.screen.blit(s, (cx-burst_r-2, cy-burst_r-2))

        elif t.state == SliceState.MISS:
            alpha = t.hit_label_alpha
            s = pygame.Surface((t.radius*2, t.radius*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*GRAY, alpha//3), (t.radius, t.radius), t.radius)
            pygame.draw.line(s, (*RED_NEG, alpha),
                             (t.radius-20, t.radius-20), (t.radius+20, t.radius+20), 4)
            pygame.draw.line(s, (*RED_NEG, alpha),
                             (t.radius+20, t.radius-20), (t.radius-20, t.radius+20), 4)
            self.screen.blit(s, (cx-t.radius, cy-t.radius))

    def _draw_hud(self):
        score_s = self.font_big.render(f"{self.score:06d}", True, WHITE)
        self.screen.blit(score_s, (W//2 - score_s.get_width()//2, 10))
        if self.combo > 1:
            col     = NEON_YELL if self.combo < 10 else NEON_PINK
            combo_s = self.font_med.render(f"COMBO x{self.combo}", True, col)
            self.screen.blit(combo_s, (W//2 - combo_s.get_width()//2, 80))
        for i in range(3):
            col = NEON_PINK if i < self.lives else DARK_GRAY
            pts = [(30+i*50, 20), (46+i*50, 36), (30+i*50, 44), (14+i*50, 36)]
            pygame.draw.polygon(self.screen, col, pts)
        if self.beat_schedule:
            prog  = min(1.0, self.elapsed_ms() / (self.beat_schedule[-1]["target_ms"] + 2000))
            bar_w = int((W-40) * prog)
            pygame.draw.rect(self.screen, DARK_GRAY, (20, H-18, W-40, 8), border_radius=4)
            if bar_w > 0:
                pygame.draw.rect(self.screen, NEON_CYAN, (20, H-18, bar_w, 8), border_radius=4)
        kb_s = self.font_small.render("● KB", True, NEON_YELL)
        self.screen.blit(kb_s, (W - kb_s.get_width() - 15, 10))
        diff_s = self.font_small.render(f"LVL {self.difficulty}", True, GRAY)
        self.screen.blit(diff_s, (W - diff_s.get_width() - 15, 35))

    def _draw_pause(self):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 140))
        self.screen.blit(ov, (0, 0))
        t = self.font_big.render("PAUSED", True, NEON_CYAN)
        self.screen.blit(t, (W//2 - t.get_width()//2, H//2 - 50))
        t2 = self.font_med.render("P to resume  |  ESC to quit", True, GRAY)
        self.screen.blit(t2, (W//2 - t2.get_width()//2, H//2 + 40))

    def _draw_gameover(self):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        self.screen.blit(ov, (0, 0))
        clear = self.level_done and self.lives > 0
        t = self.font_big.render("LEVEL CLEAR!" if clear else "GAME OVER",
                                 True, NEON_YELL if clear else NEON_PINK)
        self.screen.blit(t, (W//2 - t.get_width()//2, H//2 - 140))
        for i, (lbl, val) in enumerate([
            ("SCORE",     f"{self.score:06d}"),
            ("MAX COMBO", f"x{self.max_combo}"),
            ("LIVES LEFT", "♥"*self.lives + "♡"*(3-self.lives)),
        ]):
            l = self.font_med.render(lbl, True, GRAY)
            v = self.font_med.render(val, True, WHITE)
            self.screen.blit(l, (W//2-220, H//2-40+i*50))
            self.screen.blit(v, (W//2+80,  H//2-40+i*50))
        hint = self.font_med.render("ENTER — Play Again   ESC — Menu", True, NEON_CYAN)
        self.screen.blit(hint, (W//2 - hint.get_width()//2, H//2 + 180))

    # ── Main Loop ──────────────────────────────────────────────────────────────
    def run(self):
        last_t = time.time()
        while True:
            now_t  = time.time()
            dt_s   = min(now_t - last_t, 0.05)
            last_t = now_t

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.state == "PLAYING": self.state = "MENU"
                        elif self.state == "PAUSED": self.state = "MENU"
                        else: pygame.quit(); sys.exit()
                    elif event.key == pygame.K_p:
                        if self.state == "PLAYING": self.state = "PAUSED"
                        elif self.state == "PAUSED": self.state = "PLAYING"
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if self.state in ("MENU", "GAMEOVER"):
                            self.start_level()
                    elif self.state == "MENU":
                        if event.key == pygame.K_RIGHT:
                            self.difficulty = min(5, self.difficulty + 1)
                        elif event.key == pygame.K_LEFT:
                            self.difficulty = max(1, self.difficulty - 1)


            
            if self.state == "PLAYING" and self._serial:
                for direction in self._serial.get_pending_slices():
                    self.handle_slice(direction)

            self.update(dt_s)
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    game = WandSlicer()
    game.run()
