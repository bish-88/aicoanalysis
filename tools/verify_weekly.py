#!/usr/bin/env python3
"""週次レポート（お店づくりレポート②）のPDFと、ダッシュボード用データを照合する。

PDFの表の罫線を検出してセルごとに切り出し、tesseract で数字を読み取り、
データ（weekly_total.json / weekly_category.json、--month 指定時は monthly_*.json）
の値と比べる。OCRは誤読があるため、食い違ったセルだけを画像に並べた
確認シート（PNG）を出力し、目視で最終確認する。

使い方:
  python3 tools/verify_weekly.py --pdf 店舗A_0929.pdf --store 店舗A \
      --week 2026-09-29 --data-dir data [--month 2026-09] [--out out/]

必要なもの: poppler-utils (pdftoppm), tesseract, Python の Pillow と numpy
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ---- 表のレイアウト（列番号は左から0始まり。罫線の検出結果に対する位置） ----
# 0 カテゴリ名 / 1 適正販売率 / 2-12 当月 / 13-25 前週 / 26-32 AI.CO活用状況
WEEK_COLS = {"sales": 13, "sales_wow": 14, "sales_yoy": 15, "gross_profit": 18, "gp_yoy": 19,
             "discount": 20, "waste": 21, "waste_yoy": 22, "opp_loss": 23,
             "sku_rate": 30, "discount_sku_match": 32}
MONTH_COLS = {"sales": 2, "sales_yoy": 4, "gross_profit": 8, "gp_yoy": 9,
              "discount": 10, "waste": 11, "opp_loss": 12}
CAT_WEEK_FIELDS = ["sales", "sales_yoy", "discount", "gross_profit", "gp_yoy", "waste", "sku_rate", "discount_sku_match"]
TOT_WEEK_FIELDS = ["sales", "sales_wow", "sales_yoy", "discount", "gross_profit", "gp_yoy", "waste", "waste_yoy", "opp_loss", "discount_sku_match"]
CAT_MONTH_FIELDS = ["sales", "sales_yoy", "discount", "gross_profit", "gp_yoy", "waste"]
TOT_MONTH_FIELDS = CAT_MONTH_FIELDS + ["opp_loss"]
FIRST_ROW_Y = 500   # 220dpi で最初のカテゴリ行の上端に近いy座標
N_CATEGORIES = 20   # 表のカテゴリ行数（合計行の直前まで）


def render(pdf, dpi=220):
    tmp = tempfile.mkdtemp()
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-f", "1", "-l", "1", pdf, os.path.join(tmp, "p")], check=True)
    png = [f for f in os.listdir(tmp) if f.endswith(".png")][0]
    im = Image.open(os.path.join(tmp, png)).convert("RGB")
    if im.size[1] > im.size[0]:
        im = im.rotate(-90, expand=True)
    return im


def grid(im):
    a = np.array(im.convert("L")) < 110
    h, w = a.shape
    cs = a[600:1400].sum(0)
    rs = a[:, 150:2450].sum(1)

    def group(v):
        out = []
        for x in v:
            if out and x - out[-1][-1] <= 3:
                out[-1].append(x)
            else:
                out.append([x])
        return [int(sum(t) / len(t)) for t in out]

    return group([x for x in range(w) if cs[x] > 600]), group([y for y in range(h) if rs[y] > 1500])


def cell_img(im, V, H, r, c):
    return im.crop((V[c] + 4, H[r] + 4, V[c + 1] - 3, H[r + 1] - 3))


def ocr(img):
    a = np.array(img).astype(int)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    ink = (np.maximum(np.maximum(R, G), B) < 130) | ((R > 140) & (G < 90) & (B < 90))  # 黒文字＋赤文字
    bw = Image.fromarray(np.where(ink, 0, 255).astype("uint8"))
    bw = bw.resize((bw.width * 3, bw.height * 3), Image.LANCZOS)
    bw = ImageOps.expand(bw, border=30, fill=255)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        bw.save(f.name)
        out = subprocess.run(["tesseract", f.name, "-", "--psm", "7", "-c", "tessedit_char_whitelist=0123456789,.-%"],
                             capture_output=True).stdout.decode("utf-8", "ignore")
    os.unlink(f.name)
    return out.strip().replace(" ", "")


def num(t):
    t = t.replace(",", "").replace("%", "").strip()
    if t in ("", "-"):
        return None
    try:
        return float(t)
    except ValueError:
        return "?" + t


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--store", required=True, help="データの store 列の値（例: 店舗A）")
    ap.add_argument("--week", required=True, help="週の開始日 YYYY-MM-DD（レポートの「前週」欄）")
    ap.add_argument("--month", help="当月欄も照合する場合の月 YYYY-MM（月の最終週のレポート）")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    wt = [r for r in load(os.path.join(args.data_dir, "weekly_total.json")) if r["store"] == args.store and r["week_start"] == args.week]
    wc = [r for r in load(os.path.join(args.data_dir, "weekly_category.json")) if r["store"] == args.store and r["week_start"] == args.week]
    if len(wt) != 1:
        sys.exit(f"weekly_total に {args.store} / {args.week} の行が {len(wt)} 件あります（1件のはず）")
    checks = []  # (label, expected, row, col)
    for f in TOT_WEEK_FIELDS:
        checks.append((f"合計 週 {f}", wt[0].get(f), N_CATEGORIES, WEEK_COLS[f]))

    im = render(args.pdf)
    V, H = grid(im)
    i0 = min(range(len(H)), key=lambda i: abs(H[i] - FIRST_ROW_Y))
    # カテゴリ行はデータの並び順＝レポートの並び順。データにない行（取り扱いなし）は飛ばす。
    for k, r in enumerate(wc):
        for f in CAT_WEEK_FIELDS:
            checks.append((f"{r['category']} 週 {f}", r.get(f), k, WEEK_COLS[f]))
    if args.month:
        mt = [r for r in load(os.path.join(args.data_dir, "monthly_total.json")) if r["store"] == args.store and r["month"] == args.month]
        mc = [r for r in load(os.path.join(args.data_dir, "monthly_category.json")) if r["store"] == args.store and r["month"] == args.month]
        for f in TOT_MONTH_FIELDS:
            checks.append((f"合計 月 {f}", mt[0].get(f) if mt else "なし", N_CATEGORIES, MONTH_COLS[f]))
        for k, r in enumerate(mc):
            for f in CAT_MONTH_FIELDS:
                checks.append((f"{r['category']} 月 {f}", r.get(f), k, MONTH_COLS[f]))

    mism = []
    for label, exp, r, c in checks:
        got = num(ocr(cell_img(im, V, H, i0 + r, c)))
        want = None if exp is None else (float(exp) if isinstance(exp, (int, float)) else exp)
        if got != want and not (got is None and want == 0):  # 1桁の「0」はOCRが読み落としやすい
            mism.append((label, exp, got, r, c))
    print(f"{args.store} {args.week}: {len(checks)}セルを照合、OCRと食い違い {len(mism)}セル")

    os.makedirs(args.out, exist_ok=True)
    if mism:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except OSError:
            font = ImageFont.load_default()
        crops = []
        for label, exp, got, r, c in mism:
            crop = im.crop((V[c], H[i0 + r], V[c + 1], H[i0 + r + 1]))
            crops.append(crop.resize((crop.width * 2, crop.height * 2)))
        sheet = Image.new("RGB", (900, sum(cp.height + 12 for cp in crops)), "white")
        d = ImageDraw.Draw(sheet)
        y = 0
        for n, ((label, exp, got, r, c), crop) in enumerate(zip(mism, crops)):
            sheet.paste(crop, (8, y + 4))
            d.text((crop.width + 24, y + crop.height // 2 - 8), f"#{n} data={exp}", fill="blue", font=font)
            print(f"  #{n} {label}: data={exp} ocr={got}")
            y += crop.height + 12
        path = os.path.join(args.out, f"check_{args.week}_{len(mism)}cells.png")
        sheet.save(path)
        print(f"確認シート: {path}（画像の数字と data= の値を見比べてください）")


if __name__ == "__main__":
    main()
