"""Univers de départ pour `seed.py` : composition indicative du CAC 40.

La composition officielle change périodiquement (révisions trimestrielles
Euronext) ; cette liste est fournie à titre de point de départ pour peupler
`securities` et devra être rafraîchie séparément si l'exactitude à jour
importe pour un usage donné.
"""

# (symbol, name, country, currency, sector)
CAC40_SECURITIES = [
    ("AC.PA", "Accor", "FR", "EUR", "Consommation / Hôtellerie"),
    ("AI.PA", "Air Liquide", "FR", "EUR", "Industrie / Chimie"),
    ("AIR.PA", "Airbus", "FR", "EUR", "Aéronautique / Défense"),
    ("ALO.PA", "Alstom", "FR", "EUR", "Industrie / Transport"),
    ("MT.AS", "ArcelorMittal", "LU", "EUR", "Matériaux / Sidérurgie"),
    ("CS.PA", "AXA", "FR", "EUR", "Assurance"),
    ("BNP.PA", "BNP Paribas", "FR", "EUR", "Finance / Banque"),
    ("EN.PA", "Bouygues", "FR", "EUR", "Industrie / Construction"),
    ("CAP.PA", "Capgemini", "FR", "EUR", "Technologie / Services IT"),
    ("CA.PA", "Carrefour", "FR", "EUR", "Consommation / Distribution"),
    ("ACA.PA", "Crédit Agricole", "FR", "EUR", "Finance / Banque"),
    ("BN.PA", "Danone", "FR", "EUR", "Consommation / Agroalimentaire"),
    ("DSY.PA", "Dassault Systèmes", "FR", "EUR", "Technologie / Logiciels"),
    ("EDEN.PA", "Edenred", "FR", "EUR", "Services"),
    ("ENGI.PA", "Engie", "FR", "EUR", "Énergie / Utilities"),
    ("EL.PA", "EssilorLuxottica", "FR", "EUR", "Santé / Consommation"),
    ("ERF.PA", "Eurofins Scientific", "FR", "EUR", "Santé / Services"),
    ("RMS.PA", "Hermès International", "FR", "EUR", "Consommation / Luxe"),
    ("KER.PA", "Kering", "FR", "EUR", "Consommation / Luxe"),
    ("OR.PA", "L'Oréal", "FR", "EUR", "Consommation"),
    ("LR.PA", "Legrand", "FR", "EUR", "Industrie / Électrification"),
    ("MC.PA", "LVMH", "FR", "EUR", "Consommation / Luxe"),
    ("ML.PA", "Michelin", "FR", "EUR", "Industrie / Automobile"),
    ("ORA.PA", "Orange", "FR", "EUR", "Télécommunications"),
    ("RI.PA", "Pernod Ricard", "FR", "EUR", "Consommation / Spiritueux"),
    ("PUB.PA", "Publicis Groupe", "FR", "EUR", "Services / Communication"),
    ("RNO.PA", "Renault", "FR", "EUR", "Automobile"),
    ("SAF.PA", "Safran", "FR", "EUR", "Aéronautique / Défense"),
    ("SGO.PA", "Saint-Gobain", "FR", "EUR", "Industrie / Matériaux"),
    ("SAN.PA", "Sanofi", "FR", "EUR", "Santé"),
    ("SU.PA", "Schneider Electric", "FR", "EUR", "Industrie / Électrification"),
    ("GLE.PA", "Société Générale", "FR", "EUR", "Finance / Banque"),
    ("STLAP.PA", "Stellantis", "NL", "EUR", "Automobile"),
    ("STMPA.PA", "STMicroelectronics", "NL", "EUR", "Semi-conducteurs"),
    ("TEP.PA", "Teleperformance", "FR", "EUR", "Services"),
    ("HO.PA", "Thales", "FR", "EUR", "Défense / Technologie"),
    ("TTE.PA", "TotalEnergies", "FR", "EUR", "Énergie"),
    ("URW.PA", "Unibail-Rodamco-Westfield", "FR", "EUR", "Immobilier"),
    ("VIE.PA", "Veolia Environnement", "FR", "EUR", "Utilities / Environnement"),
    ("DG.PA", "Vinci", "FR", "EUR", "Industrie / Construction"),
]

assert len(CAC40_SECURITIES) == 40
