import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

SECTEURS = {
    "conso_res": "Résidentiel",
    "conso_indu": "Industrie",
    "conso_tert": "Tertiaire",
    "conso_agri": "Agriculture",
    "conso_autre": "Autre",
}

COULEUR_CARTE = {"Vert": "#2e7d32", "Orange": "#f9a825", "Rouge": "#c62828"}


@st.cache_data
def charger_conso():
    return pd.read_csv(os.path.join(PROCESSED_DIR, "conso_clean_dept.csv"), sep=";", encoding="utf-8-sig")


@st.cache_data
def charger_prod_annuelle():
    return pd.read_csv(os.path.join(PROCESSED_DIR, "prod_annuelle_filiere_clean.csv"), sep=";", encoding="utf-8-sig")


@st.cache_data
def charger_bilan():
    return pd.read_csv(os.path.join(PROCESSED_DIR, "bilan_energetique.csv"), sep=";", encoding="utf-8-sig")


@st.cache_data
def charger_prod_mensuelle():
    df = pd.read_csv(os.path.join(PROCESSED_DIR, "prod_mensuelle_clean_by_reg.csv"), sep=";", encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["annee"].astype(str) + "-" + df["mois_num"].astype(str).str.zfill(2) + "-01")
    return df


@st.cache_data
def charger_regions_geojson():
    with open(os.path.join(PROCESSED_DIR, "regions_geo.json"), encoding="utf-8") as f:
        return json.load(f)


def filtre_region(df, regions_dispo, key):
    choix = st.selectbox("Région", ["France entière"] + regions_dispo, key=key)
    if choix == "France entière":
        return df, choix
    return df[df["nom_reg"] == choix], choix


def onglet_consommation(df_conso):
    st.subheader("Évolution de la consommation d'électricité (2014-2024)")

    regions = sorted(df_conso["nom_reg"].unique())
    df_filtre, choix_region = filtre_region(df_conso, regions, key="conso_region")

    par_annee = df_filtre.groupby("annee")["conso_totale"].sum().reset_index()
    fig_total = px.line(
        par_annee, x="annee", y="conso_totale", markers=True,
        labels={"annee": "Année", "conso_totale": "Consommation totale (MWh)"},
        title=f"Consommation totale — {choix_region}",
    )
    st.plotly_chart(fig_total, use_container_width=True)

    par_secteur = df_filtre.groupby("annee")[list(SECTEURS)].sum().reset_index()
    par_secteur = par_secteur.rename(columns=SECTEURS).melt(
        id_vars="annee", var_name="Secteur", value_name="Consommation (MWh)"
    )
    fig_secteur = px.area(
        par_secteur, x="annee", y="Consommation (MWh)", color="Secteur",
        labels={"annee": "Année"},
        title=f"Répartition par secteur — {choix_region}",
    )
    fig_secteur.update_layout(hovermode="x unified")
    st.plotly_chart(fig_secteur, use_container_width=True)

    st.markdown("#### Consommation par département")
    annees = sorted(df_conso["annee"].unique())
    annee_dept = st.select_slider("Année", options=annees, value=annees[-1], key="conso_annee_dept")
    tableau = (
        df_filtre[df_filtre["annee"] == annee_dept][["nom_dept", "nom_reg", "conso_totale"]]
        .rename(columns={"nom_dept": "Département", "nom_reg": "Région", "conso_totale": "Consommation (MWh)"})
        .sort_values("Consommation (MWh)", ascending=False)
        .reset_index(drop=True)
    )
    st.dataframe(tableau, use_container_width=True, hide_index=True)


def onglet_mix_energetique(df_prod):
    st.subheader("Mix énergétique de production (2014-2024)")

    regions = sorted(df_prod["nom_reg"].unique())
    df_filtre, choix_region = filtre_region(df_prod, regions, key="prod_region")

    par_filiere = df_filtre.groupby(["annee", "filiere"])["prod_mwh"].sum().reset_index()
    fig_mix = px.area(
        par_filiere, x="annee", y="prod_mwh", color="filiere",
        labels={"annee": "Année", "prod_mwh": "Production (MWh)", "filiere": "Filière"},
        title=f"Production par filière — {choix_region}",
    )
    fig_mix.update_layout(hovermode="x unified")
    st.plotly_chart(fig_mix, use_container_width=True)

    derniere_annee = df_filtre["annee"].max()
    par_categorie = (
        df_filtre[df_filtre["annee"] == derniere_annee]
        .groupby("categorie")["prod_mwh"].sum().reset_index()
    )
    fig_categorie = px.pie(
        par_categorie, names="categorie", values="prod_mwh",
        title=f"Part renouvelable / non-renouvelable en {derniere_annee} — {choix_region}",
        color="categorie",
        color_discrete_map={"Renouvelable": "#2e7d32", "Non-Renouvelable": "#607d8b"},
    )
    st.plotly_chart(fig_categorie, use_container_width=True)

    st.markdown("#### Production par région")
    annees = sorted(df_prod["annee"].unique())
    annee_reg = st.select_slider("Année", options=annees, value=annees[-1], key="prod_annee_reg")
    tableau = (
        df_prod[df_prod["annee"] == annee_reg]
        .groupby("nom_reg")["prod_mwh"].sum()
        .reset_index()
        .rename(columns={"nom_reg": "Région", "prod_mwh": "Production (MWh)"})
        .sort_values("Production (MWh)", ascending=False)
        .reset_index(drop=True)
    )
    st.dataframe(tableau, use_container_width=True, hide_index=True)


def onglet_carte(df_bilan, regions_geojson):
    st.subheader("Taux de couverture énergétique par région")
    st.latex(r"\text{Taux de couverture} = \frac{\text{Production régionale (MWh)}}{\text{Consommation régionale (MWh)}} \times 100")

    annees = sorted(df_bilan["annee"].unique())
    annee = st.select_slider("Année", options=annees, value=annees[-1])
    df_annee = df_bilan[df_bilan["annee"] == annee]

    fig = px.choropleth(
        df_annee,
        geojson=regions_geojson,
        locations="code_reg",
        featureidkey="properties.code_reg",
        color="taux_couverture",
        color_continuous_scale="RdYlGn",
        range_color=(0, 150),
        hover_name="nom_region",
        hover_data={"code_reg": False, "taux_couverture": ":.1f"},
        labels={"taux_couverture": "Taux de couverture (%)"},
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "🟩 Vert : production ≥ consommation (taux ≥ 100%) · "
        "🟧 Orange : couverture partielle (50-100%) · "
        "🟥 Rouge : forte dépendance externe (< 50%)"
    )

    st.markdown("#### Détail par région")
    tableau = (
        df_annee[["nom_region", "conso_totale", "prod_mwh", "taux_couverture"]]
        .rename(columns={
            "nom_region": "Région",
            "conso_totale": "Consommation (MWh)",
            "prod_mwh": "Production (MWh)",
            "taux_couverture": "Taux de couverture (%)",
        })
        .sort_values("Taux de couverture (%)", ascending=False)
        .reset_index(drop=True)
    )
    st.dataframe(tableau, use_container_width=True, hide_index=True)


def onglet_production_mensuelle(df_prod_mois):
    st.subheader("Production mensuelle par région (2014-2024)")
    st.caption(
        "Il n'existe pas de donnée de consommation mensuelle par département dans les sources RTE/ENEDIS "
        "utilisées (uniquement annuelle). Cet onglet montre à la place la production mensuelle par région, "
        "disponible dans les données."
    )

    regions = sorted(df_prod_mois["nom_reg"].unique())
    df_filtre, choix_region = filtre_region(df_prod_mois, regions, key="prod_mois_region")

    par_mois = df_filtre.groupby("date")["prod_mwh"].sum().reset_index()
    fig_total = px.line(
        par_mois, x="date", y="prod_mwh",
        labels={"date": "Mois", "prod_mwh": "Production (MWh)"},
        title=f"Production mensuelle totale — {choix_region}",
    )
    st.plotly_chart(fig_total, use_container_width=True)

    par_mois_filiere = df_filtre.groupby(["date", "filiere"])["prod_mwh"].sum().reset_index()
    fig_filiere = px.area(
        par_mois_filiere, x="date", y="prod_mwh", color="filiere",
        labels={"date": "Mois", "prod_mwh": "Production (MWh)", "filiere": "Filière"},
        title=f"Production mensuelle par filière — {choix_region}",
    )
    fig_filiere.update_layout(hovermode="x unified")
    st.plotly_chart(fig_filiere, use_container_width=True)


def variation(debut, fin):
    if debut == 0:
        return None
    return (fin - debut) / debut * 100


def formater_variation(pct):
    if pct is None:
        return "n/d"
    fleche = "📈" if pct >= 0 else "📉"
    return f"{fleche} {pct:+.1f}%"


def onglet_resume(df_conso, df_prod, df_bilan):
    st.subheader("Résumé automatique sur une période")

    annees = sorted(df_bilan["annee"].unique())
    debut, fin = st.select_slider(
        "Période", options=annees, value=(annees[0], min(annees[-1], annees[0] + 6)),
    )
    if debut == fin:
        st.warning("Sélectionne deux années différentes pour comparer.")
        return

    conso_debut = df_conso[df_conso["annee"] == debut]["conso_totale"].sum()
    conso_fin = df_conso[df_conso["annee"] == fin]["conso_totale"].sum()
    prod_debut = df_prod[df_prod["annee"] == debut]["prod_mwh"].sum()
    prod_fin = df_prod[df_prod["annee"] == fin]["prod_mwh"].sum()

    taux_debut = prod_debut / conso_debut * 100 if conso_debut else None
    taux_fin = prod_fin / conso_fin * 100 if conso_fin else None

    st.markdown(f"### {debut} → {fin}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Consommation nationale", f"{conso_fin / 1e6:.0f} TWh", formater_variation(variation(conso_debut, conso_fin)))
    col2.metric("Production nationale", f"{prod_fin / 1e6:.0f} TWh", formater_variation(variation(prod_debut, prod_fin)))
    col3.metric(
        "Taux de couverture national",
        f"{taux_fin:.1f}%" if taux_fin is not None else "n/d",
        f"{taux_fin - taux_debut:+.1f} pts" if taux_debut is not None and taux_fin is not None else "n/d",
    )

    renouv_debut = df_prod[(df_prod["annee"] == debut) & (df_prod["categorie"] == "Renouvelable")]["prod_mwh"].sum()
    renouv_fin = df_prod[(df_prod["annee"] == fin) & (df_prod["categorie"] == "Renouvelable")]["prod_mwh"].sum()
    part_renouv_debut = renouv_debut / prod_debut * 100 if prod_debut else 0
    part_renouv_fin = renouv_fin / prod_fin * 100 if prod_fin else 0

    par_filiere_debut = df_prod[df_prod["annee"] == debut].groupby("filiere")["prod_mwh"].sum()
    par_filiere_fin = df_prod[df_prod["annee"] == fin].groupby("filiere")["prod_mwh"].sum()
    variations_filiere = {
        f: variation(par_filiere_debut.get(f, 0), par_filiere_fin.get(f, 0))
        for f in set(par_filiere_debut.index) | set(par_filiere_fin.index)
    }
    variations_filiere = {f: v for f, v in variations_filiere.items() if v is not None}
    filiere_forte_hausse = max(variations_filiere, key=variations_filiere.get) if variations_filiere else None
    filiere_forte_baisse = min(variations_filiere, key=variations_filiere.get) if variations_filiere else None

    conso_reg_debut = df_conso[df_conso["annee"] == debut].groupby("nom_reg")["conso_totale"].sum()
    conso_reg_fin = df_conso[df_conso["annee"] == fin].groupby("nom_reg")["conso_totale"].sum()
    variations_reg = {
        r: variation(conso_reg_debut.get(r, 0), conso_reg_fin.get(r, 0))
        for r in set(conso_reg_debut.index) | set(conso_reg_fin.index)
    }
    variations_reg = {r: v for r, v in variations_reg.items() if v is not None}
    region_forte_hausse = max(variations_reg, key=variations_reg.get) if variations_reg else None
    region_forte_baisse = min(variations_reg, key=variations_reg.get) if variations_reg else None

    st.markdown("#### Points clés")
    points = [
        f"La consommation nationale est passée de **{conso_debut/1e6:.0f} TWh** à **{conso_fin/1e6:.0f} TWh** "
        f"({formater_variation(variation(conso_debut, conso_fin))}).",
        f"La production nationale est passée de **{prod_debut/1e6:.0f} TWh** à **{prod_fin/1e6:.0f} TWh** "
        f"({formater_variation(variation(prod_debut, prod_fin))}).",
        f"La part des énergies renouvelables dans le mix est passée de **{part_renouv_debut:.1f}%** "
        f"à **{part_renouv_fin:.1f}%**.",
    ]
    if filiere_forte_hausse:
        points.append(
            f"La filière **{filiere_forte_hausse}** a connu la plus forte progression "
            f"({formater_variation(variations_filiere[filiere_forte_hausse])})."
        )
    if filiere_forte_baisse and filiere_forte_baisse != filiere_forte_hausse:
        points.append(
            f"La filière **{filiere_forte_baisse}** a connu la plus forte baisse "
            f"({formater_variation(variations_filiere[filiere_forte_baisse])})."
        )
    if region_forte_hausse:
        points.append(
            f"La région où la consommation a le plus augmenté est **{region_forte_hausse}** "
            f"({formater_variation(variations_reg[region_forte_hausse])})."
        )
    if region_forte_baisse and region_forte_baisse != region_forte_hausse:
        points.append(
            f"La région où la consommation a le plus baissé est **{region_forte_baisse}** "
            f"({formater_variation(variations_reg[region_forte_baisse])})."
        )

    for p in points:
        st.markdown(f"- {p}")


def main():
    st.set_page_config(page_title="EnergiFrance", page_icon="⚡", layout="wide")
    st.title("⚡ EnergiFrance — Production et consommation d'énergie (2014-2024)")

    df_conso = charger_conso()
    df_prod = charger_prod_annuelle()
    df_bilan = charger_bilan()
    df_prod_mois = charger_prod_mensuelle()
    regions_geojson = charger_regions_geojson()

    tab_conso, tab_mix, tab_carte, tab_mois, tab_resume = st.tabs(
        ["Consommation", "Mix énergétique", "Carte interactive", "Production mensuelle", "Résumé automatique"]
    )
    with tab_conso:
        onglet_consommation(df_conso)
    with tab_mix:
        onglet_mix_energetique(df_prod)
    with tab_carte:
        onglet_carte(df_bilan, regions_geojson)
    with tab_mois:
        onglet_production_mensuelle(df_prod_mois)
    with tab_resume:
        onglet_resume(df_conso, df_prod, df_bilan)


if __name__ == "__main__":
    main()
