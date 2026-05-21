import requests
import json
import csv
import io
from datetime import datetime
import time

# ============================================================
# DETROIT PROPERTY SCRAPER - Version 2
# Uses official data feeds instead of scraping live pages
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

def search_hud_api():
    """Use HUD's official API to find foreclosed homes"""
    results = []
    print("Searching HUD Homes via official API...")

    for zip_code in TARGET_ZIPS:
        try:
            url = "https://www.hudhomestore.gov/Home/PropertySearch"
            params = {
                "searchtype": "zipcode",
                "zipcode": zip_code,
                "stateCode": "MI",
                "minPrice": MIN_PRICE,
                "maxPrice": MAX_PRICE,
                "beds": 0,
                "baths": 0,
                "propertyStatus": "1",
                "currentPage": 1,
                "pageSize": 50
            }

            response = requests.get(url, params=params, headers=HEADERS, timeout=20)

            if response.status_code == 200:
                try:
                    data = response.json()
                    properties = data.get("properties", data.get("results", data.get("data", [])))

                    if isinstance(properties, list):
                        for prop in properties:
                            address = prop.get("address", prop.get("streetAddress", prop.get("propertyAddress", "")))
                            price = prop.get("listPrice", prop.get("price", prop.get("currentListPrice", "")))
                            beds = prop.get("bedrooms", prop.get("beds", ""))
                            prop_type = str(prop.get("propertyType", prop.get("type", ""))).lower()

                            if address:
                                results.append({
                                    "source": "HUD Homes",
                                    "address": address,
                                    "price": f"${price:,}" if isinstance(price, (int, float)) else str(price),
                                    "beds": str(beds),
                                    "zip": zip_code,
                                    "property_type": prop_type,
                                    "url": f"https://www.hudhomestore.gov",
                                    "date_found": datetime.now().strftime("%Y-%m-%d")
                                })
                except:
                    pass

            time.sleep(1)

        except Exception as e:
            print(f"  HUD API error for {zip_code}: {e}")
            continue

    print(f"  HUD: Found {len(results)} properties")
    return results


def search_detroit_land_bank():
    """Search Detroit Land Bank Authority - public property data"""
    results = []
    print("Searching Detroit Land Bank...")

    try:
        # Detroit Land Bank own-it-now listings
        url = "https://buildingdetroit.org/own-it-now/listings"

        response = requests.get(url, headers=HEADERS, timeout=20)

        if response.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for property listings
            listings = soup.find_all(['div', 'article', 'li'], class_=lambda x: x and any(
                word in str(x).lower() for word in ['listing', 'property', 'house', 'home']
            ))

            for listing in listings[:50]:
                text = listing.get_text(strip=True)
                links = listing.find_all('a', href=True)

                for zip_code in TARGET_ZIPS:
                    if zip_code in text:
                        address_tag = listing.find(['h2', 'h3', 'h4', 'strong', 'p'])
                        address = address_tag.get_text(strip=True) if address_tag else text[:100]

                        price_indicators = ['$', 'price', 'asking']
                        price = "See listing"
                        for word in price_indicators:
                            if word in text.lower():
                                price = "See Land Bank listing"
                                break

                        results.append({
                            "source": "Detroit Land Bank",
                            "address": address,
                            "price": price,
                            "beds": "N/A",
                            "zip": zip_code,
                            "property_type": "unknown",
                            "url": "https://buildingdetroit.org/own-it-now/listings",
                            "date_found": datetime.now().strftime("%Y-%m-%d")
                        })
                        break

    except Exception as e:
        print(f"  Land Bank error: {e}")

    print(f"  Detroit Land Bank: Found {len(results)} properties")
    return results


def search_wayne_county_auction():
    """Search Wayne County tax foreclosure auction list"""
    results = []
    print("Searching Wayne County Tax Foreclosure...")

    try:
        # Wayne County posts CSV/Excel files of foreclosure properties
        urls_to_try = [
            "https://www.waynecounty.com/elected/treasurer/tax-foreclosure.aspx",
            "https://www.waynecounty.com/elected/treasurer/auction.aspx"
        ]

        for url in urls_to_try:
            try:
                response = requests.get(url, headers=HEADERS, timeout=20)
                if response.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Look for downloadable files or table data
                    tables = soup.find_all('table')
                    for table in tables:
                        rows = table.find_all('tr')
                        for row in rows[1:]:
                            cols = row.find_all('td')
                            if len(cols) >= 2:
                                row_text = row.get_text()
                                for zip_code in TARGET_ZIPS:
                                    if zip_code in row_text:
                                        results.append({
                                            "source": "Wayne County Foreclosure",
                                            "address": cols[0].get_text(strip=True),
                                            "price": cols[1].get_text(strip=True) if len(cols) > 1 else "See listing",
                                            "beds": "N/A",
                                            "zip": zip_code,
                                            "property_type": "unknown",
                                            "url": url,
                                            "date_found": datetime.now().strftime("%Y-%m-%d")
                                        })
                                        break

                    # Look for links to CSV or Excel files
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if any(ext in href.lower() for ext in ['.csv', '.xlsx', '.xls']):
                            print(f"  Found data file: {href}")

            except Exception as e:
                continue

    except Exception as e:
        print(f"  Wayne County error: {e}")

    print(f"  Wayne County: Found {len(results)} properties")
    return results


def search_homepath():
    """Search Fannie Mae HomePath for foreclosed properties"""
    results = []
    print("Searching Fannie Mae HomePath...")

    try:
        for zip_code in TARGET_ZIPS:
            url = f"https://www.homepath.com/api/property/search"
            params = {
                "zip": zip_code,
                "minPrice": MIN_PRICE,
                "maxPrice": MAX_PRICE,
                "propertyType": "2",  # Multi-family
                "pageSize": 50
            }

            response = requests.get(url, params=params, headers=HEADERS, timeout=20)

            if response.status_code == 200:
                try:
                    data = response.json()
                    properties = data.get("properties", data.get("results", []))

                    for prop in properties:
                        address = prop.get("address", prop.get("streetAddress", ""))
                        price = prop.get("listPrice", prop.get("price", ""))

                        if address:
                            results.append({
                                "source": "Fannie Mae HomePath",
                                "address": address,
                                "price": f"${price:,}" if isinstance(price, (int, float)) else str(price),
                                "beds": str(prop.get("bedrooms", "N/A")),
                                "zip": zip_code,
                                "property_type": "multi-family",
                                "url": f"https://www.homepath.com",
                                "date_found": datetime.now().strftime("%Y-%m-%d")
                            })
                except:
                    pass

            time.sleep(1)

    except Exception as e:
        print(f"  HomePath error: {e}")

    print(f"  HomePath: Found {len(results)} properties")
    return results


def search_hubzu():
    """Search Hubzu auction platform"""
    results = []
    print("Searching Hubzu...")

    try:
        for zip_code in TARGET_ZIPS:
            url = "https://www.hubzu.com/api/search"
            params = {
                "zip": zip_code,
                "radius": 5,
                "minPrice": MIN_PRICE,
                "maxPrice": MAX_PRICE,
                "pageSize": 50,
                "pageNumber": 1
            }

            response = requests.get(url, params=params, headers=HEADERS, timeout=20)

            if response.status_code == 200:
                try:
                    data = response.json()
                    properties = data.get("listings", data.get("properties", data.get("results", [])))

                    for prop in properties:
                        address = prop.get("address", prop.get("propertyAddress", ""))
                        price = prop.get("currentBid", prop.get("startingBid", prop.get("listPrice", "")))

                        if address:
                            results.append({
                                "source": "Hubzu",
                                "address": address,
                                "price": f"${price:,}" if isinstance(price, (int, float)) else str(price),
                                "beds": str(prop.get("bedrooms", "N/A")),
                                "zip": zip_code,
                                "property_type": str(prop.get("propertyType", "")).lower(),
                                "url": "https://www.hubzu.com",
                                "date_found": datetime.now().strftime("%Y-%m-%d")
                            })
                except:
                    pass

            time.sleep(1)

    except Exception as e:
        print(f"  Hubzu error: {e}")

    print(f"  Hubzu: Found {len(results)} properties")
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
    print("DETROIT PROPERTY SCRAPER v2")
    print(f"Running: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"ZIP Codes: {', '.join(TARGET_ZIPS)}")
    print(f"Price Range: ${MIN_PRICE:,} - ${MAX_PRICE:,}")
    print(f"Property Type: Two-family flat / duplex")
    print("=" * 55)

    all_results = []

    all_results.extend(search_hud_api())
    all_results.extend(search_detroit_land_bank())
    all_results.extend(search_wayne_county_auction())
    all_results.extend(search_homepath())
    all_results.extend(search_hubzu())

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
