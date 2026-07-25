"""
Client EDGAR (SEC) pour récupérer les fondamentaux d'entreprises (10-K).
Ne PAS confondre avec les données TIC (détention de Treasuries par pays),
qui viennent d'une source différente : https://ticdata.treasury.gov

Règles SEC à respecter impérativement :
- User-Agent avec un nom + email valide (sinon 403)
- Ne jamais dépasser 10 requêtes/seconde -> time.sleep entre les appels
  si on boucle sur plusieurs entreprises.
"""
import time
import requests

HEADERS = {
    # REMPLACE par tes vraies informations avant utilisation.
    "User-Agent": "MonEntreprise monnom@monemail.com"
}

RATE_LIMIT_DELAY = 0.15  # un peu de marge sous les 10 req/s imposées par la SEC


def get_company_facts(cik):
    cik_padded = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"Erreur HTTP pour CIK {cik_padded} : {http_err}")
        if response.status_code == 403:
            print("Conseil : vérifie le format du User-Agent ('Nom Email').")
        return None
    except Exception as err:
        print(f"Erreur inattendue pour CIK {cik_padded} : {err}")
        return None


def get_multiple_companies(cik_list):
    """Boucle sûre sur une liste de CIK, en respectant le rate limit SEC."""
    results = {}
    for cik in cik_list:
        results[cik] = get_company_facts(cik)
        time.sleep(RATE_LIMIT_DELAY)  # obligatoire dès qu'on boucle sur plusieurs sociétés
    return results


def extract_revenue_history(data, tags=None):
    """
    Essaie plusieurs libellés US-GAAP possibles pour le chiffre d'affaires,
    car la taxonomie varie selon les entreprises (Apple, autres...).
    """
    if tags is None:
        tags = [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ]
    facts = data.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        if tag in facts:
            return tag, facts[tag]["units"].get("USD", [])
    return None, []


if __name__ == "__main__":
    # Exemple : Apple (320193) et Microsoft (789019)
    ciks = [320193, 789019]
    all_data = get_multiple_companies(ciks)

    for cik, data in all_data.items():
        if not data:
            continue
        print(f"\n=== {data['entityName']} (CIK {cik}) ===")
        tag_used, revenues = extract_revenue_history(data)
        if not tag_used:
            print("Aucune balise de revenu reconnue trouvée.")
            continue
        print(f"Balise utilisée : {tag_used}")
        for item in revenues:
            if item.get("form") == "10-K" and "frame" in item:
                print(f"  {item['frame']} : {item['val']:,} USD")
