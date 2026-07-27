"""Univers complémentaire pour `seed.py` : composition indicative du CAC
Mid 60 — l'indice actuel le plus proche du "second marché" historique
(aboli en 2005, fusionné dans le marché unique Euronext Paris). Réunit les
60 valeurs moyennes françaises suivant immédiatement le CAC 40 et le CAC
Next 20 en capitalisation flottante.

Compilée à partir de la fiche officielle Euronext (31 mars 2026, qui ne
détaille que le top 10) recoupée avec une liste de composition tierce
(EasyBourse) pour les 50 valeurs restantes — comme pour `cac40.py`, la
composition officielle change à chaque révision trimestrielle Euronext et
cette liste devra être rafraîchie séparément si l'exactitude à jour importe
pour un usage donné. 62 valeurs plutôt que 60 : les deux plus grosses
pondérations de la fiche Euronext (ABIVAX, Ipsen) étaient absentes de la
liste tierce (probablement une révision d'indice non encore répercutée par
cette source secondaire) — ajoutées ici plutôt qu'omises, quitte à dépasser
légèrement 60 noms.
"""

# (symbol, name, country, currency, sector)
CAC_MID60_SECURITIES = [
    ("ABVX.PA", "Abivax", "FR", "EUR", "Santé / Biotechnologie"),
    ("IPN.PA", "Ipsen", "FR", "EUR", "Santé / Pharmacie"),
    ("ADP.PA", "Aéroports de Paris", "FR", "EUR", "Infrastructure / Aéroportuaire"),
    ("AF.PA", "Air France-KLM", "FR", "EUR", "Transport / Aérien"),
    ("ATE.PA", "Alten", "FR", "EUR", "Technologie / Conseil IT"),
    ("APAM.AS", "Aperam", "LU", "EUR", "Matériaux / Sidérurgie"),
    ("ARG.PA", "Argan", "FR", "EUR", "Immobilier / Logistique"),
    ("ATO.PA", "Atos Group", "FR", "EUR", "Technologie / IT"),
    ("AYV.PA", "Ayvens", "FR", "EUR", "Finance / Location véhicules"),
    ("BB.PA", "BIC", "FR", "EUR", "Consommation / Biens de consommation"),
    ("BOL.PA", "Bolloré", "FR", "EUR", "Distribution / Logistique"),
    ("CARM.PA", "Carmila", "FR", "EUR", "Immobilier / Commerces"),
    ("CLARI.PA", "Clariane", "FR", "EUR", "Santé / Services"),
    ("COFA.PA", "Coface", "FR", "EUR", "Finance / Assurance-crédit"),
    ("COV.PA", "Covivio", "FR", "EUR", "Immobilier / Finance"),
    ("DBV.PA", "DBV Technologies", "FR", "EUR", "Santé / Biotechnologie"),
    ("DBG.PA", "Derichebourg", "FR", "EUR", "Services / Environnement"),
    ("ELIS.PA", "Elis", "FR", "EUR", "Services"),
    ("EMEIS.PA", "Emeis", "FR", "EUR", "Santé / Services"),
    ("ERA.PA", "Eramet", "FR", "EUR", "Matériaux / Mines"),
    ("RF.PA", "Eurazeo", "FR", "EUR", "Finance / Private equity"),
    ("ETL.PA", "Eutelsat Communications", "FR", "EUR", "Communications / Satellite"),
    ("EXA.PA", "Exail Technologies", "FR", "EUR", "Technologie / Défense"),
    ("EXENS.PA", "Exosens", "FR", "EUR", "Technologie / Optronique"),
    ("FRVIA.PA", "Forvia", "FR", "EUR", "Automobile / Équipementier"),
    ("GFC.PA", "Gecina", "FR", "EUR", "Immobilier"),
    ("ICAD.PA", "Icade", "FR", "EUR", "Immobilier"),
    ("IDL.PA", "ID Logistics", "FR", "EUR", "Services / Logistique"),
    ("NK.PA", "Imerys", "FR", "EUR", "Matériaux / Minéraux"),
    ("ITP.PA", "Interparfums", "FR", "EUR", "Consommation / Parfums"),
    ("IPS.PA", "Ipsos", "FR", "EUR", "Services / Études de marché"),
    ("DEC.PA", "JCDecaux", "FR", "EUR", "Services / Communication"),
    ("FDJU.PA", "FDJ United", "FR", "EUR", "Consommation / Jeux"),
    ("FII.PA", "LISI", "FR", "EUR", "Industrie / Aéronautique"),
    ("MMT.PA", "M6 (Métropole Télévision)", "FR", "EUR", "Médias"),
    ("MAU.PA", "Maurel et Prom", "FR", "EUR", "Énergie"),
    ("MEDCL.PA", "Medincell", "FR", "EUR", "Santé / Biotechnologie"),
    ("MERY.PA", "Mercialys", "FR", "EUR", "Immobilier / Commerces"),
    ("MRN.PA", "Mersen", "FR", "EUR", "Industrie / Matériaux électriques"),
    ("NANO.PA", "Nanobiotix", "FR", "EUR", "Santé / Biotechnologie"),
    ("OPM.PA", "OPmobility", "FR", "EUR", "Automobile / Équipementier"),
    ("PLX.PA", "Pluxee", "FR", "EUR", "Services"),
    ("RCO.PA", "Rémy Cointreau", "FR", "EUR", "Consommation / Spiritueux"),
    ("RUI.PA", "Rubis", "FR", "EUR", "Distribution / Énergie"),
    ("SK.PA", "SEB", "FR", "EUR", "Consommation / Électroménager"),
    ("SESG.PA", "SES", "LU", "EUR", "Communications / Satellite"),
    ("SOLB.BR", "Solvay", "BE", "EUR", "Industrie / Chimie"),
    ("SOP.PA", "Sopra Steria Group", "FR", "EUR", "Technologie / IT"),
    ("TFI.PA", "TF1", "FR", "EUR", "Médias"),
    ("TRI.PA", "Trigano", "FR", "EUR", "Consommation / Loisirs"),
    ("UBI.PA", "Ubisoft Entertainment", "FR", "EUR", "Technologie / Jeux vidéo"),
    ("FR.PA", "Valeo", "FR", "EUR", "Automobile / Équipementier"),
    ("VK.PA", "Vallourec", "FR", "EUR", "Industrie / Sidérurgie"),
    ("VLA.PA", "Valneva", "FR", "EUR", "Santé / Biotechnologie"),
    ("VRLA.PA", "Verallia", "FR", "EUR", "Industrie / Emballage"),
    ("VCT.PA", "Vicat", "FR", "EUR", "Industrie / Matériaux"),
    ("VIRP.PA", "Virbac", "FR", "EUR", "Santé / Pharmacie animale"),
    ("VIRI.PA", "Viridien", "FR", "EUR", "Énergie / Services géophysiques"),
    ("VIV.PA", "Vivendi", "FR", "EUR", "Médias"),
    ("VU.PA", "VusionGroup", "FR", "EUR", "Technologie"),
    ("MF.PA", "Wendel", "FR", "EUR", "Finance / Holding"),
    ("WLN.PA", "Worldline", "FR", "EUR", "Technologie / Paiements"),
]

assert len(CAC_MID60_SECURITIES) == 62
