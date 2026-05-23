import requests
import os
from datetime import datetime
from bs4 import BeautifulSoup
 
# ============================================================
# CONFIGURATION
# ============================================================
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
TO_EMAIL = "dan.mpulice@gmail.com"
FROM_EMAIL = "dan.mpulice@gmail.com"
FROM_NAME = "Property Scraper"
 
EXCLUDE_TYPES = ["vacant lot", "vacant land", "commercial", "industrial", "side lot"]
 
# ============================================================
# SOURCE 1: Detroit Land Bank Authority (DLBA) - Free Open API
# ============================================================
def get_dlba_properties():
    print("Fetching Detroit Land Bank (DLBA) properties...")
    properties = []
    try:
        url = "https://data.detroitmi.gov/resource/9i5p-uyis.json"
        params = {"$limit": 200, "$order": "propaddr ASC"}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
 
        for p in data:
            prop_type = str(p.get("proptype", "")).lower()
            if any(excl in prop_type for excl in EXCLUDE_TYPES):
                continue
 
            address = p.get("propaddr", "N/A")
            city = p.get("propcity", "Detroit")
            state = p.get("propstate", "MI")
            zip_code = p.get("propzip", "")
            sale_type = p.get("salecat", "N/A")
            price = p.get("saleprice", "N/A")
            if price and price != "N/A":
                try:
                    price = f"${float(price):,.0f}"
                except:
                    pass
 
            properties.append({
                "source": "Detroit Land Bank (DLBA)",
                "address": f"{address}, {city}, {state} {zip_code}".strip(", "),
                "type": prop_type.title() if prop_type else "Residential",
                "sale_type": sale_type,
                "price": price,
                "beds": p.get("bedrooms", "N/A"),
                "sqft": p.get("floorarea", "N/A"),
            })
 
        print(f"  DLBA: {len(properties)} properties found")
    except Exception as e:
        print(f"  DLBA Error: {e}")
    return properties
 
 
# ============================================================
# SOURCE 2: Wayne County Foreclosure - Detroit Open Data Portal
# ============================================================
def get_wayne_county_properties():
    print("Fetching Wayne County foreclosure properties...")
    properties = []
    try:
        url = "https://data.detroitmi.gov/resource/dxgi-9s6s.json"
        params = {"$limit": 200}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
 
        for p in data:
            try:
                prop_class_num = int(p.get("property_class", 0))
            except:
                prop_class_num = 0
 
            if prop_class_num and not (401 <= prop_class_num <= 499):
                continue
 
            address = p.get("address", "N/A")
            city = p.get("city", "Detroit")
            zip_code = p.get("zip_code", "")
            assessed = p.get("assessed_value", "N/A")
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
                "sqft": p.get("floor_area", "N/A"),
            })
 
        print(f"  Wayne County: {len(properties)} properties found")
    except Exception as e:
        print(f"  Wayne County Error: {e}")
    return properties
 
 
# ============================================================
# SOURCE 3: Lucas County Sheriff Sales (Toledo)
# ============================================================
def get_lucas_county_properties():
    print("Fetching Lucas County (Toledo) sheriff sale properties...")
    properties = []
    try:
        url = "https://lucas.sheriffsaleauction.ohio.gov/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
 
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.find_all("div", class_="AUCTION_ITEM")
        if not items:
            items = soup.find_all("tr")
 
        for item in items[:100]:
            text = item.get_text(separator=" ", strip=True)
            if not text or len(text) < 20:
                continue
            if any(excl in text.lower() for excl in EXCLUDE_TYPES):
                continue
            if not any(k in text for k in ["OH", "Toledo", "Lucas"]):
                continue
 
            properties.append({
                "source": "Lucas County Sheriff Sale (Toledo)",
                "address": text[:200],
                "type": "Residential",
                "sale_type": "Sheriff Sale",
                "price": "See auction site",
                "beds": "N/A",
                "sqft": "N/A",
            })
 
        print(f"  Lucas County: {len(properties)} properties found")
    except Exception as e:
        print(f"  Lucas County Error: {e}")
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
        Sources: Detroit Land Bank Authority | Wayne County Tax Foreclosure | Lucas County Sheriff Sales<br/>
        Residential only &mdash; vacant land excluded. Scheduled 5:00 AM daily.
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
    all_properties.extend(get_lucas_county_properties())
 
    print(f"\nTotal properties found: {len(all_properties)}")
 
    if all_properties:
        html = build_email(all_properties)
        send_email(html, len(all_properties))
    else:
        print("No properties found — check sources manually.")
 
    print("\nDone.")
 
 
if __name__ == "__main__":
    main()
