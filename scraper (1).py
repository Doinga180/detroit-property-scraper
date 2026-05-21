import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time

# ============================================================
# DETROIT PROPERTY SCRAPER
# Runs automatically and finds two-family flats in Detroit
# Target ZIP codes based on Section 8 payment standards $1,300+
# ============================================================

TARGET_ZIPS = [
    "48207", "48219", "48221", "48224", "48205",
    "48215", "48223", "48235", "48217", "48225"
]

MAX_PRICE = 200000
MIN_PRICE = 30000
PROPERTY_TYPE = "two-family flat / duplex"

def scrape_hud_homes():
    """Scrape HUD home listings for Detroit ZIP codes"""
    results = []
    print("Searching HUD Homes...")
    
    for zip_code in TARGET_ZIPS:
        try:
            url = f"https://www.hudhomestore.gov/Listing/PropertySearchResult.aspx?zipCode={zip_code}&stateCode=MI&foreclosureType=&bed=0&bath=0&story=0&garage=0&school=0&minPrice={MIN_PRICE}&maxPrice={MAX_PRICE}&offerDueDate=&propertyStatus=1&caseNumber=&street=&city=&countyName=&searchRadius=0&sortBy=4&sortOrder=ASC&currentPage=1"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                listings = soup.find_all('div', class_='property-listing')
                
                for listing in listings:
                    try:
                        address = listing.find('span', class_='address')
                        price = listing.find('span', class_='price')
                        beds = listing.find('span', class_='beds')
                        
                        if address and price:
                            results.append({
                                "source": "HUD Homes",
                                "address": address.text.strip(),
                                "price": price.text.strip(),
                                "beds": beds.text.strip() if beds else "N/A",
                                "zip": zip_code,
                                "url": url,
                                "date_found": datetime.now().strftime("%Y-%m-%d")
                            })
                    except Exception as e:
                        continue
                        
            time.sleep(2)  # Be respectful - wait 2 seconds between requests
            
        except Exception as e:
            print(f"  Could not reach HUD for ZIP {zip_code}: {e}")
            continue
    
    return results


def scrape_wayne_county():
    """Scrape Wayne County tax foreclosure listings"""
    results = []
    print("Searching Wayne County Foreclosures...")
    
    try:
        url = "https://www.waynecounty.com/elected/treasurer/tax-foreclosure.aspx"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for property listings in tables
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header row
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        address_text = cols[0].text.strip()
                        
                        # Check if any of our target ZIPs are mentioned
                        for zip_code in TARGET_ZIPS:
                            if zip_code in address_text:
                                results.append({
                                    "source": "Wayne County Foreclosure",
                                    "address": address_text,
                                    "price": cols[1].text.strip() if len(cols) > 1 else "See listing",
                                    "beds": "N/A",
                                    "zip": zip_code,
                                    "url": url,
                                    "date_found": datetime.now().strftime("%Y-%m-%d")
                                })
                                
    except Exception as e:
        print(f"  Could not reach Wayne County site: {e}")
    
    return results


def scrape_auction_com():
    """Scrape Auction.com for Detroit foreclosure properties"""
    results = []
    print("Searching Auction.com...")
    
    for zip_code in TARGET_ZIPS:
        try:
            url = f"https://www.auction.com/residential/?address={zip_code}&keywords=duplex&priceMin={MIN_PRICE}&priceMax={MAX_PRICE}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                listings = soup.find_all('div', {'data-testid': 'property-card'})
                
                for listing in listings:
                    try:
                        address = listing.find('p', class_='address')
                        price = listing.find('span', class_='price')
                        
                        if address and price:
                            results.append({
                                "source": "Auction.com",
                                "address": address.text.strip(),
                                "price": price.text.strip(),
                                "beds": "N/A",
                                "zip": zip_code,
                                "url": url,
                                "date_found": datetime.now().strftime("%Y-%m-%d")
                            })
                    except Exception as e:
                        continue
                        
            time.sleep(2)
            
        except Exception as e:
            print(f"  Could not reach Auction.com for ZIP {zip_code}: {e}")
            continue
    
    return results


def save_results(all_results):
    """Save results to a JSON file with today's date"""
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
    print(f"📄 Results saved to: {filename}")
    return filename


def run_scraper():
    print("=" * 50)
    print("DETROIT PROPERTY SCRAPER")
    print(f"Running: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"ZIP Codes: {', '.join(TARGET_ZIPS)}")
    print(f"Price Range: ${MIN_PRICE:,} - ${MAX_PRICE:,}")
    print("=" * 50)
    
    all_results = []
    
    # Run all scrapers
    all_results.extend(scrape_hud_homes())
    all_results.extend(scrape_wayne_county())
    all_results.extend(scrape_auction_com())
    
    # Save results
    save_results(all_results)
    
    # Print summary
    print("\n📋 PROPERTIES FOUND:")
    print("-" * 50)
    for i, prop in enumerate(all_results, 1):
        print(f"{i}. {prop['address']}")
        print(f"   Price: {prop['price']} | ZIP: {prop['zip']} | Source: {prop['source']}")
        print()


if __name__ == "__main__":
    run_scraper()
