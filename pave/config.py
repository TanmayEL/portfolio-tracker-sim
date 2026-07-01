"""
Central configuration: universe definition, date range, paths.

The universe is ~100 large-cap US stocks spanning 11 GICS sectors.
This is a simplified stand-in for a real index like the S&P 500.
"""

from pathlib import Path
from datetime import date

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "pave.db"

DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Simulation date range  (~2 years of daily data)
# ---------------------------------------------------------------------------
START_DATE: date = date(2023, 1, 1)
END_DATE: date = date(2024, 12, 31)

# ---------------------------------------------------------------------------
# Stock universe (~100 large-cap US stocks, 10 per sector)
# Deliberately labelled as a simplified universe, not a real index replica.
# ---------------------------------------------------------------------------
UNIVERSE: list[dict] = [
    # --- Information Technology ---
    {"ticker": "AAPL",  "name": "Apple Inc.",                    "sector": "Information Technology"},
    {"ticker": "MSFT",  "name": "Microsoft Corp.",               "sector": "Information Technology"},
    {"ticker": "NVDA",  "name": "NVIDIA Corp.",                  "sector": "Information Technology"},
    {"ticker": "AVGO",  "name": "Broadcom Inc.",                 "sector": "Information Technology"},
    {"ticker": "ORCL",  "name": "Oracle Corp.",                  "sector": "Information Technology"},
    {"ticker": "CRM",   "name": "Salesforce Inc.",               "sector": "Information Technology"},
    {"ticker": "ACN",   "name": "Accenture PLC",                 "sector": "Information Technology"},
    {"ticker": "AMD",   "name": "Advanced Micro Devices",        "sector": "Information Technology"},
    {"ticker": "TXN",   "name": "Texas Instruments",             "sector": "Information Technology"},
    {"ticker": "QCOM",  "name": "Qualcomm Inc.",                 "sector": "Information Technology"},

    # --- Financials ---
    {"ticker": "BRK-B", "name": "Berkshire Hathaway B",         "sector": "Financials"},
    {"ticker": "JPM",   "name": "JPMorgan Chase",                "sector": "Financials"},
    {"ticker": "V",     "name": "Visa Inc.",                     "sector": "Financials"},
    {"ticker": "MA",    "name": "Mastercard Inc.",               "sector": "Financials"},
    {"ticker": "BAC",   "name": "Bank of America",               "sector": "Financials"},
    {"ticker": "WFC",   "name": "Wells Fargo",                   "sector": "Financials"},
    {"ticker": "GS",    "name": "Goldman Sachs",                 "sector": "Financials"},
    {"ticker": "MS",    "name": "Morgan Stanley",                "sector": "Financials"},
    {"ticker": "AXP",   "name": "American Express",              "sector": "Financials"},
    {"ticker": "BLK",   "name": "BlackRock Inc.",                "sector": "Financials"},

    # --- Health Care ---
    {"ticker": "LLY",   "name": "Eli Lilly and Co.",             "sector": "Health Care"},
    {"ticker": "UNH",   "name": "UnitedHealth Group",            "sector": "Health Care"},
    {"ticker": "JNJ",   "name": "Johnson & Johnson",             "sector": "Health Care"},
    {"ticker": "ABBV",  "name": "AbbVie Inc.",                   "sector": "Health Care"},
    {"ticker": "MRK",   "name": "Merck & Co.",                   "sector": "Health Care"},
    {"ticker": "TMO",   "name": "Thermo Fisher Scientific",      "sector": "Health Care"},
    {"ticker": "ABT",   "name": "Abbott Laboratories",           "sector": "Health Care"},
    {"ticker": "DHR",   "name": "Danaher Corp.",                 "sector": "Health Care"},
    {"ticker": "AMGN",  "name": "Amgen Inc.",                    "sector": "Health Care"},
    {"ticker": "PFE",   "name": "Pfizer Inc.",                   "sector": "Health Care"},

    # --- Consumer Discretionary ---
    {"ticker": "AMZN",  "name": "Amazon.com Inc.",               "sector": "Consumer Discretionary"},
    {"ticker": "TSLA",  "name": "Tesla Inc.",                    "sector": "Consumer Discretionary"},
    {"ticker": "HD",    "name": "Home Depot Inc.",               "sector": "Consumer Discretionary"},
    {"ticker": "MCD",   "name": "McDonald's Corp.",              "sector": "Consumer Discretionary"},
    {"ticker": "NKE",   "name": "Nike Inc.",                     "sector": "Consumer Discretionary"},
    {"ticker": "LOW",   "name": "Lowe's Companies",              "sector": "Consumer Discretionary"},
    {"ticker": "SBUX",  "name": "Starbucks Corp.",               "sector": "Consumer Discretionary"},
    {"ticker": "TJX",   "name": "TJX Companies",                 "sector": "Consumer Discretionary"},
    {"ticker": "BKNG",  "name": "Booking Holdings",              "sector": "Consumer Discretionary"},
    {"ticker": "CMG",   "name": "Chipotle Mexican Grill",        "sector": "Consumer Discretionary"},

    # --- Communication Services ---
    {"ticker": "META",  "name": "Meta Platforms Inc.",           "sector": "Communication Services"},
    {"ticker": "GOOGL", "name": "Alphabet Inc. Class A",         "sector": "Communication Services"},
    {"ticker": "GOOG",  "name": "Alphabet Inc. Class C",         "sector": "Communication Services"},
    {"ticker": "NFLX",  "name": "Netflix Inc.",                  "sector": "Communication Services"},
    {"ticker": "DIS",   "name": "Walt Disney Co.",               "sector": "Communication Services"},
    {"ticker": "CMCSA", "name": "Comcast Corp.",                 "sector": "Communication Services"},
    {"ticker": "T",     "name": "AT&T Inc.",                     "sector": "Communication Services"},
    {"ticker": "VZ",    "name": "Verizon Communications",        "sector": "Communication Services"},
    {"ticker": "TMUS",  "name": "T-Mobile US Inc.",              "sector": "Communication Services"},
    {"ticker": "CHTR",  "name": "Charter Communications",        "sector": "Communication Services"},

    # --- Industrials ---
    {"ticker": "GE",    "name": "GE Aerospace",                  "sector": "Industrials"},
    {"ticker": "CAT",   "name": "Caterpillar Inc.",              "sector": "Industrials"},
    {"ticker": "RTX",   "name": "RTX Corp.",                     "sector": "Industrials"},
    {"ticker": "HON",   "name": "Honeywell International",       "sector": "Industrials"},
    {"ticker": "UNP",   "name": "Union Pacific Corp.",           "sector": "Industrials"},
    {"ticker": "BA",    "name": "Boeing Co.",                    "sector": "Industrials"},
    {"ticker": "LMT",   "name": "Lockheed Martin",               "sector": "Industrials"},
    {"ticker": "DE",    "name": "Deere & Co.",                   "sector": "Industrials"},
    {"ticker": "UPS",   "name": "United Parcel Service",         "sector": "Industrials"},
    {"ticker": "GD",    "name": "General Dynamics",              "sector": "Industrials"},

    # --- Consumer Staples ---
    {"ticker": "PG",    "name": "Procter & Gamble",              "sector": "Consumer Staples"},
    {"ticker": "KO",    "name": "Coca-Cola Co.",                 "sector": "Consumer Staples"},
    {"ticker": "PEP",   "name": "PepsiCo Inc.",                  "sector": "Consumer Staples"},
    {"ticker": "COST",  "name": "Costco Wholesale",              "sector": "Consumer Staples"},
    {"ticker": "WMT",   "name": "Walmart Inc.",                  "sector": "Consumer Staples"},
    {"ticker": "PM",    "name": "Philip Morris International",   "sector": "Consumer Staples"},
    {"ticker": "MO",    "name": "Altria Group",                  "sector": "Consumer Staples"},
    {"ticker": "MDLZ",  "name": "Mondelez International",        "sector": "Consumer Staples"},
    {"ticker": "CL",    "name": "Colgate-Palmolive",             "sector": "Consumer Staples"},
    {"ticker": "GIS",   "name": "General Mills",                 "sector": "Consumer Staples"},

    # --- Energy ---
    {"ticker": "XOM",   "name": "Exxon Mobil Corp.",             "sector": "Energy"},
    {"ticker": "CVX",   "name": "Chevron Corp.",                 "sector": "Energy"},
    {"ticker": "COP",   "name": "ConocoPhillips",                "sector": "Energy"},
    {"ticker": "SLB",   "name": "SLB (Schlumberger)",            "sector": "Energy"},
    {"ticker": "EOG",   "name": "EOG Resources",                 "sector": "Energy"},
    {"ticker": "MPC",   "name": "Marathon Petroleum",            "sector": "Energy"},
    {"ticker": "PSX",   "name": "Phillips 66",                   "sector": "Energy"},
    {"ticker": "VLO",   "name": "Valero Energy",                 "sector": "Energy"},
    {"ticker": "OXY",   "name": "Occidental Petroleum",          "sector": "Energy"},
    {"ticker": "HAL",   "name": "Halliburton Co.",               "sector": "Energy"},

    # --- Utilities ---
    {"ticker": "NEE",   "name": "NextEra Energy",                "sector": "Utilities"},
    {"ticker": "SO",    "name": "Southern Co.",                  "sector": "Utilities"},
    {"ticker": "DUK",   "name": "Duke Energy Corp.",             "sector": "Utilities"},
    {"ticker": "AEP",   "name": "American Electric Power",       "sector": "Utilities"},
    {"ticker": "EXC",   "name": "Exelon Corp.",                  "sector": "Utilities"},
    {"ticker": "XEL",   "name": "Xcel Energy",                   "sector": "Utilities"},
    {"ticker": "WEC",   "name": "WEC Energy Group",              "sector": "Utilities"},
    {"ticker": "PCG",   "name": "PG&E Corp.",                    "sector": "Utilities"},
    {"ticker": "AWK",   "name": "American Water Works",          "sector": "Utilities"},
    {"ticker": "ETR",   "name": "Entergy Corp.",                 "sector": "Utilities"},

    # --- Real Estate ---
    {"ticker": "PLD",   "name": "Prologis Inc.",                 "sector": "Real Estate"},
    {"ticker": "AMT",   "name": "American Tower Corp.",          "sector": "Real Estate"},
    {"ticker": "EQIX",  "name": "Equinix Inc.",                  "sector": "Real Estate"},
    {"ticker": "CCI",   "name": "Crown Castle Inc.",             "sector": "Real Estate"},
    {"ticker": "SPG",   "name": "Simon Property Group",          "sector": "Real Estate"},
    {"ticker": "O",     "name": "Realty Income Corp.",           "sector": "Real Estate"},
    {"ticker": "WELL",  "name": "Welltower Inc.",                "sector": "Real Estate"},
    {"ticker": "PSA",   "name": "Public Storage",                "sector": "Real Estate"},
    {"ticker": "DLR",   "name": "Digital Realty Trust",          "sector": "Real Estate"},
    {"ticker": "EQR",   "name": "Equity Residential",            "sector": "Real Estate"},

    # --- Materials ---
    {"ticker": "LIN",   "name": "Linde PLC",                     "sector": "Materials"},
    {"ticker": "SHW",   "name": "Sherwin-Williams Co.",          "sector": "Materials"},
    {"ticker": "APD",   "name": "Air Products and Chemicals",    "sector": "Materials"},
    {"ticker": "FCX",   "name": "Freeport-McMoRan Inc.",         "sector": "Materials"},
    {"ticker": "NEM",   "name": "Newmont Corp.",                 "sector": "Materials"},
    {"ticker": "NUE",   "name": "Nucor Corp.",                   "sector": "Materials"},
    {"ticker": "DOW",   "name": "Dow Inc.",                      "sector": "Materials"},
    {"ticker": "DD",    "name": "DuPont de Nemours",             "sector": "Materials"},
    {"ticker": "PPG",   "name": "PPG Industries",                "sector": "Materials"},
    {"ticker": "ALB",   "name": "Albemarle Corp.",               "sector": "Materials"},
]

TICKERS: list[str] = [s["ticker"] for s in UNIVERSE]
