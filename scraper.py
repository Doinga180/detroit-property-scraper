import requests
import os
from datetime import datetime, timezone

# ============================================================
# CONFIGURATION
# ============================================================
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
TO_EMAIL = "dan.mpulice@gmail.com"
FROM_EMAIL = "dan.mpulice@gmail.com"
FROM_NAME = "Property Scraper"

EXCLUDE_TYPES = ["vacant lot", "vacant land", "commercial", "industrial", "side lot", "land"]

# Any source that fails gets recorded here so the email shows it,
# instead of quietly reporting "0 properties".
SOURCE_ERRORS = []


def arcgis_query(url, params):
    """Query an ArcGIS feed. ArcGIS sends back errors as a normal-looking
    reply, so check for that and raise instead of returning nothing."""
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        err = data["error"]
        raise RuntimeError(f"ArcGIS error {err.get('code')}: {err.get('message')}")
    if "features" not in data:
        raise RuntimeError("ArcGIS reply had no 'features' list")
    return data["features"]


def format_date(value):
    """ArcGIS dates come back as milliseconds since 1970; turn into MM/DD/YYYY."""
    if value in (None, ""):
        return "N/A"
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).strftime("%m/%d/%Y")
    except (ValueError, TypeError, OSError):
        return str(value)


# ============================================================
# SOURCE 1: Detroit Land Bank Authority (DLBA)
# City of Detroit Open Data: "DLBA Properties For Sale" (updated daily)
# https://data.detroitmi.gov/datasets/dlba-properties-for-sale
# ============================================================
def get_dlba_properties():
    print("Fetching Detroit Land Bank (DLBA) properties...")
    properties = []
    try:
        url = "https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/DLBA_For_Sale/FeatureServer/0/query"
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "resultRecordCount": 2000,
            "f": "json",
        }
        features = arcgis_query(url, params)

        # The feed sometimes lists the same house twice; keep the newest listing.
        by_parcel = {}
        for feature in features:
            p = feature.get("attributes", {})
            key = str(p.get("parcel_id") or p.get("address") or "").strip()
            if not key:
                continue
            existing = by_parcel.get(key)
            if existing is None or (p.get("listing_date") or 0) > (existing.get("listing_date") or 0):
                by_parcel[key] = p

        for p in by_parcel.values():
            address = (p.get("address") or "N/A").strip()
            neighborhood = (p.get("neighborhood") or "").strip()
            program = (p.get("program") or "For Sale").strip()
            listed = format_date(p.get("listing_date"))

            properties.append({
                "source": "Detroit Land Bank (DLBA)",
                "address": f"{address}, Detroit, MI" + (f" ({neighborhood})" if neighborhood else ""),
                "type": "Residential",
                "sale_type": f"{program} - listed {listed}",
                "price": "See buildingdetroit.org",
                "beds": "N/A",
                "sqft": "N/A",
            })

        print(f"  DLBA: {len(features)} rows, {len(properties)} unique properties")
    except Exception as e:
        print(f"  DLBA Error: {e}")
        SOURCE_ERRORS.append(f"Detroit Land Bank: {e}")
    return properties


# ============================================================
# SOURCE 2: Wayne County Foreclosure
# NOTE: this address has not been verified yet - next to fix.
# ============================================================
def get_wayne_county_properties():
    print("Fetching Wayne County foreclosure properties...")
    properties = []
    try:
        url = "https://services2.arcgis.com/HsXtOCMp1Nis1Ogr/arcgis/rest/services/Foreclosure_2026/FeatureServer/0/query"
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "resultRecordCount": 200,
            "f": "json",
        }
        features = arcgis_query(url, params)

        for feature in features:
            p = feature.get("attributes", {})
            address = p.get("Address", "") or p.get("ADDRESS", "") or "N/A"
            city = p.get("City", "") or p.get("CITY", "") or "Detroit"
            assessed = p.get("AssessedValue", "") or p.get("ASSESSED_VALUE", "") or "N/A"
            if assessed and assessed != "N/A":
                try:
                    assessed = f"${float(assessed):,.0f}"
                except (ValueError, TypeError):
                    pass

            properties.append({
                "source": "Wayne County Tax Foreclosure",
                "address": f"{address}, {city}, MI",
                "type": "Residential",
                "sale_type": "Tax Foreclosure Auction",
                "price": f"Assessed: {assessed}",
                "beds": "N/A",
                "sqft": p.get("FloorArea", "N/A") or "N/A",
            })

        print(f"  Wayne County: {len(properties)} properties found")
    except Exception as e:
        print(f"  Wayne County Error: {e}")
        SOURCE_ERRORS.append(f"Wayne County: {e}")
    return properties


# ============================================================
# SOURCE 3: HUD Homes - Detroit & Toledo
# NOTE: HUD rebuilt its site; this page-reading code is out of date - to fix.
# ============================================================
def get_hud_properties():
    print("Fetching HUD foreclosure properties (Detroit + Toledo)...")
    properties = []
    try:
        for city, state in [("Detroit", "MI"), ("Toledo", "OH")]:
            url = "https://www.hudhomestore.gov/Listing/PropertySearchResult.aspx"
            params = {
                "sState": state,
                "sCity": city,
                "srProp": "SFR",
                "iListingsPerPage": 50,
                "iCurrentPage": 1,
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code != 200:
                raise RuntimeError(f"{city}: HUD site returned status {response.status_code}")

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            listings = soup.find_all("div", class_="property-listing") or \
                       soup.find_all("tr", class_="propRow") or \
                       soup.find_all("li", class_="listing")
            if not listings:
                raise RuntimeError(f"{city}: page loaded but no listings recognized (site layout changed)")

            for item in listings[:25]:
                text = item.get_text(separator=" ", strip=True)
                if not text or len(text) < 10:
                    continue
                if any(excl in text.lower() for excl in EXCLUDE_TYPES):
                    continue
                properties.append({
                    "source": f"HUD Homes ({city}, {state})",
                    "address": text[:150],
                    "type": "Single Family Residential",
                    "sale_type": "HUD Foreclosure",
                    "price": "See HUD listing",
                    "beds": "N/A",
                    "sqft": "N/A",
                })

        print(f"  HUD: {len(properties)} properties found")
    except Exception as e:
        print(f"  HUD Error: {e}")
        SOURCE_ERRORS.append(f"HUD: {e}")
    return properties


# ============================================================
# BUILD EMAIL
# ============================================================
def build_email(all_properties):
    today = datetime.now().strftime("%B %d, %Y")
    total = len(all_properties)

    by_source = {}
    for p in all_properties:
        by_source.setdefault(p["source"], []).append(p)

    html = f"""
    <html><body style="font-family: Arial, sans-serif; color: #222;">
    <h2 style="color:#1a73e8;">&#127968; Daily Property Report &mdash; {today}</h2>
    <p><strong>Total Residential Properties Found: {total}</strong></p>
    """

    if SOURCE_ERRORS:
        html += "<div style='background:#fdecea; border:1px solid #d93025; padding:10px; margin:10px 0;'>"
        html += "<strong style='color:#d93025;'>&#9888; Sources that did NOT work today:</strong><ul>"
        for err in SOURCE_ERRORS:
            html += f"<li>{err}</li>"
        html += "</ul></div>"

    html += "<hr/>"

    for source, props in by_source.items():
        html += f"<h3 style='color:#333;'>{source} ({len(props)} properties)</h3>"
        html += "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse; width:100%;'>"
        html += "<tr style='background:#1a73e8; color:white;'><th>Address</th><th>Type</th><th>Sale Type</th><th>Price/Value</th><th>Beds</th><th>Sqft</th></tr>"
        for i, p in enumerate(props):
            bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
            html += f"""<tr style='background:{bg};'>
                <td>{p['address']}</td>
                <td>{p['type']}</td>
                <td>{p['sale_type']}</td>
                <td>{p['price']}</td>
                <td>{p['beds']}</td>
                <td>{p['sqft']}</td>
            </tr>"""
        html += "</table><br/>"

    html += """
    <hr/>
    <p style='font-size:12px; color:#888;'>
        Sources: Detroit Land Bank Authority (City of Detroit Open Data) | Wayne County Tax Foreclosure | HUD Homes Detroit + Toledo<br/>
        Scheduled 2:02 AM Eastern daily.
    </p>
    </body></html>
    """
    return html


# ============================================================
# SEND EMAIL VIA BREVO
# ============================================================
def send_email(html_body, total_count):
    print("Sending email via Brevo...")
    today = datetime.now().strftime("%B %d, %Y")
    flag = f" ({len(SOURCE_ERRORS)} source errors)" if SOURCE_ERRORS else ""
    subject = f"Property Report {today} — {total_count} Listings{flag}"

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json",
    }
    payload = {
        "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
        "to": [{"email": TO_EMAIL, "name": "Dan Pulice"}],
        "subject": subject,
        "htmlContent": html_body,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code in [200, 201, 202]:
        print(f"  Email sent successfully to {TO_EMAIL}")
    else:
        print(f"  Email failed: {response.status_code} — {response.text}")


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print(f"Property Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_properties = []
    all_properties.extend(get_dlba_properties())
    all_properties.extend(get_wayne_county_properties())
    all_properties.extend(get_hud_properties())

    print(f"\nTotal properties found: {len(all_properties)}")
    if SOURCE_ERRORS:
        print("Sources with errors:")
        for err in SOURCE_ERRORS:
            print(f"  - {err}")

    send_email(build_email(all_properties), len(all_properties))
    print("\nDone.")


if __name__ == "__main__":
    main()
