"""Build Mei-Juni 2026 forensic workbook from transcribed user data.

Source of truth: output/mei_juni_source.json (transcription of the user's
message; source order preserved exactly, including the 01/05 time inversion).
Only the STRUCTURE/format of output/BRI_Forensic_Transaction_Analysis.xlsx
is reused via src.bri_parser — its Jul-Sep transactions are never touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.bri_parser import (
    build_sheets,
    classify_fees,
    link_interest_tax,
    parse_transactions,
    write_workbook,
)

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "output" / "mei_juni_source.json"
OUT = ROOT / "output" / "BRI_Forensic_Transaction_Analysis_Mei-Juni_2026.xlsx"

UNKNOWN_TXN_NOTE = (
    "Transaksi Tidak Diketahui: saldo aktual Rp100.000 lebih tinggi dari hasil "
    "hitung berurutan — indikasi transaksi masuk yang tidak tercatat sebelum "
    "baris ini (angka sumber tidak diubah)"
)
ORDER_NOTE = (
    "Anomali urutan waktu: 01/05/26 19:26:49 tercantum sebelum 19:25:49; "
    "urutan sumber dipertahankan, saldo konsisten mengikuti urutan sumber"
)


def main() -> None:
    rows = json.loads(SRC.read_text(encoding="utf-8"))
    df = pd.DataFrame(
        rows,
        columns=[
            "tanggal_transaksi",
            "waktu",
            "uraian_transaksi",
            "teller",
            "debet",
            "kredit",
            "saldo",
        ],
    )
    # Teller/User ID stays text so leading zeros survive.
    df["teller"] = df["teller"].astype(str)

    parsed = parse_transactions(df)
    parsed = classify_fees(parsed)
    parsed = link_interest_tax(parsed)
    sheets = build_sheets(parsed)

    daftar = sheets["Daftar Transaksi"]
    mask = daftar["Transaction ID"] == "TXN0005"
    assert int(mask.sum()) == 1, "TXN0005 not found"
    daftar.loc[mask, "Catatan Parser"] = (
        daftar.loc[mask, "Catatan Parser"].astype(str) + "; " + UNKNOWN_TXN_NOTE
    )
    for txn in ("TXN0001", "TXN0002"):
        m = daftar["Transaction ID"] == txn
        daftar.loc[m, "Catatan Parser"] = (
            daftar.loc[m, "Catatan Parser"].astype(str) + "; " + ORDER_NOTE
        )

    ringkas = sheets["Ringkasan"]
    ringkas.loc[ringkas["Keterangan"] == "Sumber data", "Nilai"] = (
        "Pesan pengguna — transaksi Mei-Juni 2026 "
        "(ditranskripsi; urutan sumber dipertahankan)"
    )
    extra = [
        (
            "Transaksi Tidak Diketahui",
            "Selisih Mei -Rp100.000 berasal dari gap +Rp100.000 pada TXN0005 "
            "(03/05/26 20:37:14): saldo aktual 75.173.563 vs hasil hitung "
            "75.073.563 — indikasi transaksi masuk yang tidak tercatat; "
            "angka sumber tidak diubah",
        ),
        (
            "Anomali urutan waktu 01/05/26",
            "19:26:49 tercantum sebelum 19:25:49; urutan sumber dipertahankan, "
            "saldo tetap konsisten mengikuti urutan sumber",
        ),
        (
            "Saldo awal Mei (turunan)",
            "81582563 — dihitung dari baris pertama (saldo + debet - kredit), "
            "tidak terkonfirmasi independen",
        ),
        (
            "Keterkaitan Mei-Juni",
            "Saldo akhir Mei (76544173) = saldo awal Juni (76544173) — konsisten",
        ),
    ]
    sheets["Ringkasan"] = pd.concat(
        [ringkas, pd.DataFrame(extra, columns=["Keterangan", "Nilai"])],
        ignore_index=True,
    )

    sheets["Anomali & Selisih"] = pd.DataFrame(
        [
            [
                "1",
                "TXN0005 — 03/05/26 20:37:14",
                "Saldo Seharusnya 75.073.563 vs Saldo Aktual 75.173.563 "
                "(selisih +Rp100.000)",
                "Rekap Mei: selisih -Rp100.000, status TIDAK COCOK",
                "Transaksi Tidak Diketahui — kemungkinan transaksi masuk "
                "Rp100.000 yang tidak tercatat antara baris 4 dan 5; "
                "angka dipertahankan",
            ],
            [
                "2",
                "TXN0001–TXN0002 — 01/05/26",
                "19:26:49 tercantum sebelum 19:25:49",
                "Urutan tidak kronologis; saldo tetap cocok mengikuti "
                "urutan sumber",
                "Anomali urutan waktu — urutan sumber dipertahankan, "
                "tidak diurutkan ulang",
            ],
            [
                "3",
                "Saldo awal Mei — 81.582.563 (turunan)",
                "Dihitung dari baris pertama (saldo + debet - kredit)",
                "Dasar perhitungan saldo seharusnya baris pertama",
                "Nilai turunan, bukan saldo terkonfirmasi dari sumber independen",
            ],
        ],
        columns=["No", "Lokasi", "Detail", "Dampak", "Keterangan"],
    )

    write_workbook(sheets, OUT)
    print("written:", OUT)


if __name__ == "__main__":
    main()
