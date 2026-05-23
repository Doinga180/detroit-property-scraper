import requests
import os
from datetime import datetime
 
# ============================================================
# CONFIGURATION
# ============================================================
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
TO_EMAIL = "dan.mpulice@gmail.com"
FROM_EMAIL = "dan.mpulice@gmail.com"
FROM_NAME = "Property Scraper"
 
EXCLUDE_TYPES = ["vacant lot", "vacant land", "side lot", "commercial", "industrial"]
 
# ============================================================
# SOURCE 1: Detroit Land Bank Authority (DLBA)
# Uses ArcGIS FeatureServer - correct endpoint
# ============================================================
def get_dlba_properties():
    print("Fetching Detroit Land Bank (DLBA) properties...")
    properties = []
    try:
        # Correct ArcGIS REST API endpoint for DLBA For Sale
        url = "https://services2.arcgis.com/qvkbeam8tagHnykx/arcgis/rest/services/dlba_for_sale/FeatureServer/0/query"
        params = {
            "where": "1=1",
            "outFields": "*",
            "f": "json",
            "resultRecordCount": 200
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
 
        features = data.get("features", [])
        for feat in features:
            p = feat.get("attributes", {})
            prop_type = str(p.get("proptype", "") or p.get("type", "") or "").lower()
            if any(excl in prop_type for excl in EXCLUDE_TYPES):
                continue
 
            address = p.get("propaddr") or p.get("address") or "N/A"
            city = p.get("propcity") or "Detroit"
            zip_code = p.get("propzip") or ""
            sale_type = p.get("salecat") or p.get("program") or "N/A"
            price = p.get("saleprice") or p.get("price") or "N/A"
            if price and price != "N/A":
                try:
                    price = f"${float(price):,.0f}"
                except:
                    pass
 
            properties.append({
                "source": "Detroit Land Bank (DLBA)",
                "address": f"{address}, {city}, MI {zip_code}".strip(", "),
                "type": prop_type.title() if prop_type else "Residential",
                "sale_type": sale_type,
                "price": price,
                "beds": p.get("bedrooms") or "N/A",
                "sqft": p.get("floorarea") or p.get("sqft") or "N/A",
            })
 
        print(f"  DLBA: {len(properties)} properties found")
    except Exception as e:
        print(f"  DLBA Error: {e}")
    return properties
 
 
# ============================================================
# SOURCE 2: Wayne County Foreclosure via Detroit Open Data
# ============================================================
def get_wayne_county_properties():
    print("Fetching Wayne County foreclosure properties...")
    properties = []
    try:
        # Wayne County tax foreclosure - correct Socrata API endpoint
        url = "https://data.detroitmi.gov/resource/muhn-gvgm.json"
        params = {"$limit": 200, "$where": "status='Active'"}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
 
        for p in data:
            prop_type = str(p.get("property_class", "")).lower()
            if any(excl in prop_type for excl in EXCLUDE_TYPES):
                continue
 
            address = p.get("address") or p.get("propaddress") or "N/A"
            city = p.get("city") or "Detroit"
            zip_code = p.get("zip_code") or p.get("zip") or ""
            assessed = p.get("assessed_value") or p.get("value") or "N/A"
            if assessed and assessed != "N/A":
                try:
                    assessed = f"${float(assessed):,.0f}"
                except:
                    pass
 
            properties.append({
                "source": "Wayne County Tax Foreclosure",
                "address": f"{address}, {city}, MI {zip_code}".strip(", "),
                "type": "Residential",
                "sale_type": "Tax Foreclosure Auction",
                "price": f"Assessed: {assessed}",
                "beds": "N/A",
                "sqft": p.get("floor_area") or "N/A",
            })
 
        print(f"  Wayne County: {len(properties)} properties found")
    except Exception as e:
        print(f"  Wayne County Error: {e}")
    return properties
 
 
# ============================================================
# SOURCE 3: HUD Homes - Free government API
# Replaces Lucas County which blocks scrapers
# ============================================================
def get_hud_properties():
    print("Fetching HUD foreclosure properties (Detroit + Toledo area)...")
    properties = []
    try:
        # HUD HomeStore API - public government data
        # Michigan state code = 26, Ohio = 39
        for state, label in [("MI", "Detroit Area"), ("OH", "Toledo Area")]:
            url = "https://www.hudhomestore.gov/Home/Index.aspx"
            # Use the HUD public listing API
            api_url = f"https://www.hudhomestore.gov/Listing/ListingSearch.aspx"
            params = {
                "state": state,
                "listingType": "A",  # Active listings
                "beds": "1",
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(
                f"https://www.hudhomestore.gov/Home/PropertyListing.aspx?stateCode={state}",
                headers=headers,
                timeout=30
            )
 
            if response.status_code == 200 and len(response.text) > 500:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                listings = soup.find_all("div", class_="propRow") or \
                           soup.find_all("tr", class_="propRow") or []
 
                for item in listings[:25]:
                    text = item.get_text(separator=" ", strip=True)
                    if text and len(text) > 20:
                        properties.append({
                            "source": f"HUD Foreclosure ({label})",
                            "address": text[:200],
                            "type": "HUD Foreclosure",
                            "sale_type": "HUD Home Sale",
                            "price": "See HUD listing",
                            "beds": "N/A",
                            "sqft": "N/A",
                        })
 
        print(f"  HUD: {len(properties)} properties found")
    except Exception as e:
        print(f"  HUD Error: {e}")
    return properties
 
 
# ============================================================
# BUILD EMAIL
# ============================================================
def build_email(all_properties):
    today = datetime.now().strftime("%B %d, %Y")
    total = len(all_properties)
 
    by_source = {}
    for p in all_properties:
        src = p["source"]
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(p)
 
    html = f"""
    <html><body style="font-family: Arial, sans-serif; color: #222;">
    <h2 style="color:#1a73e8;">&#127968; Daily Property Report &mdash; {today}</h2>
    <p><strong>Total Properties Found: {total}</strong></p>
    <p>Residential only &mdash; vacant land excluded.</p>
    <hr/>
    """
 
    if not all_properties:
        html += "<p>No properties found today. Sources may be temporarily unavailable.</p>"
    else:
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
        Sources: Detroit Land Bank Authority | Wayne County Tax Foreclosure | HUD Foreclosures<br/>
        Scheduled 2:00 AM daily.
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
    subject = f"Property Report {today} — {total_count} Listings (Detroit + Toledo)"
 
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    payload = {
        "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
        "to": [{"email": TO_EMAIL, "name": "Dan Pulice"}],
        "subject": subject,
        "htmlContent": html_body
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
 
    html = build_email(all_properties)
    send_email(html, len(all_properties))
 
    print("\nDone.")
 
 
if __name__ == "__main__":
    main()
