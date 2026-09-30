# -*- coding: utf-8 -*-
"""
保荣摄影灯外壳 —— 钣金展开图 生成脚本 v2 (严格复刻手绘参考图布局)
输出:  DXF (加工用, 分层) + PNG 预览 (单视图, 与参考图同构)

参考:  C:\\Users\\z3660\\Desktop\\保荣\\新建文件夹\\新建文件夹\\灯壳_洞洞板展开_600x300_预览.png
实测几何 (px -> mm, 原点=板左上, 2.0933px/mm):
  板 600x300, 折线 x=150/300/450 (蓝虚线, 0~263mm)
  法兰线 y=269 (蓝虚线全宽 + 红实线段: 0-25 / 136-164 / 283-317 / 428-468 / 579-600)
  红色竖切口: 折线顶端 0-18mm (折痕定位), 折线底端 246~300mm (穿透法兰到底, 折叠用)
  孔 8xØ7 @ y=285: x=15/135/165/285/315/435/465/585
  文字: 散热孔待定(中) / 红字1(上) / 红字2(法兰带)

用法:  python gen_cad.py        # 生成全部
改参数见 CONFIG 区。COOL_HOLE 定稿后打开即出孔阵。
"""
import os
import math

import ezdxf
from ezdxf.enums import TextEntityAlignment
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
import matplotlib.font_manager as fm

# ─────────────────────────── CONFIG ───────────────────────────
OUT_DIR = r"C:\Users\z3660\Desktop\保荣\CAD输出"

W_ALL, H_ALL = 600.0, 300.0     # 展开板
FACE_W = 150.0
FLANGE_Y = 269.0                # 法兰折线 y (距顶)
FLANGE_W = 300.0 - FLANGE_Y     # 法兰带宽 = 31mm
HOLE_D = 7.0
HOLE_Y = 285.0                  # 法兰孔中心 y
HOLE_EDGE = 15.0
NOTCH_TOP = 18.0                # 折线顶端红色切口长 (实测)
NOTCH_BOT = [246.0, 247.0, 249.0]   # 折线底端切口起点 y (到板底)
# 法兰线红色实线段 (全切开) mm x —— 统一 3cm 对称: 折线±15, 两端30mm
FLANGE_CUTS = [(0, 30), (135, 165), (285, 315), (435, 465), (570, 600)]

PLATE = 150.0                   # 端板
BIG_D = 100.0
CORNER_D = 7.0
CORNER_IN = 15.0
CLIP = 8.0
CLIP_ANGLES = [90.0, 210.0, 330.0]

COOL_HOLE = None                # 旧散热孔阵开关 (弃用) — 用 VENT 新参数
# ── 散热孔 (灯壳展开图 4 块面) ──
# 每块面: 150 宽, 靠法兰侧 150x150 区域开孔; 边缘留 2cm → 实际 130x130
# 孔型: 圆头长条孔(斜圆长孔), 宽5 间隔5; 竖孔 宽5 间隔6
VENT = {
    "edge_margin": 20.0,       # 开孔区距面边缘留白 (2cm) → 孔区 150-2*20 = 110... 
    # 注: "预留边缘2cm空白, 130*130范围开孔": 150 区域减 20 → 130. 即开孔区 130x130
    "slot_len": 30.0,          # 单条长孔长度 (圆头), 用户未给, 默认30 (可改)
    "slot_w": 5.0,             # 长孔宽度
    "gap": 7.0,                # 横/斜孔间隔
    "gap_v": 7.0,              # 竖孔间隔
    "patterns": ["S", "H", "S", "V"],   # F1斜 F2横 F3斜 F4竖
}
TOP_DIM = "600 = 4 × 150"

TITLE_INFO = ["保荣摄影灯外壳", "材料: 2mm 不锈钢板(304)",
              "洞洞板展开图 1:1", "折弯内r≥1.5t"]

C_INK = "#2A2A35"      # 鸦青 实体轮廓
C_BEND = "#3B5998"     # 石青 折弯线
C_RED = "#C0392B"      # 朱砂 切割线/法兰
C_HOLE = "#1F7A5A"     # 松绿 孔
C_DIM = "#8C8C92"
C_TXT = "#4A4A55"
C_BG = "#FFFFFF"

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

# ─────────────────────────── 几何 ───────────────────────────
def bend_lines():
    return [FACE_W * i for i in range(1, 4)]

def flange_holes():
    xs = []
    for x in [0.0] + bend_lines() + [W_ALL]:
        xs += [x - HOLE_EDGE, x + HOLE_EDGE]
    xs = [x for x in xs if 0 <= x <= W_ALL]
    return sorted(xs)

def cool_holes():
    if not COOL_HOLE:
        return [], 0
    d, pitch = COOL_HOLE
    out = []
    dy = pitch * math.sin(math.radians(60))
    row = 0
    y = 40.0
    while y < H_ALL - 20:
        x0 = 20.0 + pitch * 0.5 if row % 2 else 20.0 + pitch
        x = x0
        while x < W_ALL - 20:
            out.append((x, y))
            x += pitch
        y += dy
        row += 1
    return out, d


def vent_slots():
    """4 块面散热孔 — 圆头长条孔
    每块面 150 宽(x) x 270 长(y), 靠法兰侧 150x150 开孔区, 边缘留 2cm → 130x130
      x: 面起点+10 .. 面起点+140 ;  y: 130 .. 260
    孔型(width=5):
      H: 横向孔 — 交错阵列 (防强度削弱)
      V: 竖向孔 — 交错阵列
      S: 45° 斜孔 (F1 正斜 / F3 反斜) — 全覆盖对角, 法向间隔
    间隔统一 7mm (用户要求)
    返回 [(x0,y0,x1,y1,w)]
    """
    V = VENT
    L = V.get("slot_len", 30.0); w = V["slot_w"]
    gap_now = V.get("gap", 7.0)          # 斜/横孔净距 (用户要求 7)
    gap_v = V.get("gap_v", 7.0)          # 竖孔净距
    slots = []
    # 开孔区: 每面 150 宽, 靠法兰侧 150x150 (y 120..270), 四周留 2cm → 110x110
    ZY0, ZY1 = 140.0, 250.0              # y: 120+20 .. 270-20
    for fi, pat in enumerate(V["patterns"]):
        fx = fi * FACE_W
        ZX0, ZX1 = fx + 20.0, fx + 130.0  # x: 面起点+20 .. 面起点+130 (110 宽, 距折线 20)
        if pat == "H":
            # 横向短孔交错阵列: 行净距 10(防连孔), 列距 L+10, 隔行错半
            row_gap = w + 10.0
            col_gap = L + 10.0
            y = ZY0 + w / 2
            ri = 0
            while y + w / 2 <= ZY1 + 0.01:
                off = col_gap / 2 if ri % 2 else 0.0
                x = ZX0 + off + L / 2
                while x + L / 2 <= ZX1 + 0.01:
                    slots.append((x - L / 2, y, x + L / 2, y, w))
                    x += col_gap
                y += row_gap
                ri += 1
        elif pat == "V":
            # 竖向短孔交错阵列: 列净距 10, 行距 L+10, 隔列错半
            col_gap = w + 10.0
            row_gap = L + 10.0
            x = ZX0 + w / 2
            ci = 0
            while x + w / 2 <= ZX1 + 0.01:
                off = row_gap / 2 if ci % 2 else 0.0
                y = ZY0 + off + L / 2
                while y + L / 2 <= ZY1 + 0.01:
                    slots.append((x, y - L / 2, x, y + L / 2, w))
                    y += row_gap
                x += col_gap
                ci += 1
        elif pat == "S":
            d = math.sqrt(2) / 2
            step = gap_now + w            # 斜孔法向间隔 7+5=12
            sx = 1 if fi == 0 else -1     # F1 正斜, F3 反斜
            u = (sx * d, d)
            v = (-u[1], u[0])
            cx = (ZX0 + ZX1) / 2; cy = (ZY0 + ZY1) / 2
            for ks in range(-60, 61, 1):
                px = cx + ks * step * v[0]
                py = cy + ks * step * v[1]
                tlist = []
                if abs(u[0]) > 1e-9:
                    tlist.append((ZX0 - px) / u[0]); tlist.append((ZX1 - px) / u[0])
                if abs(u[1]) > 1e-9:
                    tlist.append((ZY0 - py) / u[1]); tlist.append((ZY1 - py) / u[1])
                ts = [t for t in tlist
                      if ZX0 - 1e-6 <= px + t * u[0] <= ZX1 + 1e-6
                      and ZY0 - 1e-6 <= py + t * u[1] <= ZY1 + 1e-6]
                if len(ts) >= 2:
                    t0, t1 = min(ts), max(ts)
                    if t1 - t0 > w + 0.5:
                        slots.append((px + t0 * u[0], py + t0 * u[1],
                                      px + t1 * u[0], py + t1 * u[1], w))
    # ── 顶部一圈短长孔 (另一端): 4 面各 3 个, 孔带距板顶边 2cm, 孔宽5 长30, 净距10 ──
    TOP_EDGE = 20.0          # 孔边缘距板顶 (2cm)
    t_cy = TOP_EDGE + w / 2  # 孔中心 y = 22.5 (孔 y 20..25)
    t_N = 3
    for fi in range(4):
        fx = fi * FACE_W
        for i in range(t_N):
            xc = fx + 35 + i * 40.0     # 中心 35/75/115 (开孔区20-130内, 中心距40=30长+10净距)
            slots.append((xc - L / 2, t_cy, xc + L / 2, t_cy, w))
    return slots

os.makedirs(OUT_DIR, exist_ok=True)

# ═════════════════════════ DXF ═════════════════════════
def setup_doc():
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    doc.header["$LUNITS"] = 2
    layers = [
        ("CUT", 2, "CONTINUOUS", "实体轮廓-切割线"),
        ("BEND", 5, "DASHDOT", "折弯线"),
        ("FLANGE", 1, "CONTINUOUS", "法兰切割线-全切开"),
        ("HOLE", 3, "CONTINUOUS", "螺钉孔"),
        ("CENTER", 8, "CENTER", "中心线"),
        ("DIM", 8, "CONTINUOUS", "尺寸标注"),
        ("TEXT", 7, "CONTINUOUS", "文字说明"),
        ("HATCH", 9, "CONTINUOUS", "预留孔阵"),
    ]
    for name, color, lt, desc in layers:
        if name not in doc.layers:
            doc.layers.add(name, color=color, linetype=lt)
    return doc, doc.modelspace()

def d_line(msp, p1, p2, layer="CUT", lw=25):
    msp.add_line(p1, p2, dxfattribs={"layer": layer, "lineweight": lw})

def d_rect(msp, x, y, w, h, layer="CUT", lw=35):
    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)],
                       close=True, dxfattribs={"layer": layer, "lineweight": lw})

def d_circle(msp, c, r, layer="HOLE", lw=15):
    msp.add_circle(c, r, dxfattribs={"layer": layer, "lineweight": lw})

def d_text(msp, txt, x, y, h=6, layer="TEXT", rot=0, center=False):
    t = msp.add_text(txt, dxfattribs={"layer": layer, "height": h,
                                      "rotation": math.degrees(rot)})
    if center:
        t.set_placement((x, y), align=TextEntityAlignment.MIDDLE_CENTER)
    else:
        t.set_placement((x, y), align=TextEntityAlignment.LEFT)
    return t

def d_dim_h(msp, x1, x2, y, txt, off=0, h=5):
    yo = y + off
    d_line(msp, (x1, y), (x1, yo - 1), "DIM", 13)
    d_line(msp, (x2, y), (x2, yo - 1), "DIM", 13)
    d_line(msp, (x1, yo), (x2, yo), "DIM", 13)
    a = 2.5
    msp.add_solid([(x1, yo), (x1 + a, yo + a * 0.35), (x1 + a, yo - a * 0.35)])
    msp.add_solid([(x2, yo), (x2 - a, yo + a * 0.35), (x2 - a, yo - a * 0.35)])
    msp.add_text(txt, dxfattribs={"layer": "DIM", "height": h}).set_placement(
        ((x1 + x2) / 2, yo + 1.5), align=TextEntityAlignment.MIDDLE_CENTER)

def d_dim_v(msp, x, y1, y2, txt, off=0, h=5):
    xo = x + off
    d_line(msp, (x, y1), (xo - 1, y1), "DIM", 13)
    d_line(msp, (x, y2), (xo - 1, y2), "DIM", 13)
    d_line(msp, (xo, y1), (xo, y2), "DIM", 13)
    a = 2.5
    msp.add_solid([(xo, y1), (xo + a * 0.35, y1 + a), (xo - a * 0.35, y1 + a)])
    msp.add_solid([(xo, y2), (xo + a * 0.35, y2 - a), (xo - a * 0.35, y2 - a)])
    msp.add_text(txt, dxfattribs={"layer": "DIM", "height": h,
                                  "rotation": 90}).set_placement(
        (xo - 1.5, (y1 + y2) / 2), align=TextEntityAlignment.MIDDLE_CENTER)


def add_slot_lwpolyline(msp, p0, p1, w, layer="HATCH"):
    """圆头长条孔 (长圆形孔) 作为闭合 LWPOLYLINE
    p0,p1 = 中心线端点, w = 槽宽。轮廓 = 两端半径为 w/2 的半圆 + 两条直边。
    ezdxf 格式: point + bulge (tupled 形式), bulge=1 表示 180° 弧
    """
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L           # 轴向单位向量
    nx, ny = -uy, ux                  # 法向
    r = w / 2
    a = (x0 + nx * r, y0 + ny * r)    # 左端上
    b = (x1 + nx * r, y1 + ny * r)    # 右端上
    c = (x1 - nx * r, y1 - ny * r)    # 右端下
    d_ = (x0 - nx * r, y0 - ny * r)   # 左端下
    # ezdxf LWPOLYLINE 用 xyseb 格式: (x, y, start_w, end_w, bulge); bulge=1 = 180° 弧
    pts = [
        (a[0], a[1], 0, 0, 0),
        (b[0], b[1], 0, 0, 1.0),
        (c[0], c[1], 0, 0, 1.0),
        (d_[0], d_[1], 0, 0, 0),
        (a[0], a[1], 0, 0, 1.0),
    ]
    msp.add_lwpolyline(pts, format="xyseb", close=True,
                       dxfattribs={"layer": layer, "lineweight": 15})


def build_blank_dxf(path):
    """展开板 DXF: 严格按参考图特征"""
    doc, msp = setup_doc()
    d_rect(msp, 0, 0, W_ALL, H_ALL)
    # 折弯线 (蓝) + 折线顶端/底端红色切口 (FLANGE)
    for i, x in enumerate(bend_lines()):
        d_line(msp, (x, 0), (x, FLANGE_Y - 4), "BEND", 25)   # 折线到法兰线上方
        d_line(msp, (x, 0), (x, NOTCH_TOP), "FLANGE", 30)     # 顶端切口 18mm
        d_line(msp, (x, NOTCH_BOT[i]), (x, H_ALL), "FLANGE", 30)  # 底端切口到底板
    # 法兰线: 蓝虚线全宽 + 红实线段切割
    d_line(msp, (0, FLANGE_Y), (W_ALL, FLANGE_Y), "BEND", 20)
    for x0, x1 in FLANGE_CUTS:
        d_line(msp, (x0, FLANGE_Y), (x1, FLANGE_Y), "FLANGE", 40)
    # 接缝标记
    for x in (0.0, W_ALL):
        d_line(msp, (x, 4), (x, H_ALL - 4), "BEND", 25)
    # 法兰孔 8xØ7
    for x in flange_holes():
        d_circle(msp, (x, HOLE_Y), HOLE_D / 2)
    # 散热孔阵 (可选)
    pts, d = cool_holes()
    for (x, y) in pts:
        d_circle(msp, (x, y), d / 2, "HATCH", 9)
    # 4 面散热孔 (圆头长条孔: 两条直线 + 两个半圆弧)
    for (x0, y0, x1, y1, w) in vent_slots():
        add_slot_lwpolyline(msp, (x0, y0), (x1, y1), w, "HATCH")
    # 中心线
    for x in bend_lines():
        d_line(msp, (x, -14), (x, H_ALL + 14), "CENTER", 13)
    # ── 尺寸标注 ──
    for i in range(4):
        d_dim_h(msp, i * FACE_W, (i + 1) * FACE_W, 0, "150", off=-10, h=4)
    d_dim_h(msp, 0, W_ALL, 0, TOP_DIM, off=-22, h=6)
    d_dim_v(msp, W_ALL, 0, H_ALL, "300", off=14, h=6)
    d_dim_v(msp, W_ALL, FLANGE_Y, H_ALL, "30", off=26, h=5)
    d_dim_v(msp, 0, 0, FLANGE_Y, "270", off=-16, h=5)
    # 法兰孔定位尺寸链
    xm = bend_lines()[1]
    d_dim_v(msp, 0, HOLE_Y, H_ALL, "15", off=-30, h=4)                   # 孔心距板边 15
    d_dim_v(msp, W_ALL, HOLE_Y, H_ALL, "15", off=38, h=4)
    # ── 文字 (与参考图同构) ──
    for i, nm in enumerate(["F1 长面", "F2 长面", "F3 长面", "F4 长面"]):
        d_text(msp, nm, i * FACE_W + FACE_W / 2, 122, 6, "TEXT", center=True)
    d_text(msp, "散热孔(洞洞板): 圆头长条孔 30×5mm, 间隔7mm",
           W_ALL / 2, 80, 5.5, "TEXT", center=True)
    d_text(msp, "F1/F3 斜孔45°(正/反)  F2横孔  F4竖孔  开孔区四周距折线/边缘 2cm",
           W_ALL / 2, 66, 5, "TEXT", center=True)
    d_text(msp, "另一端顶部距边2cm: 每面3个短长孔 30×5, 净距10 (一圈共12)",
           W_ALL / 2, 52, 5, "TEXT", center=True)
    d_text(msp, "红色实线切开1cm给折痕做定位，法兰3cm红色实线全切开方便折叠对螺丝孔",
           W_ALL / 2, 207, 5, "FLANGE", center=True)
    d_text(msp, "30mm 法兰·沿此线内折 90°(四角双层重叠)",
           W_ALL / 2, FLANGE_Y - 9, 5.5, "BEND", center=True)
    d_text(msp, "法兰孔 8×Ø7：距板边 15，每道折线/接缝两侧各 1 个；折后四角各 2 孔重叠，",
           W_ALL / 2, -16, 4.5, "DIM", center=True)
    d_text(msp, "与端板 A / B 四角 Ø7 螺丝孔对齐",
           W_ALL / 2, -24, 4.5, "DIM", center=True)
    # 标题栏
    tb_x, tb_y = W_ALL, -62
    msp.add_lwpolyline([(tb_x - 210, tb_y), (tb_x, tb_y), (tb_x, tb_y + 48),
                        (tb_x - 210, tb_y + 48), (tb_x - 210, tb_y)],
                       close=True, dxfattribs={"layer": "CUT", "lineweight": 25})
    for i in range(1, 4):
        d_line(msp, (tb_x - 210, tb_y + i * 12), (tb_x, tb_y + i * 12), "CUT", 18)
    for i, s in enumerate(TITLE_INFO):
        d_text(msp, s, tb_x - 205, tb_y + 40 - i * 12, 4.5, "TEXT")
    doc.saveas(path)
    return path


def build_plate_dxf(path, with_clip):
    """端板 150x150: 全尺寸标注版
    豁口 8x8 @120°：豁口内边与 Ø100 圆周对齐（边与边对齐，中心在 R+4 处）"""
    doc, msp = setup_doc()
    d_rect(msp, 0, 0, PLATE, PLATE)
    cx = cy = PLATE / 2
    d_circle(msp, (cx, cy), BIG_D / 2, "CUT", 30)
    d_line(msp, (cx - PLATE / 2 - 10, cy), (cx + PLATE / 2 + 10, cy), "CENTER", 13)
    d_line(msp, (cx, cy - PLATE / 2 - 10), (cx, cy + PLATE / 2 + 10), "CENTER", 13)
    for sx in (CORNER_IN, PLATE - CORNER_IN):
        for sy in (CORNER_IN, PLATE - CORNER_IN):
            d_circle(msp, (sx, sy), CORNER_D / 2)
    if with_clip:
        R = BIG_D / 2            # 50mm
        for ang in CLIP_ANGLES:
            th = math.radians(ang)
            u = (math.cos(th), math.sin(th))        # 径向单位向量
            v = (-math.sin(th), math.cos(th))       # 切向单位向量
            # 豁口中心位于 R + CLIP/2 = 54mm（内边贴合圆周, 向外开口 8mm）
            rmid = R + CLIP / 2
            pcx = cx + rmid * u[0]
            pcy = cy + rmid * u[1]
            pts = []
            for s1 in (-CLIP / 2, CLIP / 2):
                for s2 in (-CLIP / 2, CLIP / 2):
                    pts.append((pcx + s1 * u[0] + s2 * v[0],
                                pcy + s1 * u[1] + s2 * v[1]))
            # 顺序: 逆时针
            order = [0, 2, 3, 1]
            poly = [pts[i] for i in order] + [pts[0]]
            msp.add_lwpolyline(poly, close=True,
                               dxfattribs={"layer": "FLANGE", "lineweight": 25})
    # ── 尺寸标注 ──
    # 外框
    d_dim_h(msp, 0, PLATE, 0, "150", off=-10, h=5)
    d_dim_h(msp, 0, PLATE, PLATE, "150", off=10, h=5)
    d_dim_v(msp, 0, 0, PLATE, "150", off=-10, h=5)
    d_dim_v(msp, PLATE, 0, PLATE, "150", off=10, h=5)
    # 角孔定位 (15 / 15)
    d_dim_h(msp, 0, CORNER_IN, PLATE - CORNER_IN, "15", off=-18, h=4)
    d_dim_v(msp, CORNER_IN, 0, PLATE - CORNER_IN, "15", off=-18, h=4)
    d_dim_h(msp, CORNER_IN, PLATE - CORNER_IN, 0, "120", off=-18, h=4)
    d_dim_v(msp, 0, CORNER_IN, PLATE - CORNER_IN, "120", off=-18, h=4)
    # 中心圆 Ø100 + 直径标注
    d_line(msp, (cx - BIG_D / 2 - 8, cy), (cx + BIG_D / 2 + 8, cy), "DIM", 13)
    d_line(msp, (cx - BIG_D / 2 - 4, cy - 1.2), (cx - BIG_D / 2 - 4, cy + 1.2), "DIM", 13)
    d_line(msp, (cx + BIG_D / 2 + 4, cy - 1.2), (cx + BIG_D / 2 + 4, cy + 1.2), "DIM", 13)
    d_text(msp, "Ø100", cx - 12, cy - 8, 5.5, "DIM", center=True)
    # 豁口标注 (8x8 + 角度)
    if with_clip:
        d_text(msp, "3×8×8", PLATE + 12, PLATE - 30, 4.5, "FLANGE")
        d_text(msp, "卡口 @120°", PLATE + 12, PLATE - 40, 4.5, "FLANGE")
        d_text(msp, "90°/210°/330°", PLATE + 12, PLATE - 50, 4, "FLANGE")
        # 角度定位线 (90° 顶点)
        d_line(msp, (cx, cy), (cx, cy + BIG_D / 2), "CENTER", 13)
    # 角孔注记
    d_text(msp, "4×Ø7 距边15", 2, PLATE - 8, 4.5, "DIM")
    if with_clip:
        d_text(msp, "端板A - 最外端板(带卡口)", PLATE / 2, -24, 6, "TEXT", center=True)
    else:
        d_text(msp, "端板B - 中间端板(无卡口)", PLATE / 2, -24, 6, "TEXT", center=True)
    # 标题栏
    tb_x, tb_y = PLATE, -62
    msp.add_lwpolyline([(tb_x - 170, tb_y), (tb_x, tb_y), (tb_x, tb_y + 48),
                        (tb_x - 170, tb_y + 48), (tb_x - 170, tb_y)],
                       close=True, dxfattribs={"layer": "CUT", "lineweight": 25})
    for i in range(1, 4):
        d_line(msp, (tb_x - 170, tb_y + i * 12), (tb_x, tb_y + i * 12), "CUT", 18)
    for i, s in enumerate(TITLE_INFO):
        d_text(msp, s, tb_x - 165, tb_y + 40 - i * 12, 4.5, "TEXT")
    doc.saveas(path)
    return path


# ═════════════════════════ PNG 预览 (单视图, 复刻参考图) ═════════════════════════
fp = fm.FontProperties(fname=FONT_PATH)
fpb = fm.FontProperties(fname=FONT_BOLD)
plt.rcParams["axes.unicode_minus"] = False
DPI = 100

def txt(ax, x, y, s, size=9, color=C_TXT, weight="normal", ha="center", va="center"):
    ax.text(x, y, s, fontproperties=fpb if weight == "bold" else fp,
            fontsize=size, color=color, ha=ha, va=va, zorder=6)


def slot_patch(p0, p1, w, color="#B9A26B", lw=0.8):
    """圆头长条孔 Patch: 两端半圆 + 两条直边 (matplotlib Path)"""
    from matplotlib.path import Path as MPath
    import numpy as _np
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    r = w / 2
    a = (x0 + nx * r, y0 + ny * r)
    b = (x1 + nx * r, y1 + ny * r)
    c = (x1 - nx * r, y1 - ny * r)
    d_ = (x0 - nx * r, y0 - ny * r)
    verts = [a, b]
    codes = [MPath.MOVETO, MPath.LINETO]
    # b → c 半圆 (圆心 x1,y1, 半径 r, 从角 β+90° 到 β-90°)
    beta = math.atan2(dy, dx)
    for k in range(1, 9):
        th = beta + math.pi / 2 - math.pi * k / 8
        verts.append((x1 + r * math.cos(th), y1 + r * math.sin(th)))
        codes.append(MPath.LINETO)
    verts.append(c)
    codes.append(MPath.LINETO)
    verts.append(d_)
    codes.append(MPath.LINETO)
    for k in range(1, 9):
        th = beta + math.pi * k / 8 - math.pi / 2 + math.pi
        verts.append((x0 + r * math.cos(th), y0 + r * math.sin(th)))
        codes.append(MPath.LINETO)
    verts.append(a)
    codes.append(MPath.LINETO)
    return plt.Polygon(verts, closed=True, fill=False, edgecolor=color,
                       lw=lw, zorder=3)

def dim_h(ax, x1, x2, y, s, off=0, size=9, color=C_DIM, ext=True):
    yo = y + off
    if ext:
        for x in (x1, x2):
            ax.plot([x, x], [y + (1.5 if off >= 0 else -1.5), yo], color=color, lw=0.8, zorder=4)
    ax.annotate("", xy=(x1, yo), xytext=(x2, yo),
                arrowprops=dict(arrowstyle="<|-|>", color=color, lw=0.9, mutation_scale=8), zorder=5)
    txt(ax, (x1 + x2) / 2, yo + (5 if off >= 0 else -6), s, size, color)

def dim_v(ax, x, y1, y2, s, off=0, size=9, color=C_DIM, ext=True):
    xo = x + off
    if ext:
        for y in (y1, y2):
            ax.plot([x + (1.5 if off >= 0 else -1.5), xo], [y, y], color=color, lw=0.8, zorder=4)
    ax.annotate("", xy=(xo, y1), xytext=(xo, y2),
                arrowprops=dict(arrowstyle="<|-|>", color=color, lw=0.9, mutation_scale=8), zorder=5)
    txt(ax, xo + (-6 if off >= 0 else 6), (y1 + y2) / 2, s, size, color, va="center")

def draw_blank(ax):
    """展开板 (复刻参考图)"""
    # 法兰带底色
    ax.add_patch(Rectangle((0, FLANGE_Y), W_ALL, H_ALL - FLANGE_Y,
                           facecolor="#F2ECDD", edgecolor="none", zorder=0))
    # 外轮廓
    ax.add_patch(Rectangle((0, 0), W_ALL, H_ALL, fill=False,
                           edgecolor=C_INK, lw=2.0, zorder=3))
    # 折弯线 (蓝虚线) + 顶端红色切口 + 底端红色切口
    for i, x in enumerate(bend_lines()):
        ax.plot([x, x], [0, FLANGE_Y - 4], color=C_BEND, lw=1.3,
                ls=(0, (9, 3, 1.5, 3)), zorder=3)
        ax.plot([x, x], [0, NOTCH_TOP], color=C_RED, lw=3.2, zorder=4)
        ax.plot([x, x], [NOTCH_BOT[i], H_ALL], color=C_RED, lw=3.2, zorder=4)
    # 法兰线: 蓝虚线 + 红实线段
    ax.plot([0, W_ALL], [FLANGE_Y, FLANGE_Y], color=C_BEND, lw=1.2,
            ls=(0, (9, 3, 1.5, 3)), zorder=3)
    for x0, x1 in FLANGE_CUTS:
        ax.plot([x0, x1], [FLANGE_Y, FLANGE_Y], color=C_RED, lw=3.6, zorder=4)
    # 接缝
    for x in (0.0, W_ALL):
        ax.plot([x, x], [6, H_ALL - 6], color=C_BEND, lw=1.2,
                ls=(0, (9, 3, 1.5, 3)), alpha=.8, zorder=2)
    # 法兰孔
    for x in flange_holes():
        ax.add_patch(Circle((x, HOLE_Y), HOLE_D / 2, fill=False,
                            edgecolor=C_HOLE, lw=1.4, zorder=4))
    # 散热孔阵 (可选)
    pts, d = cool_holes()
    for (x, y) in pts:
        ax.add_patch(Circle((x, y), d / 2, fill=False,
                            edgecolor="#B9A26B", lw=0.6, zorder=2))
    # 4 面散热孔: 圆头长条孔 (半圆 + 矩形, 用 Path)
    for (x0, y0, x1, y1, w) in vent_slots():
        ax.add_patch(slot_patch((x0, y0), (x1, y1), w, "#B9A26B"))
    # 分面标签 (参考图在 y≈122)
    for i, nm in enumerate(["F1 长面", "F2 长面", "F3 长面", "F4 长面"]):
        txt(ax, i * FACE_W + FACE_W / 2, 122, nm, 11, C_BEND, "bold")
    # 文字
    txt(ax, W_ALL / 2, 80, "散热孔（洞洞板）：圆头长条孔 30×5mm，间隔 7mm", 10, C_TXT)
    txt(ax, W_ALL / 2, 66, "F1/F3 斜孔 45°（正/反）　F2 横孔　F4 竖孔　开孔区四周距折线/边缘 2cm", 9, C_TXT)
    txt(ax, W_ALL / 2, 52, "另一端顶部距边 2cm：每面 3 个短长孔 30×5，净距 10（一圈共 12）", 9, C_TXT)
    txt(ax, W_ALL / 2, 207,
        "红色实线切开 1cm 给折痕做定位，法兰 3cm 红色实线全切开方便折叠对螺丝孔", 9, C_RED)
    txt(ax, W_ALL / 2, FLANGE_Y - 16, "30mm 法兰 · 沿此线内折 90°（四角双层重叠）",
        10, C_BEND, "bold")
    # 法兰孔说明放板下方空白区 (y 向下: 板底 300, 下方 315/327)
    txt(ax, W_ALL / 2, 316, "法兰孔 8×Ø7 —— 每道折线 / 接缝两侧各 1 个，距板边 15，折后四角各 2 孔重叠", 9, C_HOLE)
    txt(ax, W_ALL / 2, 328, "与端板 A / B 四角 Ø7 螺丝孔对齐", 9, C_HOLE)
    # 尺寸
    for i in range(4):
        dim_h(ax, i * FACE_W, (i + 1) * FACE_W, 0, "150", -12, 8.5)
    dim_h(ax, 0, W_ALL, 0, TOP_DIM, -24, 12, C_INK)
    dim_v(ax, W_ALL, 0, H_ALL, "300", 16, 12, C_INK)
    dim_v(ax, W_ALL, FLANGE_Y, H_ALL, "30", 28, 9, C_RED)
    dim_v(ax, 0, 0, FLANGE_Y, "270", -20, 9.5)
    # 法兰孔距板边 15 (板外侧留白区, 不压法兰带文字)
    dim_v(ax, 0, HOLE_Y, H_ALL, "15", -32, 8, C_HOLE)
    dim_v(ax, W_ALL, HOLE_Y, H_ALL, "15", 40, 8, C_HOLE)


def sheet():
    """单视图预览: 复刻手绘参考图布局"""
    fig = plt.figure(figsize=(12.8, 7.6), dpi=DPI, facecolor=C_BG)
    fig.text(0.5, 0.965, "保荣摄影灯外壳 · 钣金展开图", fontproperties=fpb,
             fontsize=16, color=C_INK, ha="center")
    fig.text(0.5, 0.938, "15 × 15 × 27 cm 方灯壳　|　2mm 不锈钢板　|　单位:mm",
             fontproperties=fp, fontsize=10, color=C_TXT, ha="center")

    ax = fig.add_axes([0.12, 0.06, 0.78, 0.84])
    ax.set_xlim(-45, 650)
    ax.set_ylim(330, -85)      # y 向下增长: y=0(折弯定位切口端/板顶)在上, y=300(法兰带)在下
    ax.set_aspect("equal")
    ax.axis("off")
    draw_blank(ax)

    fig.text(0.5, 0.018, "图号 BR-LAMP-01　|　比例 1:1　|　孔距未注公差 ±0.2",
             fontproperties=fp, fontsize=8.5, color=C_DIM, ha="center")
    out = os.path.join(OUT_DIR, "灯壳_洞洞板展开_600x300_预览.png")
    fig.savefig(out, dpi=DPI, facecolor=C_BG)
    plt.close(fig)
    return out


def plate_png(path, with_clip, title):
    fig, ax = plt.subplots(figsize=(7.6, 9.2), dpi=DPI, facecolor=C_BG)
    fig.subplots_adjust(left=0.03, right=0.97, top=0.90, bottom=0.03)
    ax.set_xlim(-55, 215)
    ax.set_ylim(-70, 212)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), PLATE, PLATE, facecolor="#FBFAF6",
                           edgecolor=C_INK, lw=2.4, zorder=3))
    cx = cy = PLATE / 2
    ax.plot([cx - PLATE / 2 - 8, cx + PLATE / 2 + 8], [cy, cy], color=C_DIM,
            lw=0.8, ls=(0, (7, 3, 1, 3)), zorder=2)
    ax.plot([cx, cx], [cy - PLATE / 2 - 8, cy + PLATE / 2 + 8], color=C_DIM,
            lw=0.8, ls=(0, (7, 3, 1, 3)), zorder=2)
    ax.add_patch(Circle((cx, cy), BIG_D / 2, fill=False, edgecolor=C_INK, lw=2.2, zorder=3))
    for sx in (CORNER_IN, PLATE - CORNER_IN):
        for sy in (CORNER_IN, PLATE - CORNER_IN):
            ax.add_patch(Circle((sx, sy), CORNER_D / 2, fill=False,
                                edgecolor=C_HOLE, lw=1.5, zorder=4))
    if with_clip:
        R = BIG_D / 2
        clip_pts = []
        for ang in CLIP_ANGLES:
            th = math.radians(ang)
            u = (math.cos(th), math.sin(th))
            v = (-math.sin(th), math.cos(th))
            rmid = R + CLIP / 2
            pcx = cx + rmid * u[0]
            pcy = cy + rmid * u[1]
            pts = []
            for s1 in (-CLIP / 2, CLIP / 2):
                for s2 in (-CLIP / 2, CLIP / 2):
                    pts.append((pcx + s1 * u[0] + s2 * v[0],
                                pcy + s1 * u[1] + s2 * v[1]))
            order = [0, 2, 3, 1]
            poly = [pts[i] for i in order] + [pts[0]]
            clip_pts.append(poly)
        for poly in clip_pts:
            ax.add_patch(plt.Polygon(poly, fill=False, edgecolor=C_RED, lw=2.0, zorder=4))
    # ── 尺寸标注 ──
    dim_h(ax, 0, PLATE, 0, "150", -14, 11, C_INK)
    dim_h(ax, 0, PLATE, PLATE, "150", 14, 11, C_INK)
    dim_v(ax, 0, 0, PLATE, "150", -14, 11, C_INK)
    dim_v(ax, PLATE, 0, PLATE, "150", 14, 11, C_INK)
    # 角孔定位
    dim_h(ax, 0, CORNER_IN, PLATE - CORNER_IN, "15", -22, 8.5, C_DIM)
    dim_v(ax, CORNER_IN, 0, PLATE - CORNER_IN, "15", -22, 8.5, C_DIM)
    dim_h(ax, CORNER_IN, PLATE - CORNER_IN, 0, "120", -22, 8.5, C_DIM)
    dim_v(ax, 0, CORNER_IN, PLATE - CORNER_IN, "120", -22, 8.5, C_DIM)
    # 角孔直径注记
    txt(ax, CORNER_IN, CORNER_IN - 12, "Ø7", 8.5, C_HOLE)
    # 中心圆直径标注
    ax.annotate("", xy=(cx - BIG_D/2, cy), xytext=(cx + BIG_D/2, cy),
                arrowprops=dict(arrowstyle="<|-|>", color=C_INK, lw=1.0,
                                mutation_scale=9), zorder=5)
    txt(ax, cx, cy - 10, "Ø100", 10, C_INK, "bold")
    # 中心记号
    txt(ax, cx, cy + 8, "+", 9, C_DIM)
    # 划线到外圆
    ax.plot([cx, cx + BIG_D/2], [cy+6, cy+6], color=C_DIM, lw=0.5, ls=(0,(2,2)))
    # 卡口尺寸引线标注 (8mm) — 指向 210° 卡口 (与用户预览图一致)
    if with_clip:
        kx = cx + (BIG_D / 2 + CLIP / 2) * math.cos(math.radians(210))
        ky = cy + (BIG_D / 2 + CLIP / 2) * math.sin(math.radians(210))
        ax.annotate("", xy=(kx, ky), xytext=(17, 138),
                    arrowprops=dict(arrowstyle="-", color=C_RED, lw=0.9,
                                    mutation_scale=7), zorder=5)
        txt(ax, 22, 138, "8", 9, C_RED)
    # 豁口说明
    if with_clip:
        txt(ax, PLATE / 2, -40, "卡口 3×8×8 @120°（90°/210°/330°）", 9.5, C_RED)
        txt(ax, PLATE / 2, -52, "卡口内边与 Ø100 圆周对齐（边与边对齐）", 8.5, C_RED)
    txt(ax, PLATE / 2, -28, title, 11, C_TXT, "bold")
    txt(ax, PLATE / 2, -64, "四角 4×Ø7 通孔（距边 15）", 9, C_HOLE)
    if with_clip:
        fig.text(0.5, 0.965, "保荣摄影灯外壳 · 端板 A（最外端板·带卡口）", fontproperties=fpb,
                 fontsize=15, color=C_INK, ha="center")
        fig.text(0.5, 0.02, "图号 BR-LAMP-02　|　比例 1:1　|　2mm 不锈钢　|　尺寸单位 mm",
                 fontproperties=fp, fontsize=8.5, color=C_DIM, ha="center")
    else:
        fig.text(0.5, 0.965, "保荣摄影灯外壳 · 端板 B（中间端板·无卡口）", fontproperties=fpb,
                 fontsize=15, color=C_INK, ha="center")
        fig.text(0.5, 0.02, "图号 BR-LAMP-03　|　比例 1:1　|　2mm 不锈钢　|　尺寸单位 mm",
                 fontproperties=fp, fontsize=8.5, color=C_DIM, ha="center")
    fig.savefig(path, dpi=DPI, facecolor=C_BG)
    plt.close(fig)
    return path


if __name__ == "__main__":
    made = []
    made.append(build_blank_dxf(os.path.join(OUT_DIR, "灯壳_洞洞板展开_600x300.dxf")))
    made.append(build_plate_dxf(os.path.join(OUT_DIR, "端板A_带卡口_150x150.dxf"), True))
    made.append(build_plate_dxf(os.path.join(OUT_DIR, "端板B_中间板_150x150.dxf"), False))
    made.append(sheet())
    made.append(plate_png(os.path.join(OUT_DIR, "端板A_带卡口_150x150_预览.png"),
                          True, "端板 A（最外端板·带卡口）"))
    made.append(plate_png(os.path.join(OUT_DIR, "端板B_中间板_150x150_预览.png"),
                          False, "端板 B（中间端板·无卡口）"))
    for f in made:
        print("OK", f, os.path.getsize(f), "bytes")