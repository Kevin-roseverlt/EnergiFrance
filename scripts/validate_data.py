import pandas as pd
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')

ANNEES_ATTENDUES = set(range(2014, 2025))
NB_REGIONS_ATTENDU = 13
NB_MOIS_ATTENDU = 12

erreurs = []
avertissements = []


def check_annees(df, nom_fichier, col_annee='annee'):
    annees = set(df[col_annee].unique())
    manquantes = ANNEES_ATTENDUES - annees
    if manquantes:
        erreurs.append(f"{nom_fichier} : années manquantes {sorted(manquantes)}")
    else:
        print(f"✅ {nom_fichier} : 2014-2024 complet")


def check_regions_par_annee(df, nom_fichier, col_annee='annee', col_reg='code_reg'):
    nb_par_annee = df.groupby(col_annee)[col_reg].nunique()
    incorrectes = nb_par_annee[nb_par_annee != NB_REGIONS_ATTENDU]
    if not incorrectes.empty:
        erreurs.append(f"{nom_fichier} : nb régions ≠ {NB_REGIONS_ATTENDU} pour {incorrectes.to_dict()}")
    else:
        print(f"✅ {nom_fichier} : {NB_REGIONS_ATTENDU} régions à chaque année")


def check_mois_par_annee(df, nom_fichier, col_annee='annee', col_mois='mois_num', col_reg='code_reg'):
    nb_mois = df.groupby([col_annee, col_reg])[col_mois].nunique()
    incorrectes = nb_mois[nb_mois != NB_MOIS_ATTENDU]
    if not incorrectes.empty:
        erreurs.append(f"{nom_fichier} : nb mois ≠ {NB_MOIS_ATTENDU} pour {len(incorrectes)} couple(s) année/région")
    else:
        print(f"✅ {nom_fichier} : {NB_MOIS_ATTENDU} mois pour chaque année/région")


def check_valeurs(df, nom_fichier, colonnes, neg_est_avertissement=False):
    """Les valeurs négatives dans prod_mwh reflètent la source RTE (ex: nucléaire/thermique
    en consommation nette lors d'un arrêt technique) et ne sont donc pas bloquantes."""
    probleme = False
    for col in colonnes:
        if col not in df.columns:
            continue
        n_nan = df[col].isna().sum()
        n_neg = (df[col] < 0).sum()
        if n_nan:
            erreurs.append(f"{nom_fichier} : {n_nan} valeur(s) NaN dans '{col}'")
            probleme = True
        if n_neg:
            cible = avertissements if neg_est_avertissement else erreurs
            cible.append(f"{nom_fichier} : {n_neg} valeur(s) négative(s) dans '{col}'")
            probleme = probleme or not neg_est_avertissement
    if not probleme:
        print(f"✅ {nom_fichier} : pas de NaN/valeurs négatives bloquantes sur {colonnes}")


def main():
    conso = pd.read_csv(os.path.join(PROCESSED_DIR, 'conso_clean_dept.csv'), sep=';', encoding='utf-8-sig')
    check_annees(conso, 'conso_clean_dept.csv')
    check_regions_par_annee(conso, 'conso_clean_dept.csv')
    check_valeurs(conso, 'conso_clean_dept.csv', ['conso_totale'])

    prod_an = pd.read_csv(os.path.join(PROCESSED_DIR, 'prod_annuelle_filiere_clean.csv'), sep=';', encoding='utf-8-sig')
    check_annees(prod_an, 'prod_annuelle_filiere_clean.csv')
    check_regions_par_annee(prod_an, 'prod_annuelle_filiere_clean.csv')
    check_valeurs(prod_an, 'prod_annuelle_filiere_clean.csv', ['prod_mwh'], neg_est_avertissement=True)

    prod_mois = pd.read_csv(os.path.join(PROCESSED_DIR, 'prod_mensuelle_clean_by_reg.csv'), sep=';', encoding='utf-8-sig')
    check_annees(prod_mois, 'prod_mensuelle_clean_by_reg.csv')
    check_regions_par_annee(prod_mois, 'prod_mensuelle_clean_by_reg.csv')
    check_mois_par_annee(prod_mois, 'prod_mensuelle_clean_by_reg.csv')
    check_valeurs(prod_mois, 'prod_mensuelle_clean_by_reg.csv', ['prod_mwh'], neg_est_avertissement=True)

    bilan = pd.read_csv(os.path.join(PROCESSED_DIR, 'bilan_energetique.csv'), sep=';', encoding='utf-8-sig')
    check_annees(bilan, 'bilan_energetique.csv')
    check_regions_par_annee(bilan, 'bilan_energetique.csv')
    check_valeurs(bilan, 'bilan_energetique.csv', ['conso_totale', 'prod_mwh', 'taux_couverture'])

    print()
    if avertissements:
        print(f"⚠️  {len(avertissements)} avertissement(s) (non bloquant, caractéristique connue de la source RTE) :")
        for a in avertissements:
            print(f"   - {a}")
        print()
    if erreurs:
        print(f"❌ {len(erreurs)} problème(s) de complétude détecté(s) :")
        for e in erreurs:
            print(f"   - {e}")
        sys.exit(1)
    else:
        print("🎉 Toutes les vérifications de complétude sont passées.")


if __name__ == "__main__":
    main()
