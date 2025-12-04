import re
from pathlib import Path

import pandas as pd
import pdfplumber

# ----- paths -----
BASE_DIR = Path(__file__).resolve().parent
RAW = BASE_DIR / "data_raw"            # where your PDFs live
OUT_DIR = BASE_DIR / "data_processed"  # where we'll write the CSV
OUT_DIR.mkdir(exist_ok=True)


# ----- helpers -----

def to_float_price(x):
    if x is None:
        return None
    s = str(x).strip()
    s = s.replace("$", "").replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def extract_mg(text):
    """
    Try to pull '10mg' etc out of spec/product string.
    """
    if not text:
        return None
    s = str(text).lower().replace(" ", "")
    m = re.search(r"(\d+(?:\.\d+)?)(mg)", s)
    if not m:
        return None
    return float(m.group(1))


def extract_vials(text):
    """
    Try to pull '10 vials' from strings like '10mg/vial x 10vials'.
    Default later is 10 if we can't see it.
    """
    if not text:
        return None
    s = str(text).lower().replace(" ", "")
    m = re.search(r"(\d+)vials", s)
    if m:
        return int(m.group(1))
    m = re.search(r"x(\d+)vials", s)
    if m:
        return int(m.group(1))
    return None


def standardize_row(vendor, product_name, spec, price_str, source_file):
    price = to_float_price(price_str)
    dose_mg_per_vial = extract_mg(spec) or extract_mg(product_name)
    vials_per_kit = extract_vials(spec) or 10  # most vendors use 10-vial kits
    total_mg = dose_mg_per_vial * vials_per_kit if dose_mg_per_vial else None
    ppm = price / total_mg if (price is not None and total_mg) else None

    return {
        "vendor": vendor,
        "product_name": product_name.strip() if product_name else "",
        "spec_raw": spec.strip() if spec else "",
        "price_usd": price,
        "dose_mg_per_vial": dose_mg_per_vial,
        "vials_per_kit": vials_per_kit,
        "total_mg_per_kit": total_mg,
        "price_per_mg": ppm,
        "source_file": source_file,
    }


# ----- vendor parsers -----

def parse_hyb():
    """
    HYB-Price List - Overview.pdf
    Tables with header row: Code | Name | Specification | 1kit | 10kits | ...
    We use 1kit price.
    """
    path = RAW / "HYB-Price List - Overview.pdf"
    rows = []

    if not path.exists():
        return rows

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                if not table:
                    continue

                # find header row where first cell == "Code"
                header_idx = None
                for idx, row in enumerate(table):
                    if row and str(row[0]).strip() == "Code":
                        header_idx = idx
                        break
                if header_idx is None:
                    continue

                for r in table[header_idx + 1:]:
                    if not r or not r[0]:
                        continue
                    # expect: [code, name, spec, 1kit, 10kits, ...]
                    name = r[1] if len(r) > 1 else ""
                    spec = r[2] if len(r) > 2 else ""
                    price_1kit = r[3] if len(r) > 3 else None
                    rows.append(
                        standardize_row(
                            "HYB", str(name), str(spec), str(price_1kit), path.name
                        )
                    )
    return rows


def parse_cn_full():
    """
    CN-price list.pdf – multiple pages.
    Page 0 has header row; later pages are plain rows like:
    [code, name, spec, price].
    """
    path = RAW / "HXTNT-Lucy-price list.pdf"
    rows = []

    if not path.exists():
        return rows

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                if not table:
                    continue

                # detect header row on first page
                first = table[0]
                has_header = first and "Cat. No." in str(first[0])
                start_idx = 1 if has_header else 0

                current_name = None
                for r in table[start_idx:]:
                    if not r or not r[0]:
                        continue
                    # r[0] = code
                    if len(r) > 1 and r[1]:
                        current_name = r[1]
                    name = current_name
                    spec = r[2] if len(r) > 2 else ""
                    price = r[3] if len(r) > 3 else None

                    if not name or not price:
                        continue

                    rows.append(
                        standardize_row(
                            "HXTNT", str(name), str(spec), str(price), path.name
                        )
                    )
    return rows


def parse_violet_single():
    """
    list.pdf – single-page CN list with header row:
    [Cat. No., Product, 规格, price, ...]
    """
    path = RAW / "violet-list.pdf"
    rows = []

    if not path.exists():
        return rows

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                if not table:
                    continue

                first = table[0]
                has_header = first and "Cat. No." in str(first[0])
                start_idx = 1 if has_header else 0

                current_name = None
                for r in table[start_idx:]:
                    if not r or not r[0]:
                        continue
                    if len(r) > 1 and r[1]:
                        current_name = r[1]
                    name = current_name
                    spec = r[2] if len(r) > 2 else ""
                    price = r[3] if len(r) > 3 else None

                    if not name or not price:
                        continue

                    rows.append(
                        standardize_row(
                            "Violet", str(name), str(spec), str(price), path.name
                        )
                    )
    return rows


def parse_zj():
    """
    ZJ Latest Price List 11.24.pdf
    Header row: SKU | Products Name | Mg*vials | 1 box | ...
    We use '1 box' price.
    """
    path = RAW / "ZJlist123.pdf"
    rows = []

    if not path.exists():
        return rows

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                if not table:
                    continue

                header_idx = None
                for idx, row in enumerate(table):
                    if row and "SKU" in str(row[0]):
                        header_idx = idx
                        break
                start_idx = header_idx + 1 if header_idx is not None else 0

                current_name = None
                for r in table[start_idx:]:
                    if not r or not r[0]:
                        continue

                    if len(r) > 1 and r[1]:
                        current_name = r[1]
                    name = current_name
                    spec = r[2] if len(r) > 2 else ""
                    price = r[3] if len(r) > 3 else None

                    if not name or not price:
                        continue

                    rows.append(
                        standardize_row(
                            "ZJ", str(name), str(spec), str(price), path.name
                        )
                    )
    return rows


def parse_mix():
    """
    Mix_price-list (3).pdf – simple text like:
    Tirze-30mg 90
    Reta-15mg 120
    """
    path = RAW / "Mix_price-list (3).pdf"
    rows = []

    if not path.exists():
        return rows

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    for line in text.splitlines():
        line = line.strip()
        if (
            not line
            or "MIX-Peptides" in line
            or "Ship  from US Warehouse" in line
            or "Products/kit" in line
            or "ham@mix-peptides" in line
        ):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        name = parts[0]
        price = parts[-1]

        rows.append(
            standardize_row("Mix", name, name, price, path.name)
        )

    return rows


def parse_uther():
    """
    Uther_11-26.pdf
    Peptide tables with rows like:
    [Semaglutide 5mg, 95, 85, 75, 70]
    We'll take the first price column as 1-box price.
    """
    path = RAW / "Uther_11-26.pdf"
    rows = []

    if not path.exists():
        return rows

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                if not table or not table[0]:
                    continue

                first_cell = str(table[0][0]).lower()

                # skip contact/shipping/cosmetic sections
                if any(
                    kw in first_cell
                    for kw in ["contact us", "about shipping", "weight", "cosmetic powder"]
                ):
                    continue

                for r in table:
                    if not r or not r[0]:
                        continue
                    name = r[0]
                    price = r[1] if len(r) > 1 else None
                    if not price or not to_float_price(price):
                        continue

                    rows.append(
                        standardize_row(
                            "Uther", str(name), str(name), str(price), path.name
                        )
                    )
    return rows


def parse_jeep_csv():
    """
    Jeep uses an image; we read a hand-made CSV instead.

    Expected columns in data_raw/jeep_manual.csv:
      vendor,product_name,dose_text,price_usd,package_text
    """
    path = RAW / "jeep_manual.csv"
    rows = []

    if not path.exists():
        return rows

    df = pd.read_csv(path)

    for _, r in df.iterrows():
        vendor = r.get("vendor", "Jeep")
        name = r.get("product_name", "")
        dose = r.get("dose_text", "")
        pkg = r.get("package_text", "")
        price = r.get("price_usd", "")
        spec = f"{dose} {pkg}"
        rows.append(
            standardize_row(
                vendor, str(name), str(spec), str(price), path.name
            )
        )

    return rows


# ----- main -----

def main():
    all_rows = []
    all_rows += parse_hyb()
    all_rows += parse_cn_full()
    all_rows += parse_violet_single()
    all_rows += parse_zj()
    all_rows += parse_mix()
    all_rows += parse_uther()
    all_rows += parse_jeep_csv()

    df = pd.DataFrame(all_rows)

    # simple normalized key for grouping/filtering
    df["peptide_key"] = (
        df["product_name"]
        .str.upper()
        .str.replace(r"[^A-Z0-9\-]+", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    out_path = OUT_DIR / "peptide_prices_master.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()
