import requests
from pathlib import Path

# Leer API key directamente del archivo
api_key = Path("secrets/scopus_apikey.txt").read_text().strip()

print(f"API Key: {api_key[:10]}...{api_key[-10:]}")

# Hacer solicitud
headers = {
    "X-ELS-APIKey": api_key,
    "Accept": "application/json",
}

params = {
    "query": 'TITLE-ABS-KEY("Acanthaster planci")',
    "start": 0,
    "count": 20,
    "sort": "citedby-count",
}

response = requests.get(
    "https://api.elsevier.com/content/search/scopus",
    params=params,
    headers=headers,
    timeout=30
)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    print("✅ Búsqueda exitosa!")
    data = response.json()
    entries = data.get("search-results", {}).get("entry", [])
    print(f"\nEncontrados: {len(entries)} artículos\n")
    
    for i, entry in enumerate(entries[:5], 1):
        title = entry.get("dc:title", "N/A")
        authors = entry.get("dc:creator", "N/A")
        year = entry.get("prism:coverDate", "N/A")[:4]
        cited = entry.get("citedby-count", "0")
        
        print(f"{i}. {title}")
        print(f"   Autores: {authors}")
        print(f"   Año: {year}")
        print(f"   Citaciones: {cited}\n")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text[:500])
