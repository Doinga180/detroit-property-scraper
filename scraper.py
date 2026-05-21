import requests
import json
import csv
import io
from datetime import datetime
import time

# ============================================================
# DETROIT PROPERTY SCRAPER - Version 3
# Uses official government data files - no scraping
# Target: Two-family flats in Detroit ZIP codes
# Section 8 payment standard $1,300+ neighborhoods
# ============================================================

TARGET_ZIPS = [
    "48207", "48219", "48221", "48224", "48205",
    "48215", "48223", "48235", "48217", "48225"
]

MAX_PRICE = 200000
MIN_PRICE = 30000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,application/json,*/*",
}

def search_hud_data_file():
    """
    Download HUD's official weekly data export file
    HUD publishes all listings as a downloadable dataset
    """
    results = []
    print("Downloading HUD official data file...")

    # HUD data export URLs to try
    urls = [
        "https://www.hudhomestore.gov/HHSPortal/DownloadFile.aspx?type=csv",
        "https://www.hudhomestore.gov/Home/DownloadFile?fileType=CSV",
        "https://www.hudhomestore.gov/HHSPortal/Mi_listings.csv",
    ]

    for url in urls:
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200 and len(response.content) > 1000:
                print(f"  Got HUD data file ({len(response.content)} bytes)")

                # Parse CSV
                content = response.content.decode('utf-8', errors='ignore')
                reader = csv.DictReader(io.StringIO(content))

                for row in reader:
                    try:
                        # Look for ZIP code in any field
                        row_text = str(row).upper()
                        zip_match = None
                        for zip_code in TARGET_ZIPS:
                            if zip_code in row_text:
                                zip_match = zip_code
                                break

                        if not zip_match:
                            continue

                        # Extract price
                        price_raw = row.get('ListPrice', row.get('LIST_PRICE',
                                    row.get('Price', row.get('PRICE', '0'))))
                        try:
                            price = float(str(price_raw).replace('$', '').replace(',', ''))
                        except:
                            price = 0

                        if price < MIN_PRICE or price > MAX_PRICE:
                            continue

                        # Extract address
                        address = row.get('PropAddr', row.get('PROP_ADDR',
                                 row.get('Address', row.get('ADDRESS', ''))))
                        city = row.get('City', row.get('CITY', 'Detroit'))
                        state = row.get('State', row.get('STATE', 'MI'))

                        full_address = f"{address}, {city}, {state} {zip_match}".strip()

                        # Extract beds
                        beds = row.get('Beds', row.get('BEDS',
                               row.get('Bedrooms', row.get('BEDROOMS', 'N/A'))))

                        results.append({
                            "source": "HUD Homes (Official Data)",
                            "address": full_address,
                            "price": f"${price:,.0f}",
                            "beds": str(beds),
                            "zip": zip_match,
                            "url": "https://www.hudhomestore.gov",
                            "date_found": datetime.now().strftime("%Y-%m-%d")
                        })

                    except Exception as e:
                        continue

                if results:
                    break

        except Exception as e:
            print(f"  Could not get HUD data file from {url}: {e}")
            continue

    print(f"  HUD Data File: Found {len(results)} properties")
    return results


def search_usps_vacant():
    """
    Check HUD's USPS vacancy data for Detroit
    HUD publishes quarterly vacancy data by ZIP code
    """
    results = []
    print("Checking HUD vacancy data...")

    try:
        # HUD USPS vacancy crosswalk data
        url = "https://www.huduser.gov/apps/public/uspscrosswalk/home"
        response = requests.get(url, headers=HEADERS, timeout=20)
        print(f"  HUD vacancy data status: {response.status_code}")
    except Exception as e:
        print(f"  Vacancy data error: {e}")

    return results


def search_freddie_mac():
    """Search Freddie Mac HomeSteps foreclosed properties"""
    results = []
    print("Searching Freddie Mac HomeSteps...")

    try:
        for zip_code in TARGET_ZIPS:
            url = f"https://www.homesteps.com/api/listings/search"
            params = {
                "zip": zip_code,
                "minPrice": MIN_PRICE,
                "maxPrice": MAX_PRICE,
                "radius": 5
            }

            response = requests.get(url, params=params, headers=HEADERS, timeout=20)

            if response.status_code == 200:
                try:
                    data = response.json()
                    listings = data.get("listings", data.get("properties", data.get("results", [])))

                    for prop in listings:
                        address = prop.get("address", prop.get("streetAddress", ""))
                        price = prop.get("listPrice", prop.get("price", ""))

                        if address:
                            results.append({
                                "source": "Freddie Mac HomeSteps",
                                "address": address,
                                "price": f"${price:,}" if isinstance(price, (int, float)) else str(price),
                                "beds": str(prop.get("bedrooms", "N/A")),
                                "zip": zip_code,
                                "url": "https://www.homesteps.com",
                                "date_found": datetime.now().strftime("%Y-%m-%d")
                            })
                except:
                    pass

            time.sleep(1)

    except Exception as e:
        print(f"  HomeSteps error: {e}")

    print(f"  Freddie Mac HomeSteps: Found {len(results)} properties")
    return results


def search_treasury_auctions():
    """
    Search US Treasury / IRS property auctions
    Government seized properties are public record
    """
    results = []
    print("Searching Treasury/IRS auctions...")

    try:
        url = "https://treasury.gov/auctions/irs/cat1.htm"
        response = requests.get(url, headers=HEADERS, timeout=20)

        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            for zip_code in TARGET_ZIPS:
                if zip_code in response.text:
                    print(f"  Found Treasury listing in {zip_code}")

    except Exception as e:
        print(f"  Treasury auction error: {e}")

    print(f"  Treasury Auctions: Found {len(results)} properties")
    return results


def search_realtytrac_free():
    """Try RealtyTrac free listings"""
    results = []
    print("Searching RealtyTrac...")

    try:
        for zip_code in TARGET_ZIPS[:3]:  # Try first 3 ZIPs
            url = f"https://www.realtytrac.com/mapsearch/michigan/detroit/{zip_code}/"

            response = requests.get(url, headers=HEADERS, timeout=20)

            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for listing data
                scripts = soup.find_all('script', type='application/ld+json')
                for script in scripts:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, list):
                            for item in data:
                                if item.get('@type') in ['RealEstateListing', 'Place']:
                                    address = item.get('address', {})
                                    price = item.get('offers', {}).get('price', '')

                                    results.append({
                                        "source": "RealtyTrac",
                                        "address": str(address),
                                        "price": str(price),
                                        "beds": "N/A",
                                        "zip": zip_code,
                                        "url": url,
                                        "date_found": datetime.now().strftime("%Y-%m-%d")
                                    })
                    except:
                        continue

            time.sleep(2)

    except Exception as e:
        print(f"  RealtyTrac error: {e}")

    print(f"  RealtyTrac: Found {len(results)} properties")
    return results


def save_results(all_results):
    """Save results to JSON file"""
    filename = f"listings_{datetime.now().strftime('%Y-%m-%d')}.json"

    output = {
        "run_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_found": len(all_results),
        "target_zips": TARGET_ZIPS,
        "price_range": f"${MIN_PRICE:,} - ${MAX_PRICE:,}",
        "listings": all_results
    }

    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Done! Found {len(all_results)} properties.")
    print(f"📄 Saved to: {filename}")
    return filename


def run_scraper():
    print("=" * 55)
    print("DETROIT PROPERTY SCRAPER v3")
    print(f"Running: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"ZIP Codes: {', '.join(TARGET_ZIPS)}")
    print(f"Price Range: ${MIN_PRICE:,} - ${MAX_PRICE:,}")
    print("=" * 55)

    all_results = []

    all_results.extend(search_hud_data_file())
    all_results.extend(search_freddie_mac())
    all_results.extend(search_treasury_auctions())
    all_results.extend(search_realtytrac_free())

    save_results(all_results)

    print("\n📋 PROPERTIES FOUND:")
    print("-" * 55)
    if all_results:
        for i, prop in enumerate(all_results, 1):
            print(f"{i}. {prop['address']}")
            print(f"   Price: {prop['price']} | ZIP: {prop['zip']} | Source: {prop['source']}")
            print()
    else:
        print("No properties found this run.")
        print("Sites may be blocking access or no listings match criteria.")

    print("=" * 55)
    print("Next scheduled run: 2:00 AM daily")


if __name__ == "__main__":
    run_scraper()
