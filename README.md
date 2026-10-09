# AI.CO 週次検証

AI.COカテゴリの週次レポート（お店づくりレポート②）と月次検証レポートを、店舗ごと・週ごとに積み上げて比較するための仕組みです。

ダッシュボード本体は claude.ai のアーティファクトとして運用しています。このリポジトリには、ダッシュボードのページ、データの形式、PDFとデータを照合するツールを置いています。

> **このリポジトリは公開されています。** 店舗の売上・荒利などの数字、元のPDF、店舗ごとの所見は入れないでください。`data/` と `*.pdf` は `.gitignore` で除外しています。

## 構成

| パス | 内容 |
|---|---|
| `dashboard/index.html` | ダッシュボードのページ（4タブ：5店舗サマリー／店舗別／月次／見方と所見）。数字はすべてデータから読み込みます |
| `tools/verify_weekly.py` | PDFの表をセル単位でOCRし、データの値と照合するツール |
| `data/` | 実データの置き場（コミットしない） |

## 毎週の更新手順

1. 各店の「お店づくりレポート②」（PDF）を集める。
2. レポートの「前週」欄から、店舗×週の合計行を `weekly_total.json`、カテゴリ行を `weekly_category.json` に追加する。
3. 月の最終週のレポート（当月欄が月末まで）からは、`monthly_total.json` と `monthly_category.json` に当月の行を追加する。
4. `tools/verify_weekly.py` で、追加した行をPDFと照合する。食い違いが出たセルは確認シートの画像で見比べ、データの誤りなら直す。
5. ダッシュボードのデータファイルを差し替える。グラフ・表・要約文は自動で更新される。

月次検証レポートが届いたら、下部グラフの前年比を `monthly_trend.json` に追加します。

## データ形式

金額はレポートの表記どおり（1店1日あたり＝PSADと見られる値）。前年比などの率は「%」を除いた数値（95% → `95`）で持ちます。

### weekly_total.json（店舗×週）

| 列 | 内容 | レポートの欄 |
|---|---|---|
| `key` | `店舗コード_週開始日`（行を一意に決める） | |
| `store` / `store_name` | 店舗の略称／正式名 | |
| `week_start` / `week_end` | 週の開始日・終了日（YYYY-MM-DD） | 前週(m/d〜m/d) |
| `sales` / `sales_yoy` / `sales_wow` | 販売高・販売高前年比・前週比 | 販売高 |
| `discount` | 値引高 | 値引高 |
| `gross_profit` / `gp_yoy` | 荒利高・荒利高前年比 | 荒利高 |
| `waste` / `waste_yoy` | 廃棄高・廃棄高前年比 | 廃棄高 |
| `opp_loss` | 機会ロス高 | 機会ロス高 |
| `discount_sku_match` | 値引SKU一致率 | ※3 値引SKU一致率 |

### weekly_category.json（店舗×週×カテゴリ）

`key`（`店舗コード_週開始日_カテゴリ`）、`store`、`week_start`、`category`、`sales`、`sales_yoy`、`discount`、`gross_profit`、`gp_yoy`、`waste`、`sku_rate`（採用SKU数／推奨SKU数）、`discount_sku_match`。取り扱いのないカテゴリは行を作りません。

### monthly_total.json / monthly_category.json（当月欄）

週次と同じ列を `month`（YYYY-MM）単位で持ちます。前週比・採用SKU率・値引SKU一致率はありません。

### monthly_trend.json（月次検証レポートのグラフ）

`key`、`store`（比較店は `比較店（支店平均）`）、`month`、`gp_yoy`、`sales_yoy`。

## 指標の定義（ダッシュボードで計算）

- 荒利率 = 荒利益高 ÷ 販売高
- ロス率 = （値引高 ＋ 廃棄高）÷ 販売高
- 値引率 = 値引高 ÷ 販売高
- 5店合計 = 各店の値の合計。前週比・前週差は合計どうしで計算

前年比が100%未満の数字は赤で表示します。廃棄前年比は少ないほど良い数字のため色を付けません。

## 照合ツール

```
python3 tools/verify_weekly.py --pdf 店舗A_0929.pdf --store 店舗A \
    --week 2026-09-29 --month 2026-09 --data-dir data --out out
```

- 必要なもの：`pdftoppm`（poppler-utils）、`tesseract`、Python の Pillow と numpy
- 表の罫線を検出してセルを切り出し、数字をOCRで読み、データと比べます。
- OCRは誤読（5と9、1と7など）があるため、食い違ったセルだけを並べた確認シート（PNG）を出力します。画像の数字と `data=` の値を目で見比べて最終確認してください。
- カテゴリ行はデータの並び順をレポートの並び順として照合します。並び順を変えないでください。
