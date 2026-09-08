import pandas as pd
import os

# --- 1. CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')

# Noms des fichiers
FILE_CONSO = 'conso-departement-annuelle-2.csv'
FILE_PROD_MOIS = 'production-regionale-mensuelle-filiere-2.csv'
FILE_PROD_AN = 'prod-region-annuelle-filiere-2.csv'

# --- 2. FONCTIONS DE NETTOYAGE ---

def nettoyer_conso_enedis():
    print(f"🔹 1/3 Traitement Consommation ÉLECTRICITÉ ({FILE_CONSO})...")
    path = os.path.join(RAW_DIR, FILE_CONSO)
    
    # Lecture
    df = pd.read_csv(path, sep=';', encoding='utf-8', dtype={'Code département': str, 'Code région': str})
    
    # Sélection et Renommage précis (Uniquement l'électricité)
    df = df.rename(columns={
        'Année': 'annee', 
        'Code département': 'code_dept', 
        'Libellé département': 'nom_dept',
        'Code région': 'code_reg', 
        'Libellé région': 'nom_reg',
        # On cible les colonnes précises demandées
        'Consommation électricité agriculture (MWh)': 'conso_agri',
        'Consommation électricité industrie (MWh)': 'conso_indu',
        'Consommation électricité résidentiel (MWh)': 'conso_res',
        'Consommation électricité tertiaire (MWh)': 'conso_tert',
        'Consommation électricité autre (MWh)': 'conso_autre',
        'Consommation électricité totale (MWh)': 'conso_totale'
    })
    
    # On ne garde que les colonnes qu'on vient de renommer
    cols_to_keep = ['annee', 'code_dept', 'nom_dept', 'code_reg', 'nom_reg', 
                    'conso_agri', 'conso_indu', 'conso_res', 'conso_tert', 'conso_autre', 'conso_totale']
    
    # Vérification que les colonnes existent (pour éviter un crash silencieux)
    cols_existantes = [c for c in cols_to_keep if c in df.columns]
    df = df[cols_existantes]
    
    # Sauvegarde version départementale détaillée (utile pour des graphiques par secteur)
    df.to_csv(os.path.join(PROCESSED_DIR, 'conso_clean_dept.csv'), sep=';', encoding='utf-8-sig', index=False)
    
    # --- AGREGATION PAR REGION (Pour le Bilan) ---
    # On somme la 'conso_totale' (électricité) par région
    df_region = df.groupby(['annee', 'code_reg', 'nom_reg'])['conso_totale'].sum().reset_index()
    
    return df_region

def pivot_production(df, id_vars):
    """
    Fonction utilitaire pour transformer les colonnes (Nucléaire, Solaire...) en lignes.
    """
    cols_energie = [
        'Production nucléaire (GWh)', 'Production thermique (GWh)', 
        'Production hydraulique (GWh)', 'Production éolienne (GWh)', 
        'Production solaire (GWh)', 'Production bioénergies (GWh)'
    ]
    cols_presentes = [c for c in cols_energie if c in df.columns]
    
    df_melted = df.melt(id_vars=id_vars, value_vars=cols_presentes, var_name='filiere_raw', value_name='prod_gwh')
    
    df_melted['filiere'] = df_melted['filiere_raw'].str.replace('Production ', '').str.replace(' (GWh)', '').str.capitalize()
    df_melted['prod_gwh'] = pd.to_numeric(df_melted['prod_gwh'], errors='coerce').fillna(0)
    df_melted['prod_mwh'] = df_melted['prod_gwh'] * 1000
    
    return df_melted

def nettoyer_prod_mensuelle():
    print(f"🔹 2/3 Traitement Production Mensuelle ({FILE_PROD_MOIS})...")
    path = os.path.join(RAW_DIR, FILE_PROD_MOIS)
    
    if not os.path.exists(path):
        print("⚠️ Fichier mensuel absent, on passe.")
        return

    df = pd.read_csv(path, sep=';', encoding='utf-8', dtype={'Code INSEE région': str})
    
    df = df.rename(columns={'Code INSEE région': 'code_reg', 'Région': 'nom_reg'})
    
    if 'Mois' in df.columns:
        df['annee'] = df['Mois'].astype(str).str[:4].astype(int)
        df['mois_num'] = df['Mois'].astype(str).str[5:7]
    
    df_clean = pivot_production(df, id_vars=['annee', 'mois_num', 'code_reg', 'nom_reg'])
    
    df_clean.to_csv(os.path.join(PROCESSED_DIR, 'prod_mensuelle_clean_by_reg.csv'), sep=';', encoding='utf-8-sig', index=False)

def nettoyer_prod_annuelle():
    print(f"🔹 3/3 Traitement Production Annuelle ({FILE_PROD_AN})...")
    path = os.path.join(RAW_DIR, FILE_PROD_AN)
    
    if not os.path.exists(path):
        raise FileNotFoundError(f"Le fichier {FILE_PROD_AN} est introuvable.")

    df = pd.read_csv(path, sep=';', encoding='utf-8', dtype={'Code INSEE région': str})
    
    df = df.rename(columns={'Année': 'annee', 'Code INSEE région': 'code_reg', 'Région': 'nom_reg'})
    
    df_clean = pivot_production(df, id_vars=['annee', 'code_reg', 'nom_reg'])
    
    def get_cat(f):
        f = str(f).lower()
        if 'nucléaire' in f or 'thermique' in f: return 'Non-Renouvelable'
        return 'Renouvelable'

    df_clean['categorie'] = df_clean['filiere'].apply(get_cat)
    
    df_clean.to_csv(os.path.join(PROCESSED_DIR, 'prod_annuelle_filiere_clean.csv'), sep=';', encoding='utf-8-sig', index=False)
    
    df_global = df_clean.groupby(['annee', 'code_reg', 'nom_reg'])['prod_mwh'].sum().reset_index()
    return df_global

# --- 3. FONCTION DE FUSION (BILAN) ---

def creer_bilan(df_conso, df_prod):
    print("🔹 Création du Bilan Global (Fusion)...")
    
    df_final = pd.merge(df_conso, df_prod, on=['annee', 'code_reg'], suffixes=('_conso', '_prod'))
    
    if 'nom_reg_conso' in df_final.columns:
        df_final = df_final.rename(columns={'nom_reg_conso': 'nom_region'})
        df_final = df_final.drop(columns=['nom_reg_prod'], errors='ignore')

    df_final['taux_couverture'] = (df_final['prod_mwh'] / df_final['conso_totale']) * 100
    df_final['taux_couverture'] = df_final['taux_couverture'].round(2)
    
    def get_color(taux):
        if taux >= 100: return 'Vert'
        elif taux >= 50: return 'Orange'
        else: return 'Rouge'
    
    df_final['couleur_carte'] = df_final['taux_couverture'].apply(get_color)
    
    out_path = os.path.join(PROCESSED_DIR, 'bilan_energetique.csv')
    df_final.to_csv(out_path, sep=';', encoding='utf-8-sig', index=False)
    print(f"✅ Fichier Bilan créé : {out_path}")

# --- 4. EXECUTION ---
if __name__ == "__main__":
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)
        
    try:
        df_c = nettoyer_conso_enedis()
        nettoyer_prod_mensuelle()
        df_p = nettoyer_prod_annuelle()
        creer_bilan(df_c, df_p)
        print("\n ETL terminé avec succès !")
        
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc() 