from pathlib import Path

p = Path("src/bri_parser.py")
s = p.read_text(encoding="utf-8")
marker = "# --------------------------------------------------------------------------\n# Reporting sheets"
idx = s.index(marker)

replacement = r'''# --------------------------------------------------------------------------
# Reporting sheets
# --------------------------------------------------------------------------
BANK_INTERNAL_PATTERNS = {"INTEREST", "TAX", "ADMIN_FEE", "MONTHLY_FEE_ATM"}

def _running_balance(parsed: pd.DataFrame) -> pd.DataFrame:
    """Attach opening balance, expected balance, difference and match flag.

    The expected balance of a row equals the previous actual balance minus the
    debit plus the credit.  For the very first row the previous balance is the
    derived opening balance, so the first row is validated too (not only the
    adjacent rows).
    """
    out = parsed.copy()
    debet = out["debet"].fillna(0).astype("int64") if "debet" in out.columns else 0
    kredit = out["kredit"].fillna(0).astype("int64") if "kredit" in out.columns else 0
    saldo = out["saldo"].astype("int64") if "saldo" in out.columns else pd.Series([], dtype="int64")

    opening = None
    expected = []
    prev = None
    for i in out.index:
        d = int(debet.loc[i]) if hasattr(debet, "loc") else int(debet)
        k = int(kredit.loc[i]) if hasattr(kredit, "loc") else int(kredit)
        sv = int(saldo.loc[i]) if hasattr(saldo, "loc") else int(saldo)
        if prev is None:
            opening = sv + d - k
        exp = opening if prev is None else prev - d + k
        expected.append(exp)
        prev = sv
    out["opening_balance"] = opening
    out["expected_saldo"] = expected
    out["saldo_difference"] = out["saldo"].astype("int64") - pd.Series(expected, index=out.index)
    out["reconciliation_status"] = out["saldo_difference"].apply(lambda x: "MATCH" if x == 0 else "MISMATCH")
    return out


def _payee_identity(row: pd.Series) -> tuple[str, str]:
    """Return (destination_type, payee_label) without fabricating identities."""
    acct = str(row.get("destination_account_candidate", UNKNOWN))
    if acct and acct != UNKNOWN and not pd.isna(acct):
        name = row.get("destination_name", UNKNOWN)
        label = f"{name} ({acct})" if name and name != UNKNOWN else acct
        return "Account Transfer", label
    merchant = str(row.get("merchant_name", UNKNOWN))
    if merchant and merchant != UNKNOWN:
        return "Merchant", merchant
    wallet = str(row.get("wallet_name", UNKNOWN))
    if wallet and wallet != UNKNOWN:
        return "E-Wallet", wallet
    cp = str(row.get("counterparty_name", UNKNOWN))
    if cp and cp != UNKNOWN:
        return "Counterparty", cp
    pattern = row.get("transaction_pattern", UNKNOWN)
    if pattern == "TARIK_TUNAI":
        return "Cash Withdrawal", "ATM (TARIK TUNAI)"
    if pattern in {"PRCH", "PRTT", "NP"}:
        ref = row.get("transaction_reference", UNKNOWN)
        suffix = f" [{ref}]" if ref and ref != UNKNOWN else ""
        return "Merchant", f"Merchant not stated in description ({pattern}){suffix}"
    if pattern in BANK_INTERNAL_PATTERNS:
        return "Bank System", str(pattern)
    return "Other", str(pattern)


def build_sheets(parsed: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build the single-workbook tabs: list, summary, balance control, destination."""
    sheets: dict[str, pd.DataFrame] = {}
    parsed = _running_balance(parsed)

    # ---- Tab 1: full transaction list (source order) -----------------------
    tx = parsed.copy()
    tx["_payee"] = tx.apply(_payee_identity, axis=1)
    tx["destination_type"] = [t for t, _ in tx["_payee"]]
    tx["destination_label"] = [l for _, l in tx["_payee"]]

    def _amount(v):
        try:
            return int(v) if not pd.isna(v) else 0
        except (TypeError, ValueError):
            return 0

    list_rows = []
    for i, r in tx.iterrows():
        list_rows.append({
            "No": len(list_rows) + 1,
            "Transaction ID": r.get("transaction_id", ""),
            "Date": r.get("datetime"),
            "Tanggal": r.get("tanggal_transaksi", ""),
            "Waktu": r.get("waktu", ""),
            "Uraian Transaksi": r.get("raw_description", ""),
            "Jenis Transaksi": r.get("transaction_type", UNKNOWN),
            "Kategori": r.get("transaction_pattern", UNKNOWN),
            "Arah": "DEBIT (keluar)" if r.get("transaction_direction") == "OUT"
                    else "KREDIT (masuk)" if r.get("transaction_direction") == "IN" else UNKNOWN,
            "Debit": _amount(r.get("debet")),
            "Credit": _amount(r.get("kredit")),
            "Saldo": _amount(r.get("saldo")),
            "Saldo Seharusnya": _amount(r.get("expected_saldo")),
            "Selisih": _amount(r.get("saldo_difference")),
            "Status Rekonsiliasi": r.get("reconciliation_status", UNKNOWN),
            "Teller": r.get("teller", ""),
            "Tujuan/ Merchant": r.get("destination_label", UNKNOWN),
            "Tipe Tujuan": r.get("destination_type", UNKNOWN),
            "Rekening Tujuan": r.get("destination_account_candidate", UNKNOWN),
            "Nama Tujuan": r.get("destination_name", UNKNOWN),
            "Bank Tujuan": r.get("destination_bank", UNKNOWN),
            "Referensi": r.get("transaction_reference", UNKNOWN),
            "ESB Reference": r.get("esb_reference", UNKNOWN),
            "Biaya (Fee)": _amount(r.get("fee_amount")),
            "Klasifikasi Fee": r.get("fee_classification", UNKNOWN),
            "Transaksi Induk": r.get("parent_transaction_id", ""),
            "Tingkat Keyakinan": r.get("parser_confidence", UNKNOWN),
            "Perlu Review Manual": bool(r.get("manual_review_required", False)),
            "Catatan Parser": r.get("parser_notes", ""),
        })
    tx_sheet = pd.DataFrame(list_rows)
    sheets["Daftar Transaksi"] = tx_sheet

    # ---- Tab 2: Ringkasan ---------------------------------------------------
    total_debit = int(tx["debet"].fillna(0).sum())
    total_kredit = int(tx["kredit"].fillna(0).sum())
    opening = int(tx["opening_balance"].iloc[0]) if len(tx) else 0
    closing = int(tx["saldo"].iloc[-1]) if len(tx) else 0
    mismatches = int((tx["reconciliation_status"] != "MATCH").sum())
    dmin = tx["datetime"].min()
    dmax = tx["datetime"].max()
    summary_rows = [
        ("Sumber data", "manual.txt (satu-satunya sumber)"),
        ("Periode", f"{dmin} — {dmax}"),
        ("Jumlah transaksi", len(tx)),
        ("Total Debit", total_debit),
        ("Total Kredit", total_kredit),
        ("Saldo Awal", opening),
        ("Saldo Akhir", closing),
        ("Selisih (Awal - Debit + Kredit - Akhir)", opening - total_debit + total_kredit - closing),
        ("Jumlah baris selisih != 0", mismatches),
        ("Status rekonsiliasi", "COCOK (0 selisih)" if mismatches == 0 else f"TIDAK COCOK ({mismatches} baris)"),
        ("Jumlah transaksi fee teridentifikasi", int(tx["is_fee_transaction"].sum())),
        ("Jumlah transaksi perlu review manual", int(tx["manual_review_required"].sum())),
    ]
    sheets["Ringkasan"] = pd.DataFrame(summary_rows, columns=["Keterangan", "Nilai"])

    # ---- Tab 3: Kontrol Saldo (per baris + batas bulan) ---------------------
    ctrl = tx[["transaction_id", "datetime", "raw_description", "debet", "kredit",
               "opening_balance", "expected_saldo", "saldo", "saldo_difference",
               "reconciliation_status"]].copy()
    ctrl = ctrl.rename(columns={
        "transaction_id": "Transaction ID", "datetime": "Date", "raw_description": "Uraian Transaksi",
        "debet": "Debit", "kredit": "Credit", "opening_balance": "Saldo Awal",
        "expected_saldo": "Saldo Seharusnya", "saldo": "Saldo Aktual",
        "saldo_difference": "Selisih", "reconciliation_status": "Status",
    })
    sheets["Kontrol Saldo"] = ctrl

    # ---- Tab 4: Rekap Bulanan ----------------------------------------------
    tx["_month"] = pd.to_datetime(tx["datetime"]).dt.strftime("%Y-%m")
    monthly_rows = []
    for month, g in tx.groupby("_month", sort=True):
        month_open = int(g["opening_balance"].iloc[0])
        month_debit = int(g["debet"].fillna(0).sum())
        month_credit = int(g["kredit"].fillna(0).sum())
        month_close = int(g["saldo"].iloc[-1])
        monthly_rows.append({
            "Bulan": month,
            "Jumlah Transaksi": len(g),
            "Saldo Awal": month_open,
            "Total Debit": month_debit,
            "Total Kredit": month_credit,
            "Saldo Akhir": month_close,
            "Selisih": month_open - month_debit + month_credit - month_close,
            "Status": "COCOK" if month_open - month_debit + month_credit - month_close == 0 else "TIDAK COCOK",
        })
    sheets["Rekap Bulanan"] = pd.DataFrame(monthly_rows)

    # ---- Tab 5: Destination Summary (transfer + merchant + e-wallet) -------
    dest = tx[(~tx["is_fee_transaction"]) & (~tx["transaction_pattern"].isin(BANK_INTERNAL_PATTERNS))].copy()
    dest = dest[dest["transaction_direction"] == "OUT"]
    rows = []
    for (dtype, label), g in dest.groupby(["destination_type", "destination_label"], sort=False):
        fees = tx[(tx["parent_transaction_id"].isin(g["transaction_id"])) & (tx["is_fee_transaction"])]
        verified = bool(g["destination_account_verified"].any()) if "destination_account_verified" in g else False
        rows.append({
            "Tipe Tujuan": dtype,
            "Tujuan / Merchant": label,
            "Rekening Tujuan": g["destination_account_candidate"].iloc[0],
            "Bank": g["destination_bank"].iloc[0],
            "Status Verifikasi": "VERIFIED" if verified else "UNVERIFIED",
            "Jumlah Transaksi": int(len(g)),
            "Total Nominal": int(g["debet"].fillna(0).sum()),
            "Rata-rata": int(round(g["debet"].fillna(0).mean())) if len(g) else 0,
            "Transaksi Terbesar": int(g["debet"].fillna(0).max()) if len(g) else 0,
            "Transaksi Pertama": str(g["tanggal_transaksi"].iloc[0]),
            "Transaksi Terakhir": str(g["tanggal_transaksi"].iloc[-1]),
            "Total Fee Terkait": int(fees["fee_amount"].fillna(0).sum()) if len(fees) else 0,
            "Referensi": "; ".join(str(x) for x in g["esb_reference"].tolist() if str(x) not in ("", UNKNOWN)),
        })
    dest_cols = ["Tipe Tujuan", "Tujuan / Merchant", "Rekening Tujuan", "Bank", "Status Verifikasi",
                 "Jumlah Transaksi", "Total Nominal", "Rata-rata", "Transaksi Terbesar",
                 "Transaksi Pertama", "Transaksi Terakhir", "Total Fee Terkait", "Referensi"]
    sheets["Destination Summary"] = pd.DataFrame(rows, columns=dest_cols) if rows else pd.DataFrame(columns=dest_cols)

    # ---- Tab 6: Ringkasan Jenis Transaksi ----------------------------------
    total = len(tx)
    rows = []
    for pat in PATTERN_PRIORITY:
        g = tx[tx["transaction_pattern"] == pat]
        if g.empty:
            continue
        rows.append({
            "Jenis Transaksi": pat,
            "Tipe": PATTERN_REGISTRY[pat]["type"],
            "Kanal": PATTERN_REGISTRY[pat]["channel"],
            "Jumlah": int(len(g)),
            "Total Debit": int(g["debet"].fillna(0).sum()),
            "Total Kredit": int(g["kredit"].fillna(0).sum()),
            "Persentase Transaksi": len(g) / total if total else 0,
        })
    sheets["Ringkasan Jenis Transaksi"] = pd.DataFrame(rows)

    return sheets

'''

new_text = s[:idx] + replacement
p.write_text(new_text, encoding="utf-8")
print("replaced build_sheets section, len", len(new_text))
