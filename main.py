# INDEX: centris scraping main v1.4
# Phase: P1 - Data Extraction
# Progress: Added multi-region support (Montreal, Laval, Rive-Sud, Rive-Nord)
# Output: centris_market_data.csv

from playwright.sync_api import Playwright, sync_playwright
import time
import csv
import re
import os
import unicodedata
from datetime import datetime

# Each region needs the short "fill" text to trigger the autocomplete,
# and the exact "option" text as it appears in the dropdown.
REGIONS = [
    {"label": "Laval",         "url": "https://www.centris.ca/en/properties~for-sale~laval"},
    {"label": "South Shore",   "url": "https://www.centris.ca/en/properties~for-sale~montreal-south-shore"},
    {"label": "Montréal",      "url": "https://www.centris.ca/en/properties~for-sale~montreal"},
]

def scrape_region(context, page, region, rows_dict, existing_headers, price_col_name, price_index, filename):
    region_label = region["label"]
    print(f"\n{'='*60}")
    print(f"[REGION] Starting: {region_label}")
    print(f"{'='*60}")

    print("[STEP] Navigating to Centris...")
    page.goto("https://www.centris.ca/en")

    try:
        print("[STEP] Handling cookie consent...")
        page.get_by_role("button", name="Accept and continue").click(timeout=2000)
    except:
        print("[INFO] No consent button found.")

    print("[STEP] Navigating directly to region listing...")
    page.goto(region["url"], wait_until="domcontentloaded", timeout=30000)
    time.sleep(1)
    page.get_by_role("button", name="Price $").click()
    page.locator(".slider-selection").first.click()
    page.locator(".slider-track-high").first.click()
    page.get_by_role("slider").first.click()
    page.locator(".slider-selection").first.click()
    page.get_by_role("button", name="Apply").click()
    time.sleep(3)

    while True:
        try:
            page.wait_for_selector(".pager-current", timeout=10000)
            status_text = page.locator(".pager-current").first.inner_text().strip()
            print(f"\n>>> [{region_label}] PAGE: {status_text} <<<")
            all_numbers = re.findall(r'\d+', status_text)
            current_page = int(all_numbers[0]) if all_numbers else 0
            region_max = int(all_numbers[-1]) if len(all_numbers) >= 2 else 0
        except:
            break

        if current_page >= region_max and region_max > 0:
            print(f"  [INFO] Reached last page ({region_max}), moving to next region.")
            break

        time.sleep(1)
        page.wait_for_selector("img[alt*='for sale']", timeout=7000)
        prop_per_page = page.locator("img[alt*='for sale']")
        num_prop = prop_per_page.count()

        for i in range(num_prop):
            item_num = i + 1
            try:
                prop_alt = prop_per_page.nth(i).get_attribute("alt")
                id_match = re.search(r'(\d+)\s*-\s*Centris', prop_alt)
                if not id_match:
                    continue
                prop_id = id_match.group(1)

                temp_name = prop_alt.split(",")[0]
                slug = unicodedata.normalize('NFKD', temp_name).encode('ascii', 'ignore').decode('ascii')
                slug = slug.lower().replace(" for sale in ", " for sale ")
                slug = slug.lower().replace(" for sale ", "-for-sale-")
                slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
                full_url = f"https://www.centris.ca/en/{slug}/{prop_id}"

                if re.search(r'\b(lot|land|farm|terrain|terre|chalet|cottage)\b', prop_alt.lower()):
                    continue

                print(f"\n--- TARGET: {temp_name} ---")

                if prop_id in rows_dict:
                    print(f"  [UPDATE] ID {prop_id}: Fetching price...")
                    current_price = "N/A"
                    try:
                        container = page.locator(f"div.property-thumbnail-item:has(img[alt*='{prop_id}'])").first
                        container.scroll_into_view_if_needed()
                        price_meta = container.locator("meta[itemprop='price']")
                        if price_meta.count() > 0:
                            current_price = price_meta.get_attribute("content")
                        if not current_price or current_price == "N/A":
                            price_text = container.locator(".price span").first.inner_text()
                            current_price = re.sub(r'\D', '', price_text)
                    except:
                        pass

                    row = rows_dict[prop_id]
                    while len(row) < len(existing_headers):
                        row.append("N/A")
                    row[price_index] = current_price
                    continue

                print(f"  [NEW] Item {item_num}/{num_prop}: Opening detail page...")
                new_page = context.new_page()
                try:
                    new_page.goto(full_url, wait_until="domcontentloaded", timeout=60000)
                    new_page.wait_for_selector(".secondary-photo-container", timeout=15000)

                    cat_scraped = "N/A"
                    try:
                        cat_scraped = new_page.locator("meta[itemprop='category']").get_attribute("content")
                    except:
                        pass

                    price_scraped = "N/A"
                    try:
                        price_scraped = new_page.locator("meta[itemprop='price']").first.get_attribute("content")
                    except:
                        pass

                    p_name = new_page.locator("meta[itemprop='name']").first.get_attribute("content")
                    addr = new_page.locator("h2[itemprop='address']").first.inner_text().strip()
                    rooms = new_page.locator(".piece").first.inner_text().strip() if new_page.locator(".piece").count() > 0 else "N/A"
                    beds = new_page.locator(".cac").first.inner_text().strip() if new_page.locator(".cac").count() > 0 else "N/A"
                    baths_text = new_page.locator(".sdb").first.inner_text().strip() if new_page.locator(".sdb").count() > 0 else "N/A"

                    # --- GEOLOCATION EXTRACTION ---
                    lat_scraped = "N/A"
                    lng_scraped = "N/A"
                    try:
                        lat_scraped = new_page.evaluate("document.querySelector('meta[itemprop=\"latitude\"]')?.content")
                        lng_scraped = new_page.evaluate("document.querySelector('meta[itemprop=\"longitude\"]')?.content")
                        if not lat_scraped or lat_scraped == "None":
                            map_btn_html = new_page.locator(".btn-open-map").first.get_attribute("onclick")
                            coords = re.search(r'q=([-.\d]+),([-.\d]+)', map_btn_html)
                            if coords:
                                lat_scraped = coords.group(1)
                                lng_scraped = coords.group(2)
                    except:
                        pass

                    # --- DESCRIPTION EXTRACTION ---
                    desc_scraped = "N/A"
                    try:
                        if new_page.locator("div[itemprop='description']").count() > 0:
                            desc_scraped = new_page.locator("div[itemprop='description']").first.inner_text().replace('\n', ' ').strip()
                    except:
                        pass

                    # --- WALKSCORE EXTRACTION ---
                    walk_scraped = "N/A"
                    try:
                        if new_page.locator(".walkscore span").count() > 0:
                            walk_scraped = new_page.locator(".walkscore span").first.inner_text().strip()
                    except:
                        pass

                    # --- INTEGRATED FINANCIAL LOGIC ---
                    fin = {
                        "mt_y": "N/A", "mt_a": "N/A", "st_y": "N/A", "st_a": "N/A",
                        "fees": "N/A", "a_y": "N/A", "a_l": "N/A", "a_b": "N/A", "a_t": "N/A"
                    }
                    try:
                        new_page.wait_for_selector(".financial-details-container", timeout=10000)
                        a_table = new_page.locator("div.financial-details-table:has(th:has-text('Municipal assessment'))")
                        if a_table.count() > 0:
                            header_text = a_table.locator("thead th").inner_text()
                            year_match = re.search(r'\((\d{4})\)', header_text)
                            fin["a_y"] = year_match.group(1) if year_match else "N/A"
                            rows = a_table.locator("tbody tr")
                            for r_i in range(rows.count()):
                                label = rows.nth(r_i).locator("td").first.inner_text().strip().lower()
                                val = rows.nth(r_i).locator("td").last.inner_text().strip().replace('$', '').replace(',', '')
                                if "lot" in label:
                                    fin["a_l"] = val
                                elif "building" in label:
                                    fin["a_b"] = val
                            fin["a_t"] = a_table.locator("tfoot td").last.inner_text().strip().replace('$', '').replace(',', '')

                        t_table = new_page.locator("div.financial-details-table-yearly:has(th:has-text('Taxes'))")
                        if t_table.count() > 0:
                            rows = t_table.locator("tbody tr")
                            for r_i in range(rows.count()):
                                label_raw = rows.nth(r_i).locator("td").first.inner_text().strip()
                                val = rows.nth(r_i).locator("td").last.inner_text().strip().replace('$', '').replace(',', '')
                                year_match = re.search(r'\((\d{4})\)', label_raw)
                                year = year_match.group(1) if year_match else "N/A"
                                if "Municipal" in label_raw:
                                    fin["mt_y"], fin["mt_a"] = year, val
                                elif "School" in label_raw:
                                    fin["st_y"], fin["st_a"] = year, val

                        f_table = new_page.locator("div.financial-details-table-monthly:has(th:has-text('Fees'))")
                        if f_table.count() > 0:
                            fin["fees"] = f_table.locator("tbody td").last.inner_text().strip().replace('$', '').replace(',', '')
                    except:
                        pass

                    carac_data = {}
                    carac_elements = new_page.locator(".carac-container")
                    for j in range(carac_elements.count()):
                        try:
                            el = carac_elements.nth(j)
                            title = el.locator(".carac-title").inner_text(timeout=2000).strip().lower()
                            value = el.locator(".carac-value").inner_text(timeout=2000).strip()
                            carac_data[title] = value
                        except:
                            continue

                    new_row = [
                        prop_id, full_url, cat_scraped, p_name, addr, rooms, beds, baths_text,
                        carac_data.get("use of property", "N/A"), carac_data.get("condominium type", "N/A"),
                        carac_data.get("building style", "N/A"), carac_data.get("year built", "N/A"),
                        carac_data.get("living area", "N/A"), carac_data.get("net area", carac_data.get("unit area", "N/A")),
                        carac_data.get("lot area", "N/A"), carac_data.get("number of units", "N/A"),
                        carac_data.get("residential units", "N/A"), carac_data.get("main unit", "N/A"),
                        carac_data.get("potential gross revenue", "N/A"), carac_data.get("parking (total)", "N/A"),
                        carac_data.get("pool", "N/A"), carac_data.get("move-in date", "N/A"),
                        carac_data.get("additional features", "N/A"),
                        fin["mt_y"], fin["mt_a"], fin["st_y"], fin["st_a"], fin["fees"],
                        fin["a_y"], fin["a_l"], fin["a_b"], fin["a_t"],
                        walk_scraped, "N/A", desc_scraped, lat_scraped, lng_scraped
                    ]

                    while len(new_row) < len(existing_headers):
                        new_row.append("N/A")
                    new_row[price_index] = price_scraped
                    rows_dict[prop_id] = new_row
                    print(f"  [SUCCESS] Scraped New: {price_scraped} | WalkScore: {walk_scraped}")

                except Exception as inner_e:
                    print(f"  [ERROR] ID {prop_id}: {inner_e}")
                finally:
                    new_page.close()

            except Exception as e:
                print(f"  [CRITICAL] Loop error: {e}")

        print(f"[STEP] Saving results for current page to {filename}...")
        with open(filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(existing_headers)
            writer.writerows(rows_dict.values())

        try:
            next_btn = page.locator("#property-result #divWrapperPager a").nth(2)
            if "disabled" in (next_btn.get_attribute("class") or ""):
                break
            next_btn.click()
            time.sleep(2)
        except:
            break

    print(f"[REGION] Finished: {region_label}")


def run(playwright: Playwright) -> None:
    print(f"\n--- SCRAPER START: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    filename = "centris_market_data.csv"
    today_date = datetime.now().strftime("%Y-%m-%d")
    price_col_name = f"Price_{today_date}"

    base_headers = [
        "ID", "URL", "Category", "Name", "Address", "Rooms", "Bedrooms", "Bathrooms_Full_Text",
        "Use_of_Property", "Condo_Type", "Building_Style", "Year_Built", "Living_Area", "Net_Area", "Lot_Area",
        "Num_Units", "Residential_Units", "Main_Unit", "Revenue",
        "Parking", "Pool", "Move_in_Date", "Additional_Features",
        "Muni_Tax_Year", "Muni_Tax_Amt", "School_Tax_Year", "School_Tax_Amt",
        "Condo_Fees_Monthly", "Assess_Year", "Assess_Lot", "Assess_Building",
        "Assess_Total", "WalkScore", "Population", "Description", "lat", "lng"
    ]

    rows_dict = {}
    existing_headers = []

    if os.path.exists(filename):
        print(f"[STEP] Loading existing file: {filename}")
        with open(filename, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                existing_headers = next(reader)
                for row in reader:
                    if row:
                        rows_dict[row[0]] = row
            except StopIteration:
                existing_headers = base_headers + [price_col_name]
    else:
        existing_headers = base_headers + [price_col_name]

    if price_col_name not in existing_headers:
        existing_headers.append(price_col_name)

    price_index = existing_headers.index(price_col_name)

    for region in REGIONS:
        print("[STEP] Launching browser...")
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        scrape_region(
            context, page, region,
            rows_dict, existing_headers, price_col_name, price_index, filename
        )
        browser.close()
        print(f"[STEP] Browser closed after region: {region['label']}")

    print(f"\n--- COMPLETE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    print(f"[SUMMARY] Total properties in CSV: {len(rows_dict)}")


if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)