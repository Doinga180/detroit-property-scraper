import json
import pandas as pd
from datetime import datetime
import io
import requests
import smtplib
import os
from email.mime.text import MIMEText

# ============================================================
# DETROIT PROPERTY SCRAPER - Version 5
# Downloads PropStream export from GitHub and generates report
# ============================================================

TARGET_ZIPS = [
    "48207", "48219", "48221", "48224", "48205",
    "48215", "48223", "48235", "48217", "48225"
]

TARGET_TYPES = ["duplex", "multi-family", "two family", "2 units", "flat", "2+"]

# Direct download URL from GitHub
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Doinga180/detroit-property-scraper/main/Property%20Export%20All%2BSaved%2BProperties.xlsx"

def read_propstream_export():
    print("Downloading PropStream export from GitHub...")
    response = requests.get(GITHUB_RAW_URL)
    if response.status_code != 200:
        print(f"ERROR: Could not download file. Status code: {response.status_code}")
        return None
    print(f"Downloaded {len(response.content)} bytes")
    df = pd.read_excel(io.BytesIO(response.content))
    df['Zip'] = df['Zip'].astype(str).str.strip()
    df = df[df['Zip'].isin(TARGET_ZIPS)]
    print(f"Properties in your ZIP codes: {len(df)}")
    return df

def generate_report(df):
    report = []
    report.append("=" * 60)
    report.append("DETROIT PROPERTY MORNING REPORT")
    report.append(f"Generated: {datetime.now().strftime('%m, %d %Y, at %I:%M %p')}")
    report.append("=" * 60)
    report.append("")
    mf_mask = df['Property Type'].str.lower().str.contains("|".join(TARGET_TYPES), na=False)
    mf = df[mf_mask]
    other = df[~mf_mask]
    report.append(f"TOTAL PROPERTIES: {len(df)}")
    report.append(f"MULTI-FAMILY / DUPLEX: {len(mf)}")
    report.append(f"OTHER TYPES: {len(other)}")
    report.append("")
    report.append("=" * 60)
    report.append("MULTI-FAMILY & DUPLEX — YOUR PRIMARY TARGETS")
    report.append("=" * 60)
    report.append("")
    if len(mf) > 0:
        for i, (_, row) in enumerate(mf.iterrows(), 1):
            addr = f"{row['Address']}, {row['City']}, {row['State']} {row['Zip']}"
            report.append(f"#{i} — {addr}")
            report.append(f"    Type: {row['Property Type']}")
            report.append(f"    Beds: {row['Bedrooms']} | Baths: {row['Total Bathrooms']} | Sqft: {row['Building Sqft']}")
            est_val = row.get('Est. Value', 'N/A')
            assessed = row.get('Total Assessed Value', 'N/A')
            report.append(f"    Est. Value: ${est_val:,.0f}" if pd.notna(est_val) and est_val != 'N/A' else "    Est. Value: N/A")
            report.append(f"    Assessed Value: ${assessed:,.0f}" if pd.notna(assessed) and assessed != 'N/A' else "    Assessed Value: N/A")
            report.append(f"    Last Sale: {row['Last Sale Recording Date']}")
            report.append(f"    Owner Occupied: {row['Owner Occupied']}")
            report.append(f"    Foreclosure Factor: {row.get('Foreclosure Factor', 'N/A')}")
            report.append("")
    else:
        report.append("No multi-family properties found.")
        report.append("")
    report.append("=" * 60)
    report.append("OTHER PROPERTIES — FIX & FLIP CANDIDATES")
    report.append("=" * 60)
    report.append("")
    for i, (_, row) in enumerate(other.head(20).iterrows(), 1):
        addr = f"{row['Address']}, {row['City']}, {row['State']} {row['Zip']}"
        report.append(f"#{i} — {addr}")
        report.append(f"    Type: {row['Property Type']}")
        report.append(f"    Beds: {row['Bedrooms']} | Sqft: {row['Building Sqft']}")
        est_val = row.get('Est. Value', 'N/A')
        report.append(f"    Est. Value: ${est_val:,.0f}" if pd.notna(est_val) and est_val != 'N/A' else "    Est. Value: N/A")
        report.append("")
    report.append("=" * 60)
    report.append("Next scheduled run: 2:00 AM daily")
    report.append("=" * 60)
    return "\n".join(report)

def run_scraper():
    df = read_propstream_export()
    if df is None:
        return
    report = generate_report(df)
    print(report)
    report_file = f"morning_report_{datetime.now().strftime('%Y-%m-%d')}.txt"
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"\nSaved to: {report_file}")
    try:
        msg = MIMEText(report)
        msg['Subject'] = f"Detroit Property Report - {datetime.now().strftime('%Y-%m-%d')}"
        msg['From'] = "dan.mpulice@gmail.com"
        msg['To'] = "dan.mpulice@gmail.com"
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login("dan.mpulice@gmail.com", os.environ['GMAIL_APP_PASSWORD'])
            server.send_message(msg)
            print("Report emailed successfully.")
    except Exception as e:
        print(f"Email failed: {e}")

if __name__ == "__main__":
    run_scraper()
