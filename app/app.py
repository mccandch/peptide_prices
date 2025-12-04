import pandas as pd
import streamlit as st
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data_processed" / "peptide_prices_master.csv"


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    return df


def main():
    st.set_page_config(page_title="Peptide Price Comparator", layout="wide")
    st.title("Peptide Price Comparator")

    # ---------- Top-of-page help: how vendor CSVs should look ----------
    with st.expander("How should the vendor CSV look?", expanded=False):

        st.markdown(
            """
    To add a new vendor, upload a **CSV** with at least these columns:

    - `vendor` – short vendor code (e.g. `CN`, `ZJ`)
    - `product_name` – peptide name as listed by the vendor
    - `spec_raw` – vendor spec (e.g. `5mg*10vials`)
    - `price_usd` – total price in USD for the kit
    - `dose_mg_per_vial` – mg per vial (numeric)
    - `vials_per_kit` – number of vials per kit (numeric)
    - `total_mg_per_kit` – total mg in the kit (numeric)
    - `price_per_mg` – price in USD per mg (numeric)

    `source_file` and any other columns are **optional** and will be ignored by the app.
    """
        )

        example_text = """
    vendor,product_name,spec_raw,price_usd,dose_mg_per_vial,vials_per_kit,total_mg_per_kit,price_per_mg
    CN,BPC 157,5mg*10vials,41,5,10,50,0.82
    ZJ,AOD-9604,10mg*10vials,40,10,10,100,0.40
    """.strip()

        st.markdown("**Example CSV format:**")
        st.code(example_text, language="csv")


    # ---------- load base data ----------
    df = load_data()

    if df.empty:
        st.warning("No data found. Run prepare_data.py first.")
        return

    # ---------- optional: add extra vendor CSVs at runtime ----------
    st.sidebar.subheader("Add vendor data")

    uploaded_files = st.sidebar.file_uploader(
        "Upload additional vendor CSV(s)",
        type=["csv"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        # columns required for the app logic
        required_cols = [
            "vendor",
            "product_name",
            "spec_raw",
            "price_usd",
            "dose_mg_per_vial",
            "vials_per_kit",
            "total_mg_per_kit",
            "price_per_mg",
        ]

        base_cols = list(df.columns)

        for f in uploaded_files:
            try:
                extra = pd.read_csv(f)

                missing = set(required_cols) - set(extra.columns)
                if missing:
                    st.sidebar.error(
                        f"{f.name}: missing required columns {missing}. File was not added."
                    )
                    continue

                # ensure all current df columns exist in extra; fill missing with NaN
                for col in base_cols:
                    if col not in extra.columns:
                        extra[col] = pd.NA

                # reorder columns to match base df
                extra = extra[base_cols]

                # append
                df = pd.concat([df, extra], ignore_index=True)
                st.sidebar.success(f"Added {len(extra)} rows from {f.name}")
            except Exception as e:
                st.sidebar.error(f"Error reading {f.name}: {e}")

    # ---------- build canonical peptide name ----------
    df["canonical_peptide"] = (
        df["product_name"]
        .str.upper()
        .str.replace(r"\b\d+(\.\d+)?\s*(MG|MCG|UG|IU)\b", "", regex=True)
        # keep digits in names (ARA-290, SNAP-8, BPC 157, etc.)
        .str.replace(r"[-_]", " ", regex=True)
        .str.replace(r"[^\w]+", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # Base alias normalization: RETA/TIRZE/SEMA → full names
    cp = df["canonical_peptide"].fillna("")
    df.loc[cp.str.startswith("RETA"), "canonical_peptide"] = "RETATRUTIDE"
    df.loc[cp.str.startswith("TIRZE"), "canonical_peptide"] = "TIRZEPATIDE"
    df.loc[cp.str.startswith("SEMA"), "canonical_peptide"] = "SEMAGLUTIDE"

    # =======================
    # Alias Normalization Block
    # =======================
    cp = df["canonical_peptide"].str.upper().fillna("")

    # --- SS-31 ---
    df.loc[cp.str.match(r"^SS 31$"), "canonical_peptide"] = "SS-31"

    # --- ARA-290 / SNAP-8 / BPC 157 prettification ---
    df.loc[cp.str.startswith("ARA 290"), "canonical_peptide"] = "ARA-290"
    df.loc[cp.str.startswith("SNAP 8"), "canonical_peptide"] = "SNAP-8"
    df.loc[cp.str.startswith("BPC 157"), "canonical_peptide"] = "BPC 157"

    # --- BAC / BACTERIOSTATIC WATER ---
    df.loc[cp.str.contains("BAC WATER"), "canonical_peptide"] = "BACTERIOSTATIC WATER"
    df.loc[cp.str.contains("BACTERIOSTATIC"), "canonical_peptide"] = "BACTERIOSTATIC WATER"

    # --- BPC TB → BPC TB BLEND ---
    df.loc[cp.str.startswith("BPC TB"), "canonical_peptide"] = "BPC TB BLEND"
    # TB10MG BPC 157 and similar blends
    df.loc[(cp.str.contains("TB")) & (cp.str.contains("BPC")), "canonical_peptide"] = "BPC TB BLEND"

    # --- CAGR → CAGRILINTIDE ---
    df.loc[cp.str.startswith("CAGR"), "canonical_peptide"] = "CAGRILINTIDE"

    # --- EPITALON / EPITHALON ---
    df.loc[cp.str.contains("EPITHALON"), "canonical_peptide"] = "EPITHALON"
    df.loc[cp.str.contains("EPITALON"), "canonical_peptide"] = "EPITHALON"

    # --- GLUTATHIONE variants ---
    df.loc[cp.str.startswith("GLUTATHIONE"), "canonical_peptide"] = "GLUTATHIONE"

    # --- MAZDUTIDE / misspellings ---
    df.loc[cp.str.contains("MAZDU"), "canonical_peptide"] = "MAZDUTIDE"

    # --- MOTS C / MOTSC ---
    df.loc[cp.str.replace(" ", "", regex=False) == "MOTSC", "canonical_peptide"] = "MOTS C"

    # --- CJC NO DAC variations ---
    df.loc[cp.str.contains("CJC") & cp.str.contains("NO DAC"), "canonical_peptide"] = "CJC NO DAC"
    df.loc[cp.str.contains("CJC") & cp.str.contains("WITHOUT DAC"), "canonical_peptide"] = "CJC NO DAC"
    df.loc[cp.str.contains("CJC") & cp.str.contains("WHITOUT DAC"), "canonical_peptide"] = "CJC NO DAC"

    # --- CJC IPA variations ---
    df.loc[cp.str.contains("CJC") & cp.str.contains("IPA"), "canonical_peptide"] = "CJC NO DAC IPA"

    # --- MELANOTAN I variants ---
    df.loc[cp.str.contains("MELANOTAN 1"), "canonical_peptide"] = "MELANOTAN I"
    df.loc[cp.str.contains("MELANOTAN I"), "canonical_peptide"] = "MELANOTAN I"
    df.loc[cp.str.match(r"^MELANOTAN$"), "canonical_peptide"] = "MELANOTAN I"
    df.loc[cp.str.match(r"^MT 1$"), "canonical_peptide"] = "MELANOTAN I"

    # --- KLOW blends ---
    df.loc[cp.str.startswith("KLOW"), "canonical_peptide"] = "KLOW"
    df.loc[cp.str.contains("KLOW TB BP KP GHK"), "canonical_peptide"] = "KLOW"
    df.loc[cp.str.contains("BPC GHK CU TB KPV"), "canonical_peptide"] = "KLOW"

    # --- GLOW and blends ---
    df.loc[cp.str.startswith("GLOW"), "canonical_peptide"] = "GLOW"
    df.loc[cp.str.contains("GLOW TB BP GHK"), "canonical_peptide"] = "GLOW"
    df.loc[cp.str.contains("GLOW TBMG"), "canonical_peptide"] = "GLOW"
    glow_bpc_mask = cp.str.contains("BPC GHK CU TB") & ~cp.str.contains("KPV")
    df.loc[glow_bpc_mask, "canonical_peptide"] = "GLOW"

    # --- HCG / HUMAN CHORIONIC GONADOTROPIN ---
    df.loc[cp == "HCG", "canonical_peptide"] = "HUMAN CHORIONIC GONADOTROPIN"
    df.loc[cp.str.contains("CHORIONIC"), "canonical_peptide"] = "HUMAN CHORIONIC GONADOTROPIN"

    # --- PEG-MGF variations → PEG MGF ---
    df.loc[
        cp.str.replace(" ", "", regex=False).str.contains("PEGMGF"),
        "canonical_peptide",
    ] = "PEG MGF"

    # --- AOD / AOD-9604 ---
    df.loc[cp.str.startswith("AOD"), "canonical_peptide"] = "AOD-9604"

    # --- FOXO4 / FOXO4-DRI ---
    df.loc[cp.str.startswith("FOXO4"), "canonical_peptide"] = "FOXO4-DRI"

    # --- IGF-1 LR3 variations ---
    df.loc[cp.str.contains("IGF"), "canonical_peptide"] = "IGF-1 LR3"

    # --- KISSPEPTIN / KISSPEPTIN-10 ---
    df.loc[cp.str.startswith("KISSPEPTIN"), "canonical_peptide"] = "KISSPEPTIN-10"

    # --- L-CARNITINE variations ---
    df.loc[cp.str.startswith("L CARNITINE"), "canonical_peptide"] = "L-CARNITINE"

    # --- LL-37 variations ---
    df.loc[cp.str.match(r"^LL ?37$"), "canonical_peptide"] = "LL-37"

    # --- PT-141 variations ---
    df.loc[cp.str.match(r"^PT ?141$"), "canonical_peptide"] = "PT-141"

    # ---------- normalize total mg per kit ----------
    # Business rule: kit is always 10 vials, so total_mg_per_kit = 10 * dose_mg_per_vial
    mask = df["dose_mg_per_vial"].notna()
    df.loc[mask, "total_mg_per_kit"] = df.loc[mask, "dose_mg_per_vial"] * 10

    # ---------- sidebar filters ----------
    st.sidebar.header("Filters")

    peptide_options = sorted(df["canonical_peptide"].unique())
    selected_peptides = st.sidebar.multiselect(
        "Peptides",
        peptide_options,
        default=[],  # none selected by default
    )

    vendors = sorted(df["vendor"].unique())
    selected_vendors = st.sidebar.multiselect(
        "Vendors",
        vendors,
        default=vendors,
    )

    only_with_ppm = st.sidebar.checkbox("Only show rows with price-per-mg", value=False)

    # ---------- apply filters ----------
    filt = df.copy()
    if selected_peptides:
        filt = filt[filt["canonical_peptide"].isin(selected_peptides)]
    if selected_vendors:
        filt = filt[filt["vendor"].isin(selected_vendors)]
    if only_with_ppm:
        filt = filt[filt["price_per_mg"].notna()]

    if filt.empty:
        st.warning("No rows match the current filters.")
        return

    # ---------- base grouped data ----------
    agg_cols = {
        "price_usd": "min",
        "price_per_mg": "min",
    }
    group_cols = ["canonical_peptide", "dose_mg_per_vial", "total_mg_per_kit", "vendor"]

    grouped = (
        filt[group_cols + ["price_usd", "price_per_mg"]]
        .dropna(subset=["dose_mg_per_vial"])
        .groupby(group_cols, as_index=False)
        .agg(agg_cols)
    )

    # ---------- pivot with numeric values ----------
    pivot = grouped.pivot_table(
        index=["canonical_peptide", "dose_mg_per_vial", "total_mg_per_kit"],
        columns="vendor",
        values=["price_usd", "price_per_mg"],
        aggfunc="min",
    )

    pivot = pivot.sort_index().reset_index()

    # flatten MultiIndex columns: ('price_usd','CN') -> 'CN_price_usd'
    def flatten_col(col):
        if isinstance(col, tuple):
            level0, level1 = col
            if not level1:
                return level0
            return f"{level1}_{level0}"
        return col

    pivot.columns = [flatten_col(c) for c in pivot.columns]

    vendor_names = sorted(filt["vendor"].unique())

    # ---------- compute rank of price_per_mg per row ----------
    ppm_col_map = {}
    for vendor in vendor_names:
        col_ppm = f"{vendor}_price_per_mg"
        if col_ppm in pivot.columns:
            ppm_col_map[vendor] = col_ppm

    ppm_cols = list(ppm_col_map.values())

    if ppm_cols:
        ppm_numeric = pivot[ppm_cols]
        ranks = ppm_numeric.rank(axis=1, method="min", ascending=True)
        best_mask = ranks.eq(1)
        second_mask = ranks.eq(2)
    else:
        best_mask = pd.DataFrame(False, index=pivot.index, columns=vendor_names)
        second_mask = pd.DataFrame(False, index=pivot.index, columns=vendor_names)

    # ---------- build display table with vendor strings ----------
    display = pivot[["canonical_peptide", "dose_mg_per_vial", "total_mg_per_kit"]].copy()

    for vendor in vendor_names:
        col_price = f"{vendor}_price_usd"
        col_ppm = f"{vendor}_price_per_mg"

        if col_price not in pivot.columns:
            continue

        prices = pivot[col_price]
        ppms = pivot[col_ppm] if col_ppm in pivot.columns else pd.Series([None] * len(pivot))

        vendor_best = best_mask[ppm_col_map[vendor]] if vendor in ppm_col_map else pd.Series(
            False, index=pivot.index
        )
        vendor_second = second_mask[ppm_col_map[vendor]] if vendor in ppm_col_map else pd.Series(
            False, index=pivot.index
        )

        cells = []
        for price, ppm, is_best, is_second in zip(prices, ppms, vendor_best, vendor_second):
            if pd.isna(price):
                cells.append("")
                continue

            marker = ""
            if is_best:
                marker = "🟩 "
            elif is_second:
                marker = "🟨 "

            price_str = f"${price:,.2f}"
            if pd.notna(ppm):
                ppm_str = f"${ppm:.2f} per mg"
                cell = f"{marker}{price_str} / {ppm_str}"
            else:
                cell = f"{marker}{price_str}"

            cells.append(cell)

        display[vendor] = cells

    # Rename for display
    display = display.rename(
        columns={
            "canonical_peptide": "Peptide",
            "dose_mg_per_vial": "Dose (mg/vial)",
            "total_mg_per_kit": "Total mg/kit",
        }
    )

    # ---------- persistent selection using session_state ----------
    # Create a stable row key: Peptide|Dose|TotalMg
    display["row_key"] = display.apply(
        lambda r: f"{r['Peptide']}|{r['Dose (mg/vial)']}|{r['Total mg/kit']}",
        axis=1,
    )

    # Initialize stored selection if needed
    if "selected_row_keys" not in st.session_state:
        st.session_state["selected_row_keys"] = []

    prev_keys_set = set(st.session_state["selected_row_keys"])

    # Pre-populate Include based on stored keys
    display["Include"] = display["row_key"].isin(prev_keys_set)

    # Put Include as first column, then move row_key to index (hidden)
    cols = ["Include", "Peptide", "Dose (mg/vial)", "Total mg/kit", "row_key"] + vendor_names
    display = display[cols].set_index("row_key")

    st.subheader("Peptide doses by vendor (check rows to include in price list)")
    st.caption("🟩 = lowest price per mg,  🟨 = second-lowest price per mg.")

    edited = st.data_editor(
        display,
        num_rows="fixed",
        key="pivot_with_checks",
        column_config={
            "Include": st.column_config.CheckboxColumn(
                "Include",
                help="Check to include this peptide+dose in the price list",
                default=False,
            )
        },
        hide_index=True,  # hides the row_key index
    )

    # ---------- update stored selection ----------
    visible_keys = set(edited.index)  # index is row_key
    checked_keys = set(edited.index[edited["Include"]])

    # Keep previously selected rows that are currently not visible
    prev_outside_view = prev_keys_set - visible_keys

    new_keys_set = prev_outside_view | checked_keys
    st.session_state["selected_row_keys"] = list(new_keys_set)

    # Decode selected_keys as (Peptide, Dose, Total mg) for Phase 2
    selected_keys = []
    for key in st.session_state["selected_row_keys"]:
        pep, dose_str, total_str = key.split("|")
        try:
            dose_val = float(dose_str)
        except ValueError:
            dose_val = None
        try:
            total_val = float(total_str)
        except ValueError:
            total_val = None
        selected_keys.append((pep, dose_val, total_val))

    # ---------- Phase 2: pivoted price list by vendor for selected rows ----------
    st.subheader("Price list by vendor for selected peptides")

    if not selected_keys:
        st.info("Select one or more rows above to see the price list.")
    else:
        sel_df = pd.DataFrame(
            selected_keys,
            columns=["Peptide", "Dose (mg/vial)", "Total mg/kit"],
        )

        merged = sel_df.merge(
            grouped,
            left_on=["Peptide", "Dose (mg/vial)", "Total mg/kit"],
            right_on=["canonical_peptide", "dose_mg_per_vial", "total_mg_per_kit"],
            how="left",
        )

        price_pivot = merged.pivot_table(
            index=["Peptide", "Dose (mg/vial)"],
            columns="vendor",
            values="price_usd",
            aggfunc="min",
        )

        has_any = price_pivot.notna().any(axis=0)
        price_pivot = price_pivot.loc[:, has_any]

        if price_pivot.empty:
            st.info("No prices available for the selected peptides.")
        else:
            vendor_totals = price_pivot.sum(axis=0, skipna=True)

            ordered_vendors = vendor_totals.sort_values().index.tolist()
            price_pivot = price_pivot[ordered_vendors]

            display_prices = price_pivot.reset_index()

            total_row = {"Peptide": "TOTAL", "Dose (mg/vial)": ""}
            for v in ordered_vendors:
                total_row[v] = vendor_totals[v]
            display_prices = pd.concat(
                [display_prices, pd.DataFrame([total_row])],
                ignore_index=True,
            )

            for v in ordered_vendors:
                display_prices[v] = display_prices[v].apply(
                    lambda x: f"${x:,.2f}" if pd.notna(x) else ""
                )

            st.table(display_prices)


if __name__ == "__main__":
    main()
