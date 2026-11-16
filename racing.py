#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRID MASTER - 터미널 레이싱 전략 시뮬레이션

10대의 머신이 달리는 레이스에서 한 명의 드라이버를 맡아
랩마다 주행 모드, 피트 스톱, 타이어 선택을 결정하는 CLI 게임.
표준 라이브러리만 사용합니다 (Python 3.8+).

    python3 racing.py                 # 메뉴로 시작
    python3 racing.py --auto          # 입력 없이 자동 진행 (데모/테스트)
    python3 racing.py --auto --season 3 --seed 42
"""

import argparse
import os
import random
import re
import sys
import time
import unicodedata

# ═════════════════════════ 터미널 유틸 ═════════════════════════


class Term:
    color = True
    auto = False
    delay = 0.35


ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def col(text, code):
    if not Term.color:
        return str(text)
    return f"\033[{code}m{text}\033[0m"


def bold(t):
    return col(t, "1")


def dim(t):
    return col(t, "2")


def red(t):
    return col(t, "31")


def green(t):
    return col(t, "32")


def yellow(t):
    return col(t, "33")


def cyan(t):
    return col(t, "36")


def vwidth(s):
    """터미널 표시 폭 (한글 = 2칸)."""
    s = ANSI_RE.sub("", str(s))
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def pad(s, width, align="<"):
    s = str(s)
    gap = max(0, width - vwidth(s))
    if align == ">":
        return " " * gap + s
    if align == "^":
        left = gap // 2
        return " " * left + s + " " * (gap - left)
    return s + " " * gap


def clear():
    if Term.color and not Term.auto:
        print("\033[2J\033[H", end="")


def pause(delay=None):
    if not Term.auto:
        time.sleep(Term.delay if delay is None else delay)


def ask(prompt, default=""):
    if Term.auto:
        print(f"{prompt}{default}")
        return default
    try:
        v = input(prompt).strip()
    except EOFError:
        print("\n입력이 종료되어 게임을 마칩니다.")
        sys.exit(0)
    return v if v else default


def choose(prompt, valid, default):
    """valid: 허용되는 입력 문자열 목록 (소문자 비교)."""
    valid = [v.lower() for v in valid]
    while True:
        v = ask(prompt, default).lower()
        if v in valid:
            return v
        print(red(f"  잘못된 입력입니다: {v!r}"))


def wait_enter(msg="  [Enter] 계속..."):
    ask(dim(msg), "")


def fmt_lap(t):
    if t is None:
        return "-"
    m = int(t // 60)
    return f"{m}:{t - m * 60:06.3f}"


def hline(n=96, ch="─"):
    return dim(ch * n)


# ═════════════════════════ 게임 데이터 ═════════════════════════

TEAMS = [
    # 이름, 머신 페이스(초, 낮을수록 빠름), 랩당 신뢰도, 색상
    ("Apex Racing", 0.00, 0.9988, "91"),
    ("Velocity GP", 0.20, 0.9982, "96"),
    ("Nordwind Motorsport", 0.40, 0.9991, "94"),
    ("Crimson Arrow", 0.60, 0.9975, "95"),
    ("Horizon Racing", 0.85, 0.9980, "93"),
]

DRIVERS = [
    # 이름, 팀, 실력(초, 음수=빠름), 일관성(편차), 공격성
    ("M. Vance", 0, -0.25, 0.18, 0.70),
    ("L. Moreau", 0, 0.05, 0.25, 0.50),
    ("K. Tanaka", 1, -0.20, 0.20, 0.60),
    ("R. Silva", 1, 0.00, 0.30, 0.80),
    ("E. Lindqvist", 2, -0.10, 0.17, 0.40),
    ("J. Becker", 2, 0.10, 0.22, 0.50),
    ("A. Rossi", 3, -0.15, 0.32, 0.90),
    ("D. Okafor", 3, 0.05, 0.24, 0.60),
    ("S. Park", 4, -0.05, 0.21, 0.60),
    ("T. Novak", 4, 0.20, 0.28, 0.40),
]

TRACKS = [
    dict(name="서울 스트리트 서킷", laps=20, base=92.0, wear=1.15, overtake=0.35,
         rain=0.25, df="high", pit_loss=21.0, desc="좁은 시가지, 추월 어려움, 코너 많음"),
    dict(name="알파인 링", laps=22, base=78.5, wear=0.90, overtake=0.60,
         rain=0.40, df="medium", pit_loss=19.0, desc="산악 고저차, 변덕스러운 날씨"),
    dict(name="데저트 스피드웨이", laps=25, base=88.0, wear=1.40, overtake=0.70,
         rain=0.03, df="low", pit_loss=20.0, desc="긴 직선, 뜨거운 노면, 타이어 혹사"),
    dict(name="하버 시티 GP", laps=18, base=104.0, wear=1.00, overtake=0.25,
         rain=0.20, df="high", pit_loss=22.0, desc="항구 시가지, 벽이 가까움"),
    dict(name="포레스트 파크", laps=22, base=95.0, wear=1.10, overtake=0.50,
         rain=0.45, df="medium", pit_loss=20.0, desc="숲 속 고속 코너, 비가 잦음"),
    dict(name="로마나 오토드로모", laps=24, base=81.0, wear=0.80, overtake=0.75,
         rain=0.15, df="low", pit_loss=23.0, desc="초고속 서킷, 슬립스트림 배틀"),
]

TIRES = {
    "S": ("소프트", "91"),
    "M": ("미디엄", "93"),
    "H": ("하드", "97"),
    "I": ("인터", "92"),
    "W": ("웨트", "94"),
}
DRY_TIRES = ("S", "M", "H")

WEATHER = {
    "dry": ("맑음", "93"),
    "light": ("약한 비", "96"),
    "heavy": ("폭우", "94"),
}
WEATHER_BASE = {"dry": 0.0, "light": 4.5, "heavy": 10.0}
# 날씨별 타이어 랩타임 보정 (초)
TIRE_PACE = {
    "dry": {"S": -0.8, "M": 0.0, "H": 0.6, "I": 3.0, "W": 6.5},
    "light": {"S": 5.0, "M": 5.4, "H": 6.0, "I": 0.0, "W": 1.5},
    "heavy": {"S": 13.0, "M": 13.5, "H": 14.0, "I": 3.0, "W": 0.0},
}
# 날씨별 랩당 마모율 (%)
TIRE_WEAR = {
    "dry": {"S": 4.2, "M": 2.7, "H": 1.8, "I": 6.0, "W": 9.0},
    "light": {"S": 2.0, "M": 1.6, "H": 1.2, "I": 2.2, "W": 3.0},
    "heavy": {"S": 1.8, "M": 1.5, "H": 1.1, "I": 2.6, "W": 1.8},
}
WEATHER_RISK = {"dry": 1.0, "light": 2.0, "heavy": 3.5}

MODES = {
    "push": dict(name="푸시", color="91", pace=-0.45, wear=1.35, fuel=1.07, risk=2.0),
    "normal": dict(name="노멀", color="97", pace=0.0, wear=1.00, fuel=1.00, risk=1.0),
    "conserve": dict(name="세이브", color="92", pace=0.40, wear=0.70, fuel=0.86, risk=0.6),
}

DOWNFORCE = ["low", "medium", "high"]
DF_NAME = {"low": "낮음", "medium": "중간", "high": "높음"}
DF_EFFECT = {  # 추월 보너스, 마모 배율, 실수 배율
    "low": (0.08, 1.05, 1.15),
    "medium": (0.0, 1.0, 1.0),
    "high": (-0.05, 0.95, 0.85),
}

FUEL_LOADS = {"1": ("가볍게", 0.99), "2": ("표준", 1.05), "3": ("넉넉하게", 1.11)}
FUEL_PACE = 0.06  # 연료 1단위당 랩타임 손해(초)

POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
DIFFICULTY = {"1": ("쉬움", -0.35), "2": ("보통", -0.10), "3": ("어려움", 0.10)}


def tire_tag(t):
    return col(t, TIRES[t][1])


def weather_tag(w):
    return col(f"[{WEATHER[w][0]}]", WEATHER[w][1])


# ═════════════════════════ 차량 / 드라이버 ═════════════════════════


class Car:
    def __init__(self, name, team, skill, consistency, aggression, is_player=False):
        self.name = name
        self.team = team  # (이름, 페이스, 신뢰도, 색)
        self.skill = skill
        self.consistency = consistency
        self.aggression = aggression
        self.is_player = is_player
        self.points = 0
        self.wins = 0

    @property
    def team_name(self):
        return self.team[0]

    def label(self, width=14):
        text = pad(self.name[:width], width)
        if self.is_player:
            return bold(col(text, "97;44"))
        return text

    def team_label(self, width=20):
        return col(pad(self.team_name[:width], width), self.team[3])

    def reset(self, track, laps):
        self.total = 0.0
        self.tire = "M"
        self.wear = 0.0
        self.tire_age = 0
        self.used_dry = set()
        self.used_wet = False
        self.fuel = laps * 1.05
        self.fuel_warned = False
        self.mode = "normal"
        self.df = track["df"]
        self.pits = 0
        self.dnf = None
        self.laps_done = 0
        self.last_lap = None
        self.best_lap = None
        self.pit_request = None
        self.penalty = 0.0
        self.flag = ""
        self.grid = 0

    def fit_tire(self, t):
        self.tire = t
        self.wear = 0.0
        self.tire_age = 0
        if t in DRY_TIRES:
            self.used_dry.add(t)
        else:
            self.used_wet = True


def build_field(player_name, team_idx, difficulty):
    """플레이어가 선택한 팀의 두 번째 드라이버 자리를 대신합니다."""
    seat = [i for i, d in enumerate(DRIVERS) if d[1] == team_idx][1]
    cars = []
    for i, (name, ti, skill, cons, aggr) in enumerate(DRIVERS):
        if i == seat:
            cars.append(Car(player_name, TEAMS[ti], DIFFICULTY[difficulty][1], 0.22, 0.6, True))
        else:
            cars.append(Car(name, TEAMS[ti], skill, cons, aggr))
    return cars


# ═════════════════════════ 레이스 엔진 ═════════════════════════


def gen_weather(track, laps, rng):
    """랩별 날씨 (index 0 = 출발 시점)."""
    w = "light" if rng.random() < track["rain"] * 0.45 else "dry"
    states = [w]
    for _ in range(laps + 3):
        r = rng.random()
        if w == "dry":
            if r < track["rain"] * 0.08:
                w = "light"
        elif w == "light":
            if r < 0.10 + track["rain"] * 0.1:
                w = "heavy"
            elif r < 0.26:
                w = "dry"
        else:
            if r < 0.20:
                w = "light"
        states.append(w)
    return states


class Race:
    def __init__(self, track, cars, laps, rng, player_auto=False):
        self.track = track
        self.cars = cars
        self.laps = laps
        self.rng = rng
        self.lap = 0
        self.weather = gen_weather(track, laps, rng)
        self.radar_ok = [rng.random() < 0.8 for _ in range(laps + 3)]
        self.sc_left = 0
        self.sc_next = False
        self.events = []
        self.player_auto = player_auto
        self.fastest = None  # (시간, 차, 랩)
        self.player = next((c for c in cars if c.is_player), None)
        self.order = []
        for c in cars:
            c.reset(track, laps)

    # ── 공용 ──
    def log(self, msg, code="0"):
        self.events.append((self.lap, col(msg, code)))

    def running(self):
        return sorted([c for c in self.cars if not c.dnf], key=lambda c: c.total)

    def now_weather(self):
        return self.weather[self.lap]

    def wet_race(self):
        return any(w != "dry" for w in self.weather[: self.laps + 1])

    def wear_rate(self, car, tire, w):
        mode = MODES[car.mode]["wear"]
        return TIRE_WEAR[w][tire] * self.track["wear"] * mode * DF_EFFECT[car.df][1]

    def forecast(self):
        """플레이어용 레이더 (정확도 약 80%)."""
        cur = self.weather[self.lap]
        if not self.radar_ok[self.lap]:
            return dim("레이더 신호 불안정...")
        for k in range(1, 4):
            if self.lap + k > self.laps:
                break
            nxt = self.weather[self.lap + k]
            if nxt != cur:
                return yellow(f"{k}랩 후 {WEATHER[nxt][0]} 예상")
        return green("향후 3랩 날씨 변화 없음")

    # ── 예선 ──
    def qualify(self):
        w = self.weather[0]
        results = []
        for c in self.cars:
            best_tire = min(TIRE_PACE[w], key=lambda t: TIRE_PACE[w][t])
            t = (self.track["base"] + c.team[1] + c.skill + self.setup_delta(c)
                 + WEATHER_BASE[w] + TIRE_PACE[w][best_tire]
                 + abs(self.rng.gauss(0, c.consistency * 1.3)) - 0.6)
            results.append((t, c))
        results.sort(key=lambda x: x[0])
        for i, (t, c) in enumerate(results):
            c.grid = i + 1
            c.total = i * 0.25  # 스타트 그리드 간격
        self.order = [c for _, c in results]
        return results

    def setup_delta(self, car):
        opt = DOWNFORCE.index(self.track["df"])
        return 0.25 * abs(DOWNFORCE.index(car.df) - opt)

    # ── AI 전략 ──
    def choose_dry(self, car, laps_left):
        must_change = (not self.wet_race_so_far() and not car.used_wet
                       and len(car.used_dry) == 1)
        options = []
        for t in DRY_TIRES:
            if must_change and t in car.used_dry:
                continue
            rate = TIRE_WEAR["dry"][t] * self.track["wear"]
            life = 78 / rate
            options.append((t, life))
        # 남은 랩을 버티는 가장 부드러운 타이어 (공격적이면 조금 더 무리)
        stretch = 1.0 + car.aggression * 0.15
        for t, life in options:
            if life * stretch >= laps_left:
                return t
        return options[-1][0]

    def wet_race_so_far(self):
        return any(w != "dry" for w in self.weather[: self.lap + 1])

    def ai_decide(self, car, gap_ahead):
        rng = self.rng
        # sim_lap()에서 self.lap은 이미 '이번에 달릴 랩'으로 증가된 상태
        laps_left = self.laps - self.lap + 1
        w = self.weather[self.lap - 1]  # 직전 랩까지 관측된 날씨
        threshold = 70 + car.aggression * 15
        want = None

        # 날씨가 몇 랩째 이어지는지 (잠깐 지나가는 소나기에 피트인하지 않도록)
        streak = 0
        for k in range(self.lap - 1, -1, -1):
            if self.weather[k] != w:
                break
            streak += 1
        pit_cost = self.track["pit_loss"] * (0.45 if self.sc_left > 0 else 1.0) + 3

        def worth(new):
            gain = TIRE_PACE[w][car.tire] - TIRE_PACE[w][new]
            return gain * min(laps_left, 8) > pit_cost

        wrong_tire = ((w == "dry" and car.tire in ("I", "W"))
                      or (w == "light" and car.tire in DRY_TIRES)
                      or (w == "heavy" and car.tire != "W"))
        if wrong_tire:
            new = self.choose_dry(car, laps_left) if w == "dry" else ("I" if w == "light" else "W")
            patience = 1 if w == "heavy" else 2
            if streak >= patience and worth(new) and rng.random() < 0.8:
                want = new
        elif car.wear > threshold and laps_left > 2:
            want = self.choose_dry(car, laps_left) if w == "dry" else car.tire
        elif (w == "dry" and not self.wet_race_so_far() and not car.used_wet
              and len(car.used_dry) == 1 and laps_left <= 4 + int(car.wear > 40) * 3):
            want = self.choose_dry(car, laps_left)
        elif self.sc_left > 0 and car.wear > 45 and laps_left > 4 and rng.random() < 0.6:
            want = self.choose_dry(car, laps_left) if w == "dry" else car.tire
        if want and laps_left >= 1:
            car.pit_request = want

        need = laps_left * 1.0
        if car.fuel < need + 0.3:
            car.mode = "conserve"
        elif laps_left <= 3 and car.fuel >= laps_left * 1.07 and car.wear < 90:
            car.mode = "push"
        elif (gap_ahead is not None and gap_ahead < 1.0 and car.wear < 65
              and car.fuel >= need * 1.04 and rng.random() < car.aggression):
            car.mode = "push"
        else:
            car.mode = "normal"

    # ── 랩 시뮬레이션 ──
    def base_lap(self, car, w, sc):
        tr = self.track
        if sc:
            return tr["base"] * 1.35 + WEATHER_BASE[w] + self.rng.uniform(0, 0.3)
        wear_pen = 0.012 * car.wear + max(0.0, car.wear - 70) ** 2 * 0.004
        t = (tr["base"] + car.team[1] + car.skill + self.setup_delta(car)
             + WEATHER_BASE[w] + TIRE_PACE[w][car.tire] + wear_pen
             + car.fuel * FUEL_PACE + MODES[car.mode]["pace"]
             + self.rng.gauss(0, car.consistency))
        if self.lap == 1:
            t += 2.0 + abs(self.rng.gauss(0, 0.6))
        return t

    def retire(self, car, reason, sc_chance):
        car.dnf = reason
        code = "1;31" if car.is_player else "31"
        self.log(f"{car.name} 리타이어 - {reason}", code)
        if self.sc_left == 0 and self.rng.random() < sc_chance:
            self.sc_next = True

    def sim_lap(self):
        rng = self.rng
        prev_order = self.running()
        self.lap += 1
        lap = self.lap
        w = self.weather[lap]
        if w != self.weather[lap - 1]:
            self.log(f"날씨 변화: {WEATHER[self.weather[lap - 1]][0]} → {WEATHER[w][0]}", "1;36")
        sc = self.sc_left > 0

        # 1) 전략 결정
        for i, car in enumerate(prev_order):
            gap = car.total - prev_order[i - 1].total if i > 0 else None
            if not car.is_player or self.player_auto:
                self.ai_decide(car, gap)

        # 2) 각 차량 랩타임
        proposed = {}
        for car in prev_order:
            car.flag = ""
            extra = 0.0
            clean = not sc

            if car.pit_request:
                loss = self.track["pit_loss"] * (0.45 if sc else 1.0)
                stop = rng.uniform(2.1, 3.0)
                if rng.random() < 0.06:
                    stop += rng.uniform(3, 8)
                    self.log(f"{car.name} 피트 작업 지연! ({stop:.1f}s)", "33")
                extra += loss + stop
                old = car.tire
                car.fit_tire(car.pit_request)
                car.pits += 1
                car.flag = "PIT"
                clean = False
                if car.is_player or prev_order.index(car) < 3:
                    self.log(f"{car.name} 피트인: {TIRES[old][0]} → {TIRES[car.tire][0]} "
                             f"({stop:.1f}s)", "1;97" if car.is_player else "97")
                car.pit_request = None

            t = self.base_lap(car, w, sc)

            # 실수 / 사고
            risk = (0.0045 * MODES[car.mode]["risk"] * DF_EFFECT[car.df][2]
                    * WEATHER_RISK[w] * (car.consistency / 0.22))
            if w != "dry" and car.tire in DRY_TIRES:
                risk *= 3.0
            if sc:
                risk *= 0.2
            if lap == 1:
                risk *= 2.0
            if rng.random() < risk:
                if rng.random() < 0.22:
                    self.retire(car, rng.choice(["벽에 충돌", "스핀 후 그래블 고립", "접촉 사고"]), 0.75)
                    continue
                lost = rng.uniform(2.0, 6.0)
                extra += lost
                clean = False
                car.flag = car.flag or "ERR"
                self.log(f"{car.name} 코스 이탈! (-{lost:.1f}s)", "1;33" if car.is_player else "33")

            # 기계 결함
            fail = (1 - car.team[2]) * (1.6 if car.mode == "push" else 1.0)
            if rng.random() < fail:
                self.retire(car, rng.choice(["엔진 고장", "기어박스 고장", "유압 문제", "브레이크 과열"]), 0.3)
                continue

            # 펑크
            if car.wear > 88 and rng.random() < (car.wear - 88) * 0.025:
                newt = car.tire if car.tire not in DRY_TIRES else self.choose_dry(car, self.laps - lap)
                extra += 18 + self.track["pit_loss"]
                car.fit_tire(newt)
                car.pits += 1
                car.flag = "PNC"
                clean = False
                self.log(f"{car.name} 타이어 펑크! 천천히 피트로 복귀", "1;31" if car.is_player else "31")

            # 연료 / 마모
            car.fuel -= MODES[car.mode]["fuel"] * (0.6 if sc else 1.0)
            if car.fuel < 0:
                car.fuel = 0
                self.retire(car, "연료 고갈", 0.2)
                continue
            if car.is_player and not car.fuel_warned and car.fuel < (self.laps - lap) * 0.99:
                car.fuel_warned = True
                self.log("무전: 연료가 부족합니다! 세이브 모드(3)로 아껴주세요", "1;31")
            rate = self.wear_rate(car, car.tire, w) * (0.4 if sc else 1.0) * rng.uniform(0.9, 1.1)
            car.wear = min(100.0, car.wear + rate)
            car.tire_age += 1

            if clean and (car.best_lap is None or t < car.best_lap):
                car.best_lap = t
            if clean and (self.fastest is None or t < self.fastest[0]):
                self.fastest = (t, car, lap)

            lap_total = t + extra
            car.last_lap = lap_total
            car.laps_done = lap
            proposed[car] = car.total + lap_total

        # 3) 순위 정리 / 추월
        self.resolve(prev_order, proposed, sc)

        # 4) 세이프티카 처리
        if sc:
            self.sc_left -= 1
            if self.sc_left == 0:
                self.log("세이프티카 철수 - 그린 플래그!", "1;32")
        elif rng.random() < 0.004:
            self.sc_next = True
            self.log("코스 위 파편 발견", "33")
        if self.sc_next and self.sc_left == 0 and lap < self.laps:
            self.sc_left = rng.randint(2, 4)
            self.log(f"세이프티카 출동! ({self.sc_left}랩)", "1;33")
        self.sc_next = False
        self.order = self.running()

    def pass_prob(self, car, ahead, delta):
        base = self.track["overtake"] + (0.15 if self.lap == 1 else 0.0)
        p = base * (0.5 + delta * 0.8) + car.aggression * 0.12
        p += DF_EFFECT[car.df][0] - DF_EFFECT[ahead.df][0] * 0.5
        p += 0.10 if car.mode == "push" else 0.0
        p -= 0.06 if ahead.mode == "push" else 0.0
        p += (ahead.wear - car.wear) * 0.004
        return max(0.03, min(0.92, p))

    def resolve(self, prev_order, proposed, sc):
        rng = self.rng
        result = []
        for car in prev_order:
            if car not in proposed:
                continue
            result.append(car)
            i = len(result) - 1
            while i > 0:
                ahead = result[i - 1]
                t, ta = proposed[car], proposed[ahead]
                if t > ta + 0.15:
                    break
                free = (ahead.flag in ("PIT", "PNC") and car.flag not in ("PIT", "PNC")) or t < ta - 1.2
                if not free:
                    if sc or rng.random() >= self.pass_prob(car, ahead, ta - t):
                        proposed[car] = ta + rng.uniform(0.2, 0.6)
                        if (car.is_player or ahead.is_player) and not sc:
                            if car.is_player:
                                self.log(f"{ahead.name} 추월 시도 실패 - 방어당함", "33")
                            else:
                                self.log(f"{car.name}의 추월 시도를 막아냄!", "32")
                        break
                if t >= ta:
                    t = ta - 0.05
                    proposed[car] = t
                proposed[ahead] = max(ta, t + rng.uniform(0.15, 0.4))
                result[i - 1], result[i] = car, ahead
                i -= 1
                if not free and (car.is_player or ahead.is_player or i < 3):
                    code = "1;32" if car.is_player else ("1;31" if ahead.is_player else "36")
                    self.log(f"{car.name} ▶ {ahead.name} 추월! (P{i + 1})", code)
        # 단조 증가 보정 + 세이프티카 간격 압축
        for i in range(1, len(result)):
            lo = proposed[result[i - 1]] + 0.05
            if proposed[result[i]] < lo:
                proposed[result[i]] = lo
            if sc and proposed[result[i]] - proposed[result[i - 1]] > 0.8:
                proposed[result[i]] = proposed[result[i - 1]] + 0.8
        for car in result:
            car.total = proposed[car]

    # ── 결과 ──
    def finish(self):
        wet = self.wet_race()
        for c in self.cars:
            if not c.dnf and not wet and not c.used_wet and len(c.used_dry) < 2:
                c.penalty = 20.0
                self.log(f"{c.name} +20초 페널티 (드라이 컴파운드 2종 미사용)", "31")
        finishers = sorted([c for c in self.cars if not c.dnf], key=lambda c: c.total + c.penalty)
        dnfs = sorted([c for c in self.cars if c.dnf], key=lambda c: -c.laps_done)
        classified = finishers + dnfs
        for pos, c in enumerate(classified):
            if not c.dnf and pos < len(POINTS):
                c.points += POINTS[pos]
                c.race_points = POINTS[pos]
            else:
                c.race_points = 0
            if pos == 0 and not c.dnf:
                c.wins += 1
        return classified

    # ── 화면 ──
    def render(self, show_controls=True):
        clear()
        tr = self.track
        w = self.weather[self.lap]
        sc_tag = col(" SAFETY CAR ", "1;30;43") if self.sc_left > 0 else ""
        lap_txt = "출발 대기" if self.lap == 0 else f"LAP {self.lap}/{self.laps}"
        if self.lap >= self.laps:
            lap_txt = col("체커기!", "1;97")
        print(f" {bold(col('GRID MASTER', '1;91'))}  │ {bold(tr['name'])} │ {bold(lap_txt)} │ "
              f"날씨 {weather_tag(w)} {sc_tag}")
        print(hline())
        print(dim(" " + pad("P", 4) + pad("드라이버", 15) + pad("팀", 21) + pad("리더차", 10, ">")
                  + pad("앞차", 9, ">") + "  " + pad("타이어", 9) + pad("마모", 17)
                  + pad("피트", 5) + "상태"))
        order = self.order or self.running()
        leader = order[0] if order else None
        for i, c in enumerate(order):
            if i == 0:
                gap, intv = "리더", ""
            else:
                gap = f"+{c.total - leader.total:.3f}"
                intv = f"+{c.total - order[i - 1].total:.3f}"
            marker = col("▶", "1;94") if c.is_player else " "
            moved = ""
            if c.grid and self.lap > 0:
                d = c.grid - (i + 1)
                moved = green(f"▲{d}") if d > 0 else (red(f"▼{-d}") if d < 0 else dim(" -"))
            flag = {"PIT": cyan("PIT"), "PNC": red("PNC"), "ERR": yellow("ERR")}.get(c.flag, "")
            mode = col(MODES[c.mode]["name"], MODES[c.mode]["color"]) if c.mode != "normal" else ""
            print(f"{marker}{pad(i + 1, 3)} {c.label()} {c.team_label()} {pad(gap, 10, '>')}"
                  f"{pad(intv, 9, '>')}  {tire_tag(c.tire)} {pad(str(c.tire_age) + '랩', 6)} "
                  f"{wear_bar(c.wear)}  {pad(c.pits, 4)} {pad(moved, 4)} {flag} {mode}")
        for c in self.cars:
            if c.dnf:
                print(dim(f"  -- {pad(c.name[:14], 14)} {pad(c.team_name[:20], 20)} "
                          f"DNF  L{c.laps_done} {c.dnf}"))
        print(hline())
        if self.player:
            self.render_player()
        print(hline())
        for lap, msg in self.events[-6:]:
            print(f"  {dim(pad('L' + str(lap), 4))} {msg}")
        if show_controls and self.player and not self.player.dnf:
            print(hline())
            print(f"  {bold('[Enter]')} 다음 랩   {bold('1')} 푸시  {bold('2')} 노멀  {bold('3')} 세이브"
                  f"   {bold('p')} 피트인   {bold('s')} 5랩 진행   {bold('f')} 끝까지 자동   "
                  f"{bold('q')} 기권")

    def render_player(self):
        p = self.player
        if p.dnf:
            print(red(f"  ▶ {p.name}: 리타이어 ({p.dnf})"))
            return
        order = self.order or self.running()
        pos = order.index(p)
        w = self.weather[self.lap]
        laps_left = self.laps - self.lap
        rate = self.wear_rate(p, p.tire, w)
        life = max(0, (85 - p.wear) / rate) if rate > 0 else 99
        need = laps_left * 1.0
        fuel_state = green("여유") if p.fuel >= need * 1.015 else (
            yellow("빠듯함") if p.fuel >= need else red("부족! 세이브 필요"))
        mode = MODES[p.mode]
        print(f"  {col('▶ 내 차', '1;94')}  {bold(p.name)} ({p.team_name})  "
              f"{bold(f'P{pos + 1}')}  출발 P{p.grid}   모드: {col(mode['name'], '1;' + mode['color'])}"
              f"   다운포스: {DF_NAME[p.df]}")
        print(f"    타이어 {tire_tag(p.tire)} {TIRES[p.tire][0]} ({p.tire_age}랩)  {wear_bar(p.wear)}"
              f"  예상 수명 ~{life:.0f}랩   |   연료 {p.fuel:5.1f} (남은 {laps_left}랩 ≈ {need:.1f}) {fuel_state}")
        ahead = f"{order[pos - 1].name} {p.total - order[pos - 1].total:+.3f}" if pos > 0 else "-"
        behind = (f"{order[pos + 1].name} {order[pos + 1].total - p.total:+.3f}"
                  if pos + 1 < len(order) else "-")
        print(f"    직전 랩 {fmt_lap(p.last_lap)}  베스트 {fmt_lap(p.best_lap)}   "
              f"앞차: {ahead}   뒷차: {behind}")
        rule = ""
        if not self.wet_race_so_far():
            ok = len(p.used_dry) >= 2 or p.used_wet
            rule = ("규정: 드라이 2종 사용 " + (green("✔") if ok else yellow("✘ (미사용 시 +20초)")))
        fl = ""
        if self.fastest:
            fl = f"패스티스트 랩: {self.fastest[1].name} {fmt_lap(self.fastest[0])}"
        print(f"    레이더: {self.forecast()}   {rule}   {dim(fl)}")


def wear_bar(w, n=10):
    filled = int(round(w / 100 * n))
    color = "32" if w < 50 else ("33" if w < 75 else "31")
    return col("#" * filled, color) + dim("." * (n - filled)) + f" {w:3.0f}%"


# ═════════════════════════ 플레이어 입력 ═════════════════════════


def pit_menu(race):
    p = race.player
    w = race.weather[race.lap]
    laps_left = race.laps - race.lap
    print()
    print(bold(f"  피트 스톱 - 교체할 타이어 (현재 날씨 {WEATHER[w][0]}, 남은 {laps_left}랩)"))
    for t in "SMHIW":
        rate = race.wear_rate(p, t, w)
        life = 85 / rate
        pace = TIRE_PACE[w][t]
        print(f"    {tire_tag(t)} {pad(TIRES[t][0], 7)} 랩타임 {pace:+5.1f}s   "
              f"마모 ~{rate:4.1f}%/랩   수명 ~{life:4.0f}랩")
    print(dim(f"    피트 손실 약 {race.track['pit_loss'] * (0.45 if race.sc_left else 1):.0f}s + 작업 2~3s"
              + ("  (세이프티카 중 - 저렴!)" if race.sc_left else "")))
    v = choose("  선택 (S/M/H/I/W, c=취소): ", list("smhiwc"), "c")
    if v == "c":
        return False
    p.pit_request = v.upper()
    return True


def player_turn(race):
    """플레이어 입력 처리. 반환: 진행할 랩 수 (0 = 기권)"""
    if race.player is None or race.player.dnf or race.player_auto:
        return 1
    p = race.player
    while True:
        v = ask("  > ", "").lower()
        if v == "":
            return 1
        if v in ("1", "2", "3"):
            p.mode = {"1": "push", "2": "normal", "3": "conserve"}[v]
            return 1
        if v == "p":
            if pit_menu(race):
                return 1
            race.render()
            continue
        if v == "s":
            return 5
        if v == "f":
            race.player_auto = True
            return race.laps
        if v == "q":
            if choose("  정말 기권하시겠습니까? (y/n): ", ["y", "n"], "n") == "y":
                p.dnf = "기권"
                race.log(f"{p.name} 기권", "31")
                return race.laps
            race.render()
            continue
        print(red("  알 수 없는 명령입니다."))


# ═════════════════════════ 게임 흐름 ═════════════════════════


TITLE = r"""
   ██████╗ ██████╗ ██╗██████╗     ███╗   ███╗ █████╗ ███████╗████████╗███████╗██████╗
  ██╔════╝ ██╔══██╗██║██╔══██╗    ████╗ ████║██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗
  ██║  ███╗██████╔╝██║██║  ██║    ██╔████╔██║███████║███████╗   ██║   █████╗  ██████╔╝
  ██║   ██║██╔══██╗██║██║  ██║    ██║╚██╔╝██║██╔══██║╚════██║   ██║   ██╔══╝  ██╔══██╗
  ╚██████╔╝██║  ██║██║██████╔╝    ██║ ╚═╝ ██║██║  ██║███████║   ██║   ███████╗██║  ██║
   ╚═════╝ ╚═╝  ╚═╝╚═╝╚═════╝     ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
"""

HELP = """
 ■ 목표
   10대가 참가하는 레이스에서 한 명의 드라이버가 되어 최대한 좋은 순위로 완주하세요.
   운전은 자동이고, 당신은 레이스 엔지니어처럼 '전략'을 결정합니다.

 ■ 랩마다 할 수 있는 것
   Enter  다음 랩 진행           1/2/3  주행 모드 변경 후 진행
   p      피트인 (타이어 교체)   s      5랩 연속 진행 (위험 상황 시 자동 정지)
   f      끝까지 자동 진행       q      기권

 ■ 주행 모드
   푸시    랩당 약 0.45초 빠름 / 타이어 마모 ×1.35 / 연료 ×1.07 / 실수 확률 ×2
   노멀    기준
   세이브  랩당 약 0.4초 느림 / 타이어 마모 ×0.7 / 연료 ×0.86 / 실수 확률 ×0.6

 ■ 타이어
   소프트(S) 빠르지만 빨리 닳음 · 미디엄(M) 균형 · 하드(H) 느리지만 오래감
   인터(I) 약한 비용 · 웨트(W) 폭우용.  비 오는데 슬릭을 신으면 매우 느리고 위험!
   마모 70%를 넘으면 랩타임이 급격히 나빠지고, 90% 근처에서는 펑크가 날 수 있습니다.

 ■ 규칙과 변수
   · 비가 한 번도 오지 않은 레이스는 드라이 타이어 2종을 반드시 써야 합니다 (위반 시 +20초).
   · 피트 스톱은 약 20초를 잃지만, 세이프티카 중에는 절반 이하로 줄어듭니다.
   · 추월은 서킷 특성, 페이스 차이, 타이어 상태, 다운포스, 모드에 따라 성공 확률이 달라집니다.
   · 연료가 바닥나면 리타이어! 무거운 연료는 느리지만 푸시할 여유를 줍니다.
   · 레이더 예보는 약 80% 정확합니다.
   · 다운포스가 서킷 특성(고속/테크니컬)과 맞지 않으면 랩당 손해를 봅니다.
"""


def pick_track(rng):
    print(bold("\n  서킷 선택"))
    for i, t in enumerate(TRACKS, 1):
        print(f"    {i}. {pad(t['name'], 20)} {t['laps']:2d}랩  {dim(t['desc'])}")
    print("    r. 랜덤")
    v = choose("  번호 (기본 1): ", [str(i) for i in range(1, len(TRACKS) + 1)] + ["r"], "1")
    return rng.choice(TRACKS) if v == "r" else TRACKS[int(v) - 1]


def pick_player():
    print(bold("\n  팀 선택"))
    for i, (name, pace, rel, color) in enumerate(TEAMS, 1):
        stars = "★" * (5 - i + 1) + "☆" * (i - 1)
        print(f"    {i}. {col(pad(name, 22), color)} 머신 성능 {yellow(stars)}  "
              f"{dim('신뢰도 ' + ('높음' if rel > 0.9985 else '보통' if rel > 0.9979 else '낮음'))}")
    team = int(choose("  번호 (기본 3): ", [str(i) for i in range(1, len(TEAMS) + 1)], "3")) - 1
    name = ask("  드라이버 이름 (기본 'YOU'): ", "YOU")[:14]
    print(bold("\n  난이도 (드라이버 실력)"))
    for k, (n, _) in DIFFICULTY.items():
        print(f"    {k}. {n}")
    diff = choose("  번호 (기본 2): ", list(DIFFICULTY), "2")
    return name, team, diff


def race_setup(race):
    tr = race.track
    p = race.player
    w0 = race.weather[0]
    clear()
    print(bold(f"\n  ■ {tr['name']}  -  레이스 셋업"))
    print(hline(70))
    over = "쉬움" if tr["overtake"] > 0.6 else ("보통" if tr["overtake"] > 0.4 else "어려움")
    wear = "높음" if tr["wear"] > 1.1 else ("보통" if tr["wear"] >= 0.95 else "낮음")
    print(f"    랩 수 {race.laps}   기준 랩타임 {fmt_lap(tr['base'])}   피트 손실 ~{tr['pit_loss']:.0f}초")
    print(f"    추월 난이도 {over}   타이어 마모 {wear}   강우 확률 {int(tr['rain'] * 100)}%")
    print(f"    특징: {tr['desc']}")
    print(f"    현재 날씨: {weather_tag(w0)}")
    print(hline(70))

    print(bold("\n  1) 다운포스"))
    print(dim("     낮음: 직선 빠름·추월 유리 / 높음: 코너 안정·타이어 보호. 서킷에 맞춰야 빠릅니다."))
    v = choose("     1 낮음  2 중간  3 높음 (기본 2): ", ["1", "2", "3"], "2")
    p.df = DOWNFORCE[int(v) - 1]

    print(bold("\n  2) 연료 탑재량"))
    for k, (n, m) in FUEL_LOADS.items():
        print(f"     {k}. {n} ({race.laps * m:.1f})")
    v = choose("     번호 (기본 2): ", list(FUEL_LOADS), "2")
    p.fuel = race.laps * FUEL_LOADS[v][1]

    print(bold("\n  3) 스타트 타이어"))
    for t in "SMHIW":
        print(f"     {tire_tag(t)} {pad(TIRES[t][0], 7)} 랩타임 {TIRE_PACE[w0][t]:+5.1f}s  "
              f"마모 ~{race.wear_rate(p, t, w0):4.1f}%/랩")
    default = "m" if w0 == "dry" else ("i" if w0 == "light" else "w")
    v = choose(f"     선택 (기본 {default.upper()}): ", list("smhiw"), default)
    p.fit_tire(v.upper())


def ai_setup(race):
    rng = race.rng
    w0 = race.weather[0]
    for c in race.cars:
        if c.is_player and not race.player_auto:
            continue
        c.df = race.track["df"] if rng.random() < 0.8 else rng.choice(DOWNFORCE)
        c.fuel = race.laps * 1.05
        if w0 == "light":
            c.fit_tire("I")
        elif w0 == "heavy":
            c.fit_tire("W")
        else:
            c.fit_tire(rng.choices(DRY_TIRES, weights=[4, 5, 1.5])[0])


def show_qualifying(race, results):
    clear()
    print(bold(f"\n  ■ 예선 결과 - {race.track['name']}  {weather_tag(race.weather[0])}"))
    print(hline(70))
    pole = results[0][0]
    for i, (t, c) in enumerate(results, 1):
        gap = "POLE" if i == 1 else f"+{t - pole:.3f}"
        mark = col("▶", "1;94") if c.is_player else " "
        print(f" {mark}{pad(i, 3)} {c.label()} {c.team_label()} {fmt_lap(t)}  {pad(gap, 8, '>')}")
    print(hline(70))
    wait_enter("  [Enter] 레이스 시작!")


def run_race(track, cars, rng, laps=None, player_auto=False):
    laps = laps or track["laps"]
    race = Race(track, cars, laps, rng, player_auto=player_auto)
    if race.player and not player_auto:
        race_setup(race)
    ai_setup(race)
    results = race.qualify()
    show_qualifying(race, results)

    # 스타트
    race.render(show_controls=False)
    if not Term.auto:
        for light in range(1, 6):
            print("\r  " + col("● " * light, "1;31") + dim("○ " * (5 - light)), end="", flush=True)
            time.sleep(0.45)
        time.sleep(rng.uniform(0.3, 1.2))
        print("\r  " + col("LIGHTS OUT AND AWAY WE GO!", "1;32") + " " * 10)
        time.sleep(0.6)
    race.log("레이스 스타트!", "1;32")

    steps = 0
    while race.lap < race.laps:
        if steps <= 0:
            race.render()
            steps = player_turn(race)
            multi = steps > 1
        p = race.player
        before = (race.weather[race.lap], race.sc_left, p.dnf if p else None)
        race.sim_lap()
        steps -= 1
        if steps > 0 and race.lap < race.laps:
            race.render(show_controls=False)
            pause(0.15 if race.player_auto or (p and p.dnf) else Term.delay)
            # 연속 진행 중 중요한 상황이면 정지
            if multi and p and not p.dnf and not race.player_auto:
                after = (race.weather[race.lap], race.sc_left, p.dnf)
                if (after[0] != before[0] or (after[1] and not before[1])
                        or p.wear > 75 or p.fuel < (race.laps - race.lap) * 0.98):
                    steps = 0
    classified = race.finish()
    race.render(show_controls=False)
    print()
    wait_enter("  [Enter] 결과 보기")
    show_results(race, classified)
    return race, classified


def show_results(race, classified):
    clear()
    print(bold(f"\n  🏁 최종 결과 - {race.track['name']} ({race.laps}랩)"))
    print(hline(92))
    print(dim("  " + pad("P", 4) + pad("드라이버", 15) + pad("팀", 21) + pad("기록", 13, ">")
              + pad("출발", 6, ">") + pad("피트", 6, ">") + "  " + pad("베스트랩", 10) + "포인트"))
    winner = classified[0]
    win_time = winner.total + winner.penalty
    fl_car = race.fastest[1] if race.fastest else None
    for i, c in enumerate(classified, 1):
        if c.dnf:
            rec = red("DNF")
        elif i == 1:
            rec = fmt_lap(win_time)
        else:
            rec = f"+{c.total + c.penalty - win_time:.3f}"
        if c.penalty:
            rec += yellow("*")
        mark = col("▶", "1;94") if c.is_player else " "
        best = fmt_lap(c.best_lap)
        if c is fl_car:
            best = col(best, "1;95")
        pts = f"+{c.race_points}" if c.race_points else ""
        medal = {1: col("🥇", "33"), 2: "🥈", 3: "🥉"}.get(i, "  ") if not c.dnf else "  "
        print(f" {mark}{pad(i, 3)} {c.label()} {c.team_label()} {pad(rec, 13, '>')}"
              f"{pad('P' + str(c.grid), 6, '>')}{pad(c.pits, 6, '>')}  {pad(best, 10)} "
              f"{pad(green(pts), 5)} {medal}")
    print(hline(92))
    if race.fastest:
        t, c, lap = race.fastest
        print(f"  패스티스트 랩: {col(c.name, '1;95')} {fmt_lap(t)} (L{lap})")
    if any(c.penalty for c in classified):
        print(yellow("  * 드라이 컴파운드 2종 미사용 +20초 페널티 포함"))
    p = race.player
    if p:
        pos = classified.index(p) + 1
        if p.dnf:
            msg = red(f"  아쉽게도 리타이어했습니다 ({p.dnf}).")
        elif pos == 1:
            msg = col("  🏆 우승! 완벽한 레이스였습니다!", "1;93")
        elif pos <= 3:
            msg = green(f"  포디움 달성! P{pos} (출발 P{p.grid})")
        elif pos <= 10:
            msg = f"  P{pos}로 완주 (출발 P{p.grid}), {p.race_points}포인트 획득"
        else:
            msg = f"  P{pos}로 완주"
        print(msg)
    print()


def show_standings(cars, title="챔피언십 순위"):
    print(bold(f"  ■ {title}"))
    print(hline(60))
    for i, c in enumerate(sorted(cars, key=lambda c: (-c.points, -c.wins)), 1):
        mark = col("▶", "1;94") if c.is_player else " "
        print(f" {mark}{pad(i, 3)} {c.label()} {c.team_label()} {pad(c.points, 5, '>')}점  "
              f"{dim(str(c.wins) + '승') if c.wins else ''}")
    print(hline(60))
    teams = {}
    for c in cars:
        teams[c.team] = teams.get(c.team, 0) + c.points
    print(bold("  ■ 컨스트럭터 순위"))
    for i, (t, pts) in enumerate(sorted(teams.items(), key=lambda x: -x[1]), 1):
        print(f"   {pad(i, 3)} {col(pad(t[0], 22), t[3])} {pad(pts, 5, '>')}점")
    print(hline(60))


def quick_race(rng, auto=False, laps=None):
    if auto:
        track = rng.choice(TRACKS)
        name, team, diff = "YOU", 2, "2"
    else:
        clear()
        print(bold("\n  ■ 퀵 레이스"))
        track = pick_track(rng)
        if laps is None:
            v = ask(f"  랩 수 (기본 {track['laps']}, 5~60): ", str(track["laps"]))
            laps = max(5, min(60, int(v))) if v.isdigit() else track["laps"]
        name, team, diff = pick_player()
    cars = build_field(name, team, diff)
    run_race(track, cars, rng, laps=laps, player_auto=auto)
    wait_enter("  [Enter] 메인 메뉴로")


def championship(rng, auto=False, n=None, laps=None):
    if auto:
        name, team, diff = "YOU", 2, "2"
        n = n or 3
    else:
        clear()
        print(bold("\n  ■ 챔피언십"))
        if n is None:
            n = int(choose(f"  레이스 수 (3~{len(TRACKS)}, 기본 {len(TRACKS)}): ",
                           [str(i) for i in range(3, len(TRACKS) + 1)], str(len(TRACKS))))
        name, team, diff = pick_player()
    tracks = TRACKS[:n] if not auto else rng.sample(TRACKS, n)
    cars = build_field(name, team, diff)
    for rnd, track in enumerate(tracks, 1):
        clear()
        print(bold(f"\n  ■ ROUND {rnd}/{len(tracks)} - {track['name']}"))
        show_standings(cars)
        wait_enter("  [Enter] 레이스 위켄드 시작")
        run_race(track, cars, rng, laps=laps, player_auto=auto)
        wait_enter("  [Enter] 챔피언십 순위 보기")
        clear()
        print()
        show_standings(cars, f"챔피언십 순위 (ROUND {rnd}/{len(tracks)} 종료)")
        if rnd < len(tracks):
            wait_enter()
    champ = max(cars, key=lambda c: (c.points, c.wins))
    print()
    if champ.is_player:
        print(col(f"  🏆🏆🏆  {champ.name}, 월드 챔피언 등극!  🏆🏆🏆", "1;93"))
    else:
        player = next(c for c in cars if c.is_player)
        rank = sorted(cars, key=lambda c: (-c.points, -c.wins)).index(player) + 1
        print(f"  챔피언: {bold(champ.name)} ({champ.team_name}) - {champ.points}점")
        print(f"  당신의 시즌 최종 순위: P{rank} ({player.points}점)")
    print()
    wait_enter("  [Enter] 메인 메뉴로")


def main():
    ap = argparse.ArgumentParser(description="GRID MASTER - 터미널 레이싱 전략 시뮬레이션")
    ap.add_argument("--seed", type=int, help="난수 시드 (재현용)")
    ap.add_argument("--auto", action="store_true", help="입력 없이 AI가 대신 진행 (데모)")
    ap.add_argument("--season", type=int, default=0, help="--auto와 함께: 챔피언십 레이스 수")
    ap.add_argument("--laps", type=int, help="랩 수 강제 지정")
    ap.add_argument("--no-color", action="store_true", help="색상 끄기")
    ap.add_argument("--speed", type=float, default=0.35, help="연속 진행 시 랩 간 딜레이(초)")
    args = ap.parse_args()

    if os.name == "nt":
        os.system("")  # Windows 콘솔 ANSI 활성화
    Term.color = not args.no_color and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
    Term.auto = args.auto
    Term.delay = max(0.0, args.speed)
    rng = random.Random(args.seed)

    if args.auto:
        if args.season > 0:
            championship(rng, auto=True, n=min(args.season, len(TRACKS)), laps=args.laps)
        else:
            quick_race(rng, auto=True, laps=args.laps)
        return

    while True:
        clear()
        print(col(TITLE, "1;91"))
        print(bold("              터미널 레이싱 전략 시뮬레이션") + dim("  —  당신은 피트월의 두뇌입니다\n"))
        print("    1. 퀵 레이스")
        print("    2. 챔피언십")
        print("    3. 게임 방법")
        print("    4. 종료\n")
        v = choose("  선택: ", ["1", "2", "3", "4"], "1")
        if v == "1":
            quick_race(rng, laps=args.laps)
        elif v == "2":
            championship(rng, laps=args.laps)
        elif v == "3":
            clear()
            print(HELP)
            wait_enter()
        else:
            print("  다음 레이스에서 만나요! 🏁")
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  게임을 종료합니다.")
