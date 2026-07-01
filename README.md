# Montreal Real Estate Strategic Mesh Engine

A multi-phase real estate intelligence system targeting the Greater Montréal market. It scrapes property listings from [Centris.ca](https://www.centris.ca), enriches each property with interpolated commute-time data via a pre-built spatial mesh, and produces a final per-property accessibility score (0–100) for investment analysis.

---

## System architecture

The pipeline is divided into four decoupled phases. Scraper logic and scoring logic are kept strictly separate — Phase 1/2 produce raw data; Phase 3/4 consume it.

```
Phase 1 → Build Mesh          (geometric grid snapped to OSM roads)
Phase 2 → API Sprint          (Google Maps travel times to target schools/POIs)
Phase 3 → IDW Interpolation   (blend mesh node scores onto property coordinates)
Phase 4 → Accessibility Score (0–100 investment score per listing)
```

---

## Project structure

```
centris-scraper/
├── main.py                              # Phase 1 scraper (Centris listings → CSV)
├── requirements.txt                     # Python dependencies
├── .gitignore
├── centris_scorer_rules.txt             # Blueprint / operating rules (do not modify)
├── centris_market_data.csv              # Scraper output (git-ignored)
├── final_full_lifecycle_mesh.csv        # Static mesh intelligence layer (git-ignored)
├── centris_with_accessibility_scores.csv # Final scored output (git-ignored)
└── README.md
```

---

## Phase 1 — Centris Scraper (`main.py`)

Extracts residential listings from Centris.ca across three regions: **Montréal, Laval, and South Shore**.

**What it scrapes per listing:**
- Identification: MLS ID, URL, category, name, address
- Physical characteristics: rooms, bedrooms, bathrooms, building style, year built, living area, lot area
- Financial details: municipal tax, school tax, condo fees, municipal assessment (lot, building, total)
- Location: `lat` / `lng` (locked before all `Price_*` columns — required by Phase 3)
- Extra: WalkScore, description, parking, pool, move-in date, number of units, revenue potential

**Incremental price tracking:** on re-runs, known properties are price-updated only (a new `Price_YYYY-MM-DD` column is appended each day). The CSV is saved after every page so a crash loses no prior data.

**Filters:** lots, land parcels, farms, chalets, and cottages are excluded by keyword.

---

## Phase 2 — API Sprint (Static Mesh)

Uses Google Maps API trial credits to query driving (best/pessimistic) and transit (Tuesday @ 8:15 AM) travel times from every mesh node to 30+ school and POI targets. Results are stored permanently in `final_full_lifecycle_mesh.csv` — **never re-queried** (Rule 5: Zero Waste).

---

## Phase 3 — IDW Interpolation

Blends mesh node travel times onto individual property coordinates using **Inverse Distance Weighting** over the 4 nearest nodes, powered by `scipy.spatial.cKDTree` for millisecond-speed lookups. Batch-saving and ID-check protection allow safe interruptions and restarts.

---

## Phase 4 — Accessibility Scoring

Produces a proprietary **0–100 accessibility score** per property.

- Drive vs. transit weighting is customizable
- Logarithmic decay penalty applied to commutes over 30 minutes ("The Cliff Effect")
- Output: `centris_with_accessibility_scores.csv`

---

## Output CSV columns

### Scraper output (`centris_market_data.csv`)

| Column | Description |
|---|---|
| `ID` | Centris MLS number |
| `URL` | Direct listing URL |
| `Category` | Property type (e.g. House, Condo) |
| `Name` | Listing title |
| `Address` | Street address |
| `Rooms` / `Bedrooms` / `Bathrooms_Full_Text` | Room counts |
| `Use_of_Property` / `Condo_Type` / `Building_Style` | Property characteristics |
| `Year_Built` / `Living_Area` / `Net_Area` / `Lot_Area` | Size and age |
| `Num_Units` / `Residential_Units` / `Main_Unit` / `Revenue` | Multi-unit fields |
| `Parking` / `Pool` / `Move_in_Date` / `Additional_Features` | Amenities |
| `Muni_Tax_Year` / `Muni_Tax_Amt` | Municipal tax |
| `School_Tax_Year` / `School_Tax_Amt` | School tax |
| `Condo_Fees_Monthly` | Monthly condo fees |
| `Assess_Year` / `Assess_Lot` / `Assess_Building` / `Assess_Total` | Municipal assessment |
| `WalkScore` | Walk Score (scraped if available) |
| `Population` | Reserved / not yet populated |
| `Description` | Full listing description text |
| `lat` / `lng` | Geolocation coordinates (**locked before Price columns**) |
| `Price_YYYY-MM-DD` | Asking price on that run date (one column per day) |

### Final scored output (`centris_with_accessibility_scores.csv`)

Extends the scraper CSV with interpolated commute times and the final 0–100 accessibility score for each property.

---

## Requirements

- Python 3.9+
- Google Maps API key (Phase 2 only — used once during the API Sprint)
- Chromium (installed via Playwright)

---

## Setup

**1. Clone the repository**

```bash
git clone https://github.com/your-username/centris-scraper.git
cd centris-scraper
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**3. Install Python dependencies**

```bash
pip install -r requirements.txt
```

**4. Install the Playwright browser**

```bash
playwright install chromium
```

---

## Usage

**Run the scraper (Phase 1):**

```bash
python main.py
```

The browser runs visible (`headless=False`) so you can monitor progress. A new window opens per region and closes when that region finishes.

Subsequent phases are invoked via their own scripts (see each phase's module once implemented).

---

## Operating rules

These rules are enforced across all phases and must not be violated:

| Rule | Description |
|---|---|
| Rule 1 | No changes to existing functional code unless required for error handling |
| Rule 2 | No changes to `centris_scorer_rules.txt` unless explicitly requested |
| Rule 3 | Data separation — scraper logic is decoupled from scoring logic |
| Rule 4 | Master integrity — `lat`/`lng` columns are locked before all `Price_*` columns |
| Rule 5 | Zero waste — never pay for the same coordinate or travel time twice |

---

## Regions

Regions are defined in `main.py` as the `REGIONS` list. To add a region, find the URL on Centris.ca and append an entry:

```python
{"label": "Longueuil", "url": "https://www.centris.ca/en/properties~for-sale~longueuil"},
```
