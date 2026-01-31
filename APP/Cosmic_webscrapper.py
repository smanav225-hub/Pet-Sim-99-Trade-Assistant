import asyncio
import os
import re
import sqlite3
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright

import sys

# --- PATH CONFIGURATION (STRICTLY LOCAL) ---
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    
DB_FILE = os.path.join(SCRIPT_DIR, "cosmic_values.db")
EXPORT_DIR = os.path.join(SCRIPT_DIR, "Exports")

# Ensure Exports folder exists
if not os.path.exists(EXPORT_DIR):
    os.makedirs(EXPORT_DIR)

CATEGORIES = {
    "1": ("Titanics", "https://petsimulatorvalues.com/values.php?category=Titanics&sort=id&order=ASC"),
    "2": ("Gargantuans", "https://petsimulatorvalues.com/values.php?category=Gargantuans&sort=id&order=ASC"),
    "3": ("Huges", "https://petsimulatorvalues.com/values.php?category=Huges&sort=id&order=ASC"),
    "4": ("Exclusives", "https://petsimulatorvalues.com/values.php?category=Exclusives&sort=id&order=ASC"),
    "5": ("Clans", "https://petsimulatorvalues.com/values.php?category=Clans&sort=id&order=ASC"),
    "6": ("Misc", "https://petsimulatorvalues.com/values.php?category=Misc&sort=id&order=ASC"),
    "7": ("Eggs", "https://petsimulatorvalues.com/values.php?category=Eggs&sort=id&order=ASC"),
    "8": ("All", "https://petsimulatorvalues.com/values.php?category=all")
}

def parse_raw_text(text, scrape_date):
    data = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    current_pet = {}
    j = 0
    while j < len(lines):
        line = lines[j]
        
        if line.startswith("Last updated:"):
            current_pet['Last Updated'] = line.replace("Last updated:", "").strip()

        if line == "Variant":
            if j > 0: current_pet['Pet Name'] = lines[j-1]
            if j + 1 < len(lines): current_pet['Variant'] = lines[j+1]
            j += 1
        
        elif line == "Value":
            value_parts = []
            k = j + 1
            while k < len(lines) and lines[k] != "Demand":
                value_parts.append(lines[k])
                k += 1
            raw_value = " ".join(value_parts)
            if "|" in raw_value:
                change, val = raw_value.split("|", 1)
                current_pet['Value Change'], current_pet['Value'] = change.strip(), val.strip()
            else:
                current_pet['Value Change'], current_pet['Value'] = "", raw_value
            j = k - 1
        
        elif line == "Demand":
            if j + 1 < len(lines): current_pet['Demand'] = lines[j+1]
        
        elif line.startswith("RAP:"):
            current_pet['RAP'] = line.replace("RAP:", "").strip()
        
        elif line.startswith("EXIST:"):
            current_pet['Exist'] = line.replace("EXIST:", "").strip()
            
            if 'Pet Name' in current_pet:
                p_name = current_pet.get('Pet Name', '')
                variant = current_pet.get('Variant', 'Normal')
                
                v_pattern = re.compile(re.escape(variant), re.IGNORECASE)
                current_pet['Name'] = v_pattern.sub('', p_name).strip() if variant.lower() != "normal" else p_name
                current_pet['GOLD'] = "gold" in variant.lower()
                current_pet['RAINBOW'] = "rainbow" in variant.lower()
                current_pet['SHINY'] = "shiny" in variant.lower()
                current_pet['Date_Scraped'] = scrape_date
                
                final_pet = {
                    'Pet Name': p_name,
                    'Variant': variant,
                    'Value': current_pet.get('Value', ''),
                    'Value Change': current_pet.get('Value Change', ''),
                    'Last Updated': current_pet.get('Last Updated', ''),
                    'Demand': current_pet.get('Demand', ''),
                    'Exist': current_pet.get('Exist', ''),
                    'RAP': current_pet.get('RAP', ''),
                    'Name': current_pet['Name'],
                    'GOLD': current_pet['GOLD'],
                    'RAINBOW': current_pet['RAINBOW'],
                    'SHINY': current_pet['SHINY'],
                    'Date_Scraped': scrape_date
                }
                data.append(final_pet)
            current_pet = {}
        j += 1
    return data

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS master 
                         ("Pet Name" TEXT, "Variant" TEXT, "Value" TEXT, "Value Change" TEXT, 
                          "Last Updated" TEXT, "Demand" TEXT, "Exist" TEXT, "RAP" TEXT, 
                          "Name" TEXT, "GOLD" BOOLEAN, "RAINBOW" BOOLEAN, "SHINY" BOOLEAN, 
                          "Date_Scraped" TEXT, PRIMARY KEY ("Pet Name", "Variant"))''')
        conn.commit()
        conn.close()

    def update_pets(self, pet_list):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        inserts, updates, skipped = 0, 0, 0

        for pet in pet_list:
            cursor.execute('SELECT "Value", "Value Change", "Demand", "Exist", "RAP" FROM master WHERE "Pet Name" = ? AND "Variant" = ?', 
                           (pet['Pet Name'], pet['Variant']))
            row = cursor.fetchone()
            
            if row:
                db_val, db_change, db_demand, db_exist, db_rap = row
                changed = (str(pet['Value']) != str(db_val) or 
                           str(pet['Value Change']) != str(db_change) or
                           str(pet['Demand']) != str(db_demand) or
                           str(pet['Exist']) != str(db_exist) or
                           str(pet['RAP']) != str(db_rap))

                if changed:
                    cursor.execute('''UPDATE master SET "Value"=?,
                                     "Value Change"=?,
                                     "Last Updated"=?,
                                     "Demand"=?,
                                     "Exist"=?,
                                     "RAP"=?,
                                     "Date_Scraped"=? 
                                     WHERE "Pet Name"=? AND "Variant"=?''',
                                   (pet['Value'], pet['Value Change'], pet['Last Updated'], 
                                    pet['Demand'], pet['Exist'], pet['RAP'], pet['Date_Scraped'],
                                    pet['Pet Name'], pet['Variant']))
                    updates += 1
                else:
                    skipped += 1
            else:
                cursor.execute('''INSERT INTO master ("Pet Name", "Variant", "Value", "Value Change", 
                                 "Last Updated", "Demand", "Exist", "RAP", "Name", "GOLD", "RAINBOW", "SHINY", "Date_Scraped") 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                               (pet['Pet Name'], pet['Variant'], pet['Value'], pet['Value Change'],
                                pet['Last Updated'], pet['Demand'], pet['Exist'], pet['RAP'],
                                pet['Name'], pet['GOLD'], pet['RAINBOW'], pet['SHINY'], pet['Date_Scraped']))
                inserts += 1
        
        conn.commit()
        conn.close()
        return inserts, updates, skipped

    def export_to_excel(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM master", conn)
        conn.close()

        if df.empty: return

        titanics = df[df['Pet Name'].str.contains('Titanic', case=False, na=False)]
        gargantuans = df[df['Pet Name'].str.contains('Gargantuan', case=False, na=False)]
        huges = df[df['Pet Name'].str.contains('Huge', case=False, na=False)]
        special_names = ['Titanic', 'Gargantuan', 'Huge']
        pattern = '|'.join(special_names)
        misc = df[~df['Pet Name'].str.contains(pattern, case=False, na=False)]

        categories = {
            "Master": df,
            "Titanics": titanics,
            "Gargantuans": gargantuans,
            "Huges": huges,
            "Misc": misc
        }

        for name, cat_df in categories.items():
            output_path = os.path.join(EXPORT_DIR, f"{name}.xlsx")
            lock_file = os.path.join(EXPORT_DIR, f"~${name}.xlsx")
            
            if os.path.exists(lock_file):
                continue

            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                cat_df.to_excel(writer, index=False, sheet_name=name)
                ws = writer.sheets[name]
                for column in ws.columns:
                    max_len = max([len(str(cell.value)) for cell in column] + [0])
                    ws.column_dimensions[column[0].column_letter].width = max_len + 2

async def scrape_page(context, url, p_num, semaphore, scrape_date):
    async with semaphore:
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="commit", timeout=40000)
            await asyncio.sleep(1.5)
            text = await page.inner_text("body")
            await page.close()
            return parse_raw_text(text, scrape_date)
        except Exception:
            await page.close()
            return []

async def perform_scrape(category_name, start_url, db_manager, max_p, concurrent_p, progress_callback=None):
    scrape_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(start_url, wait_until="domcontentloaded")
        first_page_text = await page.inner_text("body")
        await page.close()
        
        page_numbers = re.findall(r'(\d+)\nNext', first_page_text) or re.findall(r'(\d+)\s+Next', first_page_text)
        last_page = min(int(page_numbers[-1]) if page_numbers else 1, max_p)
        
        if progress_callback: progress_callback(f"Scraping {category_name}: {last_page} pages detected.")

        semaphore = asyncio.Semaphore(concurrent_p)
        all_pets = parse_raw_text(first_page_text, scrape_date)
        
        if last_page > 1:
            base_url = start_url.split('&page=')[0]
            link_temp = base_url + "&page={}" if '?' in base_url else base_url + "?page={}"
            tasks = [scrape_page(context, link_temp.format(i), i, semaphore, scrape_date) for i in range(2, last_page + 1)]
            results = await asyncio.gather(*tasks)
            for r in results: all_pets.extend(r)
        
        await browser.close()

    if all_pets:
        ins, upd, skp = db_manager.update_pets(all_pets)
        if progress_callback: progress_callback(f"Finished {category_name}: {ins} New, {upd} Updated.")

async def start_scraping_process(choices, max_p, concurrent_p, progress_callback=None):
    db_manager = DatabaseManager(DB_FILE)
    
    if "8" in choices:
        target_choices = ["8"]
    else:
        target_choices = choices

    for choice in target_choices:
        if choice in CATEGORIES:
            name, url = CATEGORIES[choice]
            await perform_scrape(name, url, db_manager, max_p, concurrent_p, progress_callback)
    
    if progress_callback: progress_callback("Exporting to Excel...")
    db_manager.export_to_excel()
    if progress_callback: progress_callback("Process Complete!")

async def main():
    db_manager = DatabaseManager(DB_FILE)
    print("\nPet Simulator 99 Unified Scrapper")
    for k, v in CATEGORIES.items():
        print(f"{k}: {v[0]}")
    choice = input("\nSelect category (1-8): ").strip()
    if choice in CATEGORIES:
        name, url = CATEGORIES[choice]
        await perform_scrape(name, url, db_manager, 9999, 3)
        db_manager.export_to_excel()
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    asyncio.run(main())
