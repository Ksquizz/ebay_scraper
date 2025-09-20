import pandas as pd
import numpy as np
import requests
import time
from statistics import median

# ========================
# CONFIGURATION
# ========================
EBAY_APP_ID = ""  
MAX_CALLS = 4750
WARNINGS = [2500, 3500, 4000]
RESULTS_PER_PAGE = 100

# Exclusion filters
EXCLUDE_KEYWORDS = ["for parts", "spares", "faulty", "not working", "broken", "bundle", "system", "pc", "lot", "job lot", "combo"]

# ========================
# API CALL COUNTER
# ========================
api_call_count = 0

def api_call(url, params):
    global api_call_count
    if api_call_count >= MAX_CALLS:
        raise RuntimeError("Hard cap of 4750 API calls reached. Stopping.")
    api_call_count += 1
    if api_call_count in WARNINGS:
        print(f"⚠️ Warning: {api_call_count} API calls used.")
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

# ========================
# eBay Search Function
# ========================
def ebay_search(query, entries=10):
    """Search completed items on eBay UK, return up to entries results."""
    results = []
    pages = (entries // RESULTS_PER_PAGE) + 1

    for page in range(1, pages + 1):
        url = "https://svcs.ebay.com/services/search/FindingService/v1"
        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.13.0",
            "SECURITY-APPNAME": EBAY_APP_ID,
            "RESPONSE-DATA-FORMAT": "JSON",
            "REST-PAYLOAD": "true",
            "keywords": query,
            "itemFilter(0).name": "Condition",
            "itemFilter(0).value": "Used",
            "itemFilter(1).name": "SoldItemsOnly",
            "itemFilter(1).value": "true",
            "itemFilter(2).name": "LocatedIn",
            "itemFilter(2).value": "GB",
            "paginationInput.entriesPerPage": RESULTS_PER_PAGE,
            "paginationInput.pageNumber": page
        }
        data = api_call(url, params)
        try:
            items = data['findCompletedItemsResponse'][0]['searchResult'][0]['item']
        except KeyError:
            break

        for item in items:
            title = item['title'][0].lower()
            price = float(item['sellingStatus'][0]['currentPrice'][0]['__value__'])
            if not any(x in title for x in EXCLUDE_KEYWORDS):
                results.append(price)

        if len(results) >= entries:
            break
        time.sleep(2)

    return results

# ========================
# Outlier Filtering
# ========================
def filter_outliers(prices):
    if len(prices) < 5:
        return prices, np.mean(prices) if prices else np.nan, (np.nan, np.nan), np.nan

    q1, q3 = np.percentile(prices, [25, 75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    filtered = [p for p in prices if lower <= p <= upper]

    if len(filtered) < 5:
        # fallback to MAD
        med = median(prices)
        mad = median([abs(p - med) for p in prices])
        filtered = [p for p in prices if abs(p - med) <= 3 * mad]

    # Trimmed mean (drop top/bottom 5%)
    trimmed = np.sort(filtered)
    cut = max(1, int(len(trimmed) * 0.05))
    trimmed = trimmed[cut:-cut] if len(trimmed) > 2 * cut else trimmed

    corrected_mean = np.mean(trimmed) if trimmed else np.nan
    stddev_mean = np.std(filtered) if filtered else np.nan
    return filtered, corrected_mean, (lower, upper), stddev_mean

# ========================
# Main Processing
# ========================
def process_excel(input_file, output_file):
    df = pd.read_excel(input_file, sheet_name=r"C:\Users\kelan.scullion.GEOQUIP\Downloads\gpu_comparison_template.xlsx")

    df = df.head(3)

    gpu_comparison = df.copy()
    samples_log = []
    stats_log = []

    for idx, row in df.iterrows():
        nvidia_gpu = str(row["NVIDIA GPU"]).strip() if not pd.isna(row["NVIDIA GPU"]) else None
        vram = str(row["VRAM"]).strip() if not pd.isna(row["VRAM"]) else ""

        # Handle NVIDIA baseline
        if nvidia_gpu:
            query = f"{nvidia_gpu} {vram} graphics card"
            prices = ebay_search(query)

            raw_mean = np.mean(prices) if prices else np.nan
            filtered, corrected_mean, iqr_range, stddev = filter_outliers(prices)

            gpu_comparison.at[idx, "Price"] = round(corrected_mean, 2) if not np.isnan(corrected_mean) else np.nan

            samples_log.append({
                "GPU": f"{nvidia_gpu} {vram}",
                "Vendor": "NVIDIA",
                "Total Samples": len(prices),
                "Valid Samples": len(prices),
                "Ambiguous Titles": 0,  # placeholder for hybrid desc checks
                "Anomalies Removed": len(prices) - len(filtered),
                "Used for AVG": len(filtered)
            })

            stats_log.append({
                "GPU": f"{nvidia_gpu} {vram}",
                "Vendor": "NVIDIA",
                "Samples Scanned": len(prices),
                "Raw Mean": round(raw_mean, 2) if not np.isnan(raw_mean) else np.nan,
                "Corrected Mean": round(corrected_mean, 2) if not np.isnan(corrected_mean) else np.nan,
                "IQR Range": f"{round(iqr_range[0],2)}–{round(iqr_range[1],2)}" if not np.isnan(iqr_range[0]) else "N/A",
                "Std Dev Around Mean": round(stddev, 2) if not np.isnan(stddev) else np.nan
            })

    # Build output Excel
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        gpu_comparison.to_excel(writer, sheet_name="GPU comparison", index=False)
        pd.DataFrame(samples_log).to_excel(writer, sheet_name="Samples", index=False)
        pd.DataFrame(stats_log).to_excel(writer, sheet_name="stats", index=False)

    print(f"✅ Exported to {output_file}")

# Example usage
process_excel("gpu_comparison_nvidia_amd_intel_vram_split.xlsx", "gpu_comparison_with_prices.xlsx")