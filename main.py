import os
import pandas as pd
import json

from web_scrape import scrape_sold_prices, filter_outliers
from api_scrape import eBayAPIScraper

FILTERS_PATH = os.path.join(os.path.dirname(__file__), "filters", "custom_filters.json")

def choose_option(prompt, options):
    while True:
        print("\n" + prompt)
        for i, opt in enumerate(options, 1):
            print(f"{i}. {opt}")
        choice = input("Select option: ").strip()
        if choice.isdigit():
            choice = int(choice)
            if 1 <= choice <= len(options):
                return choice
            print("Invalid Choice, select 1, 2 or 3")

def ask_yes_no(prompt):
    ans = input(f"{prompt} (y/n): ").strip().lower()
    return ans.startswith("y")

def load_filters():
    if os.path.exists(FILTERS_PATH):
        with open(FILTERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def run_single_search():
    query = input("Enter search term: ").strip()
    if not query:
        print("No query provided.")
        return

    # Step 2: Filter choice
    filters = load_filters()
    exclude_keywords = []

    choice = choose_option(
        "Choose filter option:",
        ["Use JSON filter template", "Type your own filters", "Skip filters"]
    )

    if choice == 1:
        if not filters:
            print("No filters found in filters/custom_filters.json")
        else:
            print("Available filter sets:", ", ".join(filters.keys()))
            set_name = input("Enter filter set name: ").strip()
            if set_name in filters:
                exclude_keywords = filters[set_name]
                print(f"Using filters: {exclude_keywords}")
    elif choice == 2:
        text = input("Enter comma-separated filters: ").strip()
        exclude_keywords = [t.strip().lower() for t in text.split(",") if t.strip()]

    # Step 3: Choose backend
    backend = choose_option("Choose search method:", ["Web scrape", "API scrape"])

    if backend == 1:
        pages = input("Pages to scrape (default=1): ").strip()
        pages = int(pages) if pages.isdigit() else 1
        prices = scrape_sold_prices(query, pages=pages, exclude_keywords=exclude_keywords, debug=True)
    elif backend == 2:
        api_key = input("Enter your eBay API key: ").strip()
        prices = eBayAPIScraper(query, api_key=api_key)
    else:
        print("Invalid backend choice.")
        return

    if not prices:
        print("No prices found.")
        return

    filtered, mean, std = filter_outliers(prices)
    print(f"\nResults for '{query}':")
    print(f"Total found: {len(prices)}, After filtering: {len(filtered)}")
    print(f"Mean: £{mean:.2f}, Std: £{std:.2f}")

def run_batch_search():
    file = input("Enter Excel file path: ").strip()
    if not os.path.exists(file):
        print("File not found.")
        return

    # Only grab the "query" column
    try:
        df = pd.read_excel(file, usecols=["query"])
    except Exception as e:
        print("Error reading Excel:", e)
        return

    print(f"Loaded {len(df)} queries from Excel")
    print("Queries:", df["query"].tolist())

    filters = load_filters()
    exclude_keywords = []

    choice = choose_option(
        "Choose filter option:",
        ["Use JSON filter template", "Type your own filters", "Skip filters"]
    )

    if choice == 1 and filters:
        print("Available filter sets:", ", ".join(filters.keys()))
        set_name = input("Enter filter set name: ").strip()
        if set_name in filters:
            exclude_keywords = filters[set_name]
    elif choice == 2:
        text = input("Enter comma-separated filters: ").strip()
        exclude_keywords = [t.strip().lower() for t in text.split(",") if t.strip()]

    backend = choose_option("Choose search method:", ["Web scrape", "API scrape"])

    if backend == 2:
        api_key = input("Enter your eBay API key: ").strip()
        scraper = eBayAPIScraper(api_key)

    results = []
    for idx, query in enumerate(df["query"], start=1):
        print(f"\n=== Processing {idx}/{len(df)}: {query} ===")

        if backend == 1:
            prices = scrape_sold_prices(query, pages=1, exclude_keywords=exclude_keywords, verbose=True)
        else:
            prices = scraper.scrape_sold_prices(query, exclude_keywords=exclude_keywords)

        filtered, mean, std = filter_outliers(prices)
        results.append({
            "query": query,
            "mean_price": mean,
            "std": std,
            "count": len(filtered)
        })

    out = pd.DataFrame(results)

    if ask_yes_no("Export To Excel?"):
        out_file = input("Enter filename (default=batch_results.xlsx): ").strip()
        if not out_file:
            out_file = "batch_results.xlsx"
        out.to_excel(out_file, index=False)
        print(f"\n✅ Results saved to {out_file}")
    else:
        print("\nℹ️ Export skipped. Results not saved to file.")

    if backend == 2:
        print(f"Total API calls made: {scraper.api_calls}")

if __name__ == "__main__":
    print("=== eBay Webscraper ===")
    while True:
        choice = choose_option("Choose mode:", ["Single search", "Batch search"])
        if choice == 1:
            run_single_search()
        elif choice == 2:
            run_batch_search()
        elif choice == 3:
            print("Goodbye/Au revoir")
            break
