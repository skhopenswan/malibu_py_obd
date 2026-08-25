#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迈锐宝 1.5T (LFV) OBD 200km 高速日志 · 完整动力诊断图 + 6T45 变速箱油温诊断图
输入: data_logs/malibu_obd_log_20260823_172509.csv
输出: AI_agent_analysis/ 下的两张 PNG 与事件列表 JSON + 分析报告 md

图1 完整动力曲线诊断图: RPM/Speed, MAP/Boost, MAF/Throttle/Load, STFT/LTFT, ECT/IAT, TFT
图2 6T45 油温诊断:   TFT + Speed/RPM/Load + 急加速事件升温/恢复标注
"""
import csv
import os
import json
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

# ---------------------------------------------------------------- 中文
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(os.path.dirname(BASE), "data_logs",
                        "malibu_obd_log_20260823_172509.csv")

# 列索引映射
I = {
    "t": 0, "rpm": 1, "map": 2, "maf": 3, "thr": 4, "relthr": 5,
    "load": 6, "stft": 7, "ltft": 8, "o2f": 9, "o2r": 10, "cat": 11,
    "eq": 12, "boost": 13, "spd": 14, "ect": 15, "iat": 16, "baro": 17,
    "tim": 18, "volt": 19, "fuel": 20, "amb": 21, "tft": 22,
}
NUM_KEYS = [k for k in I if k != "t"]


def _num(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return np.nan


def load():
    rows = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        rd = csv.reader(f)
        next(rd)
        for r in rd:
            rows.append(r)
    n = len(rows)
    t = np.full(n, np.nan)
    c = {k: np.full(n, np.nan) for k in NUM_KEYS}
    t0 = datetime.strptime(rows[0][0], "%Y-%m-%d %H:%M:%S.%f")
    for i, r in enumerate(rows):
        t[i] = (datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S.%f") - t0).total_seconds()
        for k in NUM_KEYS:
            c[k][i] = _num(r[I[k]])
    return t, c


def savgol(x, w=7):
    """轻量滑动平均（去抖，保持趋势），窗口 w 为奇数。"""
    w = int(w)
    if w % 2 == 0:
        w += 1
    n = len(x)
    out = np.full_like(x, np.nan)
    half = w // 2
    for i in range(half, n - half):
        seg = x[i - half:i + half + 1]
        seg = seg[~np.isnan(seg)]
        if len(seg):
            out[i] = np.nanmean(seg)
    return out
def detect_accel_events(t, c):
    """
    抓取急加速事件（基于相对节气门突增 + 车速同步上升），逐段编号。
    返回事件列表 [{idx0, idx1, t0, t1, label, kind, ...}]
    """
    spd = c["spd"]
    thr = c["relthr"]
    nt = len(t)
    rt = savgol(thr, 5)
    rich_t = savgol(np.hstack([thr, thr, thr]), 31)[nt:2 * nt]

    # 相对节气门上升斜率（每秒增加量，约 %/s）
    dt = np.gradient(t)
    dthr = np.gradient(rich_t) / np.maximum(dt, 0.05)

    moving = spd > 3
    ramp = dthr > 3.5                      # 快速踩油门
    kick = np.zeros(nt, bool)

    acc = []
    i = 0
    while i < nt - 1:
        if ramp[i] and moving[i]:
            j = i
            while j + 1 < nt and (ramp[j + 1] or t[j + 1] - t[j] < 0.6):
                j += 1
                if t[j] - t[i] > 12:       # 事件最长 ~12s
                    break
            # 膨胀到事件前最低点 / 后平台
            a0, a1 = i, j
            while a0 > 0 and t[i] - t[a0 - 1] < 3 and thr[a0 - 1] <= thr[a0] + 0.5:
                a0 -= 1
            while a1 + 1 < nt and t[a1 + 1] - t[j] < 3 and thr[a1 + 1] >= thr[a1] - 0.5:
                a1 += 1
            if (a1 - a0) > 2:
                acc.append([a0, a1])
            i = j + 1
        else:
            i += 1

    # 合并重叠/相邻
    merged = []
    for a in acc:
        if merged and a[0] <= merged[-1][1] + 50:
            merged[-1][1] = max(merged[-1][1], a[1])
        else:
            merged.append(a)

    events = []
    for k, (a0, a1) in enumerate(merged):
        ev = {
            "id": k + 1,
            "idx0": int(a0), "idx1": int(a1),
            "t0": float(t[a0]), "t1": float(t[a1]),
            "dur_s": float(t[a1] - t[a0]),
        }
        # 窗口内关键特征
        seg_spd = spd[a0:a1 + 1] if a1 < nt else spd[a0:]
        seg_rpm = c["rpm"][a0:a1 + 1]
        seg_boost = c["boost"][a0:a1 + 1]
        seg_maf = c["maf"][a0:a1 + 1]
        seg_map = c["map"][a0:a1 + 1]
        seg_baro = c["baro"][a0:a1 + 1]
        seg_thr = thr[a0:a1 + 1]
        seg_rel = c["relthr"][a0:a1 + 1]
        seg_load = c["load"][a0:a1 + 1]
        seg_tft = c["tft"][a0:a1 + 1]

        def safe(x):
            x = x[~np.isnan(x)]
            return x

        v0 = safe(seg_spd); v1 = safe(seg_rpm); v2 = safe(seg_boost)
        v3 = safe(seg_maf); v4 = safe(seg_map); v5 = safe(seg_baro)
        v6 = safe(seg_rel); v7 = safe(seg_load); v8 = safe(seg_tft)
        ev_v0 = safe(c["spd"][:a0])[-1] if a0 > 0 else 0
        ev_v1 = safe(c["rpm"][:a0])[-1] if a0 > 0 else 0

        spd_from = float(ev_v0) if (a0 > 0 and ev_v0 is not None) else 0.0
        rpm_from = float(ev_v1) if (a0 > 0 and ev_v1 is not None) else 0.0
        spd_to = float(v0[-1]) if len(v0) else float("nan")
        dur = ev["dur_s"]
        e_rate = (spd_to - spd_from) / max(dur, 0.1) if (spd_to == spd_to and spd_from == spd_from) else 0
        rpm_max = float(v1.max()) if len(v1) else float("nan")
        rpm_delta = (rpm_max - rpm_from) if (rpm_max == rpm_max and rpm_from == rpm_from) else 0

        boost_peak = float(v2.max()) if len(v2) else float("nan")
        boost_p98 = float(np.nanpercentile(v2, 98)) if len(v2) else float("nan")
        maf_max = float(v3.max()) if len(v3) else float("nan")
        thr_max = float(v6.max()) if len(v6) else float("nan")
        load_max = float(v7.max()) if len(v7) else float("nan")
        tft_from = float(v8[0]) if len(v8) else float("nan")
        tft_peak = float(v8.max()) if len(v8) else float("nan")
        tft_rise = (tft_peak - tft_from) if (tft_from == tft_from) else float("nan")

        ev.update({
            "spd_from": spd_from, "spd_to": spd_to, "spd_rate_kph_s": e_rate,
            "rpm_from": rpm_from, "rpm_max": rpm_max, "rpm_delta": rpm_delta,
            "boost_max": ev_boost if (ev_boost := boost_peak) else boost_peak,
            "boost_peak": boost_peak, "boost_p98": boost_p98,
            "maf_max": maf_max, "thr_max": thr_max, "load_max": load_max,
            "tft_from": tft_from, "tft_peak": tft_peak, "tft_rise": tft_rise,
        })

        # ---------- 分类 ----------
        kinds = []
        if boost_p98 > 0.05 or boost_peak > 0.05:
            kinds.append("真实增压")
        else:
            kinds.append("增压不足")
        if rpm_delta > 250 and e_rate < 2.5:
            kinds.append("疑似降档")
        if thr_max > 55 and boost_peak < 0.25 and rpm_max < 3500:
            kinds.append("扭矩受限")
        if dur > 2.5 and rpm_delta > 400 and e_rate < 4.0 and spd_from > 20:
            kinds.append("疑似滑差")
        ev["kind"] = " + ".join(kinds) if kinds else ("常规加速" if e_rate >= 2.0 else "巡航微调")
        events.append(ev)
    return events


def safe_prev(arr, idx):
    """取 idx 之前最近的有效数值。"""
    j = idx - 1
    while j >= 0 and np.isnan(arr[j]):
        j -= 1
    return float(arr[j]) if j >= 0 else float("nan")
# ---------------------------------------------------------------- 绘图：图1 完整动力曲线
def build_power_fig(t, c, events):
    fig, axs = plt.subplots(6, 1, figsize=(16, 16), sharex=True,
                            gridspec_kw={"hspace": 0.10})
    for ax in axs:
        for ev in events:
            ax.axvspan(ev["t0"] / 60, ev["t1"] / 60, color="#ffd54d", alpha=0.18, lw=0)
    # 1 RPM + Speed
    ax = axs[0]
    ax.plot(t / 60, c["rpm"], color="#1565c0", lw=0.7, label="RPM")
    ax.set_ylabel("RPM", color="#1565c0")
    ax2 = ax.twinx()
    ax2.plot(t / 60, c["spd"], color="#2e7d32", lw=0.7, label="SPEED")
    ax2.set_ylabel("Speed(km/h)", color="#2e7d32")
    ax2.grid(False)
    for ev in events:
        ax.text(ev["t0"] / 60, ax.get_ylim()[1] * 0.97,
                "E" + str(ev["id"]) + ":" + ev["kind"],
                fontsize=6.5, color="#b71c1c", rotation=90, va="top")
    ax.set_title("完整动力曲线诊断  黄底=急加速事件 顶部标注编号与判定", loc="left", fontsize=10)
    ax.legend(loc="upper left", fontsize=7)
    ax = axs[1]
    ax.plot(t / 60, c["map"], color="#8e24aa", lw=0.6, label="MAP")
    ax.plot(t / 60, c["baro"], color="#90a4ae", lw=0.6, ls="--", label="Baro")
    ax.set_ylabel("MAP/Baro(kPa)")
    ax2 = ax.twinx()
    ax2.axhline(0, color="grey", lw=0.5)
    ax2.plot(t / 60, c["boost"], color="#e53935", lw=0.9, label="Boost")
    ax2.axhline(0.3, color="orange", lw=0.4, ls="--")
    ax2.set_ylabel("Boost(bar)", color="#e53935")
    ax2.grid(False)
    ax.legend(loc="upper left", fontsize=7)
    ax2.legend(loc="upper right", fontsize=7)

    ax = axs[2]
    ax.plot(t / 60, c["maf"], color="#00838f", lw=0.8, label="MAF_g_s")
    ax.set_ylabel("MAF(g/s)")
    ax2 = ax.twinx()
    ax2.plot(t / 60, c["relthr"], color="#fb8c00", lw=0.7, label="RelThrottle")
    ax2.plot(t / 60, c["load"], color="#6a1b9a", lw=0.6, ls=":", label="Load%")
    ax2.set_ylabel("Throttle%/Load%", color="#fb8c00")
    ax2.grid(False)
    ax.legend(loc="upper left", fontsize=7)
    ax2.legend(loc="upper right", fontsize=7)

    ax = axs[3]
    ax.axhline(0, color="grey", lw=0.5)
    ax.plot(t / 60, c["stft"], color="#00796b", lw=0.5, label="STFT%")
    ax.plot(t / 60, c["ltft"], color="#c62828", lw=1.1, label="LTFT%")
    ax.axhline(10, color="red", lw=0.4, ls="--")
    ax.axhline(-10, color="red", lw=0.4, ls="--")
    ax.set_ylabel("STFT/LTFT%")
    ax.legend(loc="upper right", fontsize=7)

    ax = axs[4]
    ax.plot(t / 60, c["ect"], color="#d32f2f", lw=0.9, label="ECT")
    ax.plot(t / 60, c["iat"], color="#0288d1", lw=0.8, label="IAT")
    ax.set_ylabel("Temp(C)")
    ax.legend(loc="upper right", fontsize=7)

    ax = axs[5]
    ax.plot(t / 60, c["tft"], color="#5d4037", lw=1.0, label="TFT")
    ax.axhline(70, color="grey", lw=0.4, ls="--")
    ax.axhline(85, color="orange", lw=0.4, ls="--")
    ax.set_ylabel("TFT(C)")
    ax.legend(loc="upper left", fontsize=7)

    for ax in axs:
        ax.grid(alpha=0.25)
        ax.set_xlabel("时间(min)")
    out = os.path.join(BASE, "diag_power_diagnostic.png")
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out
# ---------------------------------------------------------------- 绘图：图2 6T45 油温诊断
def build_tft_fig(t, c, events):
    fig, axs = plt.subplots(3, 1, figsize=(15, 11), sharex=True,
                            gridspec_kw={"hspace": 0.14})

    ax = axs[0]
    for ev in events:
        ax.axvspan(ev["t0"] / 60, ev["t1"] / 60, color="#ffd54d", alpha=0.18, lw=0)
    sm = savgol(c["tft"].astype(float), 41)
    ax.plot(t / 60, c["tft"], color="#5d4037", lw=0.8, alpha=0.8, label="TFT_raw")
    ax.plot(t / 60, sm, color="#e53935", lw=1.6, label="TFT_MA(~17s)")
    ax.axhline(70, color="grey", lw=0.6, ls="--")
    ax.axhline(85, color="orange", lw=0.6, ls="--")
    ax.axhline(95, color="red", lw=0.6, ls="--")
    for ev in events:
        ax.text(ev["t0"] / 60, 95.5, "E" + str(ev["id"]), fontsize=7, color="#6d4c41")
        if ev["tft_rise"] == ev["tft_rise"]:
            ax.text(ev["t0"] / 60, 91, "d" + str(round(ev["tft_rise"])) + "C",
                    fontsize=6, color="#c62828")
    ax.set_ylabel("TFT(C)")
    ax.set_ylim(60, 100)
    ax.set_title("6T45 变速箱油温诊断曲线  (黄底=急加速事件, 顶部=事件号/升温幅度)", loc="left", fontsize=11)
    ax.legend(loc="upper right", fontsize=7)

    ax = axs[1]
    ax.plot(t / 60, c["spd"], color="#2e7d32", lw=0.9, label="Speed")
    ax.set_ylabel("km/h", color="#2e7d32")
    ax2 = ax.twinx()
    ax2.plot(t / 60, c["rpm"], color="#1565c0", lw=0.7, label="RPM")
    ax2.plot(t / 60, c["load"], color="#6a1b9a", lw=0.6, ls=":", label="Load%")
    ax2.set_ylabel("RPM/Load%")
    ax2.grid(False)
    ax.legend(loc="upper left", fontsize=7)
    ax2.legend(loc="upper right", fontsize=7)

    ax = axs[2]
    ids = [e["id"] for e in events]
    rise = [e["tft_rise"] for e in events]
    frm = [e["tft_from"] if e["tft_from"] == e["tft_from"] else 0 for e in events]
    pk = [e["tft_peak"] if e["tft_peak"] == e["tft_peak"] else 0 for e in events]
    x = np.arange(len(events))
    ax.bar(x, rise, color="#8d6e63", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(ids, fontsize=7)
    ax.set_ylabel("事件内TFT升温 (C)")
    ax.set_xlabel("急加速事件编号 E1..E" + str(len(events)))
    ax.grid(alpha=0.3, axis="y")
    for xi, r, a, b in zip(x, rise, frm, pk):
        if r == r:
            ax.annotate("%.0f->%.0f d%.0f" % (a, b, r), (xi, r),
                        textcoords="offset points", xytext=(0, 3),
                        ha="center", fontsize=6, color="#3e2723")
    out = os.path.join(BASE, "diag_tft_thermal.png")
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out
# ---------------------------------------------------------------- 汇总输出
def build_summary(t, c, events):
    jp = os.path.join(BASE, "accel_events_20260823.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"events": events}, f, ensure_ascii=False, indent=1)

    names = ["真实增压", "疑似降档", "扭矩受限", "疑似滑差", "增压不足"]
    cnt = {nm: sum(1 for e in events if nm in e["kind"]) for nm in names}
    bo = [e["boost_p98"] for e in events if e["boost_p98"] == e["boost_p98"]]
    lines = [
        "# 迈锐宝 LFV 200km 高速动力与变速箱油温诊断汇总",
        "",
        "- 样本: %d 行 . 周期 %d 分钟 . 采样率 %.2fHz" % (t.size, t[-1] / 60, t.size / t[-1]),
        "- 车速峰值 %.0f km/h, 高速(>80)占比 %.0f%%" % (np.nanmax(c["spd"]), np.mean(c["spd"] > 80) * 100),
        "- RPM峰值 %.0f rpm, Boost峰值 %+.2f bar" % (np.nanmax(c["rpm"]), np.nanmax(c["boost"])),
        "- 事件Boost P98上限 %+.2f bar (若极低->涡轮/进气受限; 需结合油门)" % (np.nanpercentile(bo, 98) if bo else 0),
        "- LTFT 均值 %.1f%% 范围 %.1f..%.1f%% (持续大正>+10 才提示漏气)" % (np.nanmean(c["ltft"]), np.nanmin(c["ltft"]), np.nanmax(c["ltft"])),
        "- TFT 范围 %.0f..%.0f C (正常70-95)" % (np.nanmin(c["tft"]), np.nanmax(c["tft"])),
        "",
        "## 急加速事件判定 (共 %d)" % len(events),
        "| 类型 | 次数 |", "|---|---|",
    ]
    for nm in names:
        lines.append("| %s | %d |" % (nm, cnt[nm]))
    lines += ["", "### 明细"]
    lines.append("```")
    if events:
        for e in events:
            lines.append("  E%02d t=%6.1fmin dur=%4.1fs spd=%3.0f->%3.0f "
                         "boost98=%+.2f MAFmax=%5.1f RPMmax=%4.0f "
                         "loadmax=%3.0f TFT %3.0f->%3.0f [%s]" % (
                             e["id"], e["t0"] / 60, e["dur_s"], e["spd_from"],
                             e["spd_to"], e["boost_p98"], e["maf_max"],
                             e["rpm_max"], e["load_max"], e["tft_from"],
                             e["tft_peak"], e["kind"]))
    lines.append("```")
    md = os.path.join(BASE, "analysis_20260823_report.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return jp, md


# ---------------------------------------------------------------- 主程序
if __name__ == "__main__":
    t, c = load()
    events = detect_accel_events(t, c)
    print("载入 %d 条, 急加速事件 %d 起" % (len(t), len(events)))
    for e in events:
        print("  E%-2d t=%6.1fmin dur=%4.1fs spd=%3.0f->%3.0f boost98=%+.2f "
              "MAFmax=%5.1f RPMmax=%4.0f TFT %3.0f->%3.0f [%s]" % (
                  e["id"], e["t0"] / 60, e["dur_s"], e["spd_from"], e["spd_to"],
                  e["boost_p98"], e["maf_max"], e["rpm_max"],
                  e["tft_from"], e["tft_peak"], e["kind"]))
    p1 = build_power_fig(t, c, events)
    p2 = build_tft_fig(t, c, events)
    p3 = build_summary(t, c, events)
    print("已生成:")
    print(" ", p1)
    print(" ", p2)
    print("  JSON+MD:", p3[0], p3[1])