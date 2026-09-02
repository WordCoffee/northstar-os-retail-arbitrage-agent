from scavio_client import search_kirkland_products

if __name__ == "__main__":
    results = search_kirkland_products()
    print(f"Got {len(results)} results")
    for r in results[:5]:
        print(r)