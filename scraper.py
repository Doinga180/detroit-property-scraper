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
 
EXCLUDE_TYPES = ["vacant lot", "vacant land", "commercial", "industrial", "side lot", "land"]
 
# ============================================================
# SOURCE 1: Detroit Land Bank Authority (DLBA)
# Using verified ArcGIS REST API
# ============================================================
def get_dlba_properties():
    print("Fetching Detroit Land Bank (DLBA) properties...")
    properties = []
    try:
        # Verified ArcGIS FeatureServer endpoint for DLBA For Sale
        url = "https://services2.arcgis.com/HsXtOCMp1Nis1Ogr/arcgis/rest/services/DLBA_ForSale/FeatureServer/0/query"
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "resultRecordCount": 200,
            "f": "json"
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
 
        features = data.get("features", [])
        for feature in features:
            p = feature.get("attributes", {})
            prop_type = str(p.get("PropType", "") or p.get("PROPTYPE", "") or "").lower()
            
            if any(excl in prop_type for excl in EXCLUDE_TYPES):
                continue
 
            address = p.get("PropAddr", "") or p.get("PROPADDR", "") or p.get("Address", "") or "N/A"
            sale_type = p.get("SaleCat", "") or p.get("SALECAT", "") or "For Sale"
            price = p.get("SalePrice", "") or p.get("SALEPRICE", "") or "N/A"
            if price and price != "N/A":
                try:
                    price = f"${float(price):,.0f}"
                except:
                    pass
 
            properties.append({
                "source": "Detroit Land Bank (DLBA)",
                "address": f"{address}, Detroit, MI",
                "type": prop_type.title() if prop_type else "Residential",
                "sale_type": sale_type,
                "price": price,
                "beds": p.get("Bedrooms", "N/A") or p.get("BEDROOMS", "N/A"),
                "sqft": p.get("FloorArea", "N/A") or p.get("FLOORAREA", "N/A"),
            })
 
        print(f"  DLBA: {len(properties)} properties found")
    except Exception as e:
        print(f"  DLBA Error: {e}")
    return properties
 
 
# ============================================================
# SOURCE 2: Wayne County Foreclosure
# Using buildingdetroit.org public listing
# ============================================================
def get_wayne_county_properties():
    print("Fetching Wayne County foreclosure properties...")
    properties = []
    try:
        # Wayne County public foreclosure listing via Detroit open data
        url = "https://services2.arcgis.com/HsXtOCMp1Nis1Ogr/arcgis/rest/services/Foreclosure_2026/FeatureServer/0/query"
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "resultRecordCount": 200,
            "f": "json"
        }
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
 
        features = data.get("features", [])
        for feature in features:
            p = feature.get("attributes", {})
            address = p.get("Address", "") or p.get("ADDRESS", "") or "N/A"
            city = p.get("City", "") or p.get("CITY", "") or "Detroit"
            assessed = p.get("AssessedValue", "") or p.get("ASSESSED_VALUE", "") or "N/A"
            if assessed and assessed != "N/A":
                try:
                    assessed = f"${float(assessed):,.0f}"
                except:
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
    return properties
 
 
# ============================================================
# SOURCE 3: HUD Homes - Detroit & Toledo
# HUD uses a public API - no bot blocking
# ============================================================
def get_hud_properties():
    print("Fetching HUD foreclosure properties (Detroit + Toledo)...")
    properties = []
    try:
        # HUD homestore public API
        for city, state in [("Detroit", "MI"), ("Toledo", "OH")]:
            url = f"https://www.hudhomestore.gov/Listing/PropertySearchResult.aspx"
            params = {
                "sState": state,
                "sCity": city,
                "srProp": "SFR",  # Single Family Residential
                "iListingsPerPage": 50,
                "iCurrentPage": 1,
            }
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                listings = soup.find_all("div", class_="property-listing") or \
                           soup.find_all("tr", class_="propRow") or \
                           soup.find_all("li", class_="listing")
 
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
    <p><strong>Total Residential Properties Found: {total}</strong></p>
    <hr/>
    """
 
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
        Sources: Detroit Land Bank Authority | Wayne County Tax Foreclosure | HUD Homes Detroit + Toledo<br/>
        Residential only &mdash; vacant land excluded. Scheduled 2:00 AM daily.
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
 
    if all_properties:
        html = build_email(all_properties)
        send_email(html, len(all_properties))
    else:
        send_email("<p>No properties found today. Sources may be temporarily unavailable.</p>", 0)
 
    print("\nDone.")
 
 
if __name__ == "__main__":
    main()
