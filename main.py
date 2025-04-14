"""Générateur d'emploi du temps avec OR-Tools."""

import csv
import os
from datetime import datetime, timedelta
import calendar
from ortools.sat.python import cp_model
import model
import pandas as pd
from icalendar import Calendar, Event
import pytz
from datetime import datetime
from model import Salle, Enseignant, Groupe, Cours, Seance
import multiprocessing
import traceback
import logging
import sys
import holidays


# Configuration de la journalisation
logging.basicConfig(
    level=logging.DEBUG,  # Niveau de journalisation (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(levelname)s - %(message)s",  # Format des messages
    filename="edt_ingemedia.log",  # Nom du fichier log
    filemode="w",  # Mode d'ouverture du fichier ('w' pour écraser, 'a' pour ajouter)
)


# Redirection de stdout et stderr vers le fichier log
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open("edt_ingemedia.log", "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        # Cette méthode est nécessaire pour que la redirection fonctionne correctement.
        self.terminal.flush()
        self.log.flush()


sys.stdout = Logger()
sys.stderr = Logger()


# Ajout de la classe de callback pour suivre les solutions
class SolutionCallback(cp_model.CpSolverSolutionCallback):
    """Callback pour suivre les solutions trouvées pendant la résolution."""

    def __init__(self):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self._solution_count = 0
        self._start_time = datetime.now()

    def on_solution_callback(self):
        """Appelé à chaque solution trouvée."""
        current_time = datetime.now()
        elapsed = current_time - self._start_time
        self._solution_count += 1
        print(f"Solution #{self._solution_count} trouvée après {elapsed}")

    def solution_count(self):
        return self._solution_count


def charger_salles(fichier="data/salle.csv"):
    """Charge les salles depuis un fichier CSV."""
    salles = []
    with open(fichier, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (
                row["id"].strip() and "id" not in row["id"]
            ):  # Ignorer les lignes de commentaire
                # Charger les disponibilités depuis le CSV
                disponibilite = {
                    "lundi": {
                        "matin": int(row["Lundi_Matin"]),
                        "apres_midi": int(row["Lundi_ApresMidi"]),
                    },
                    "mardi": {
                        "matin": int(row["Mardi_Matin"]),
                        "apres_midi": int(row["Mardi_ApresMidi"]),
                    },
                    "mercredi": {
                        "matin": int(row["Mercredi_Matin"]),
                        "apres_midi": int(row["Mercredi_ApresMidi"]),
                    },
                    "jeudi": {
                        "matin": int(row["Jeudi_Matin"]),
                        "apres_midi": int(row["Jeudi_ApresMidi"]),
                    },
                    "vendredi": {
                        "matin": int(row["Vendredi_Matin"]),
                        "apres_midi": int(row["Vendredi_ApresMidi"]),
                    },
                }
                salles.append(
                    model.Salle(
                        id=int(row["id"]),
                        nom=row["nom"],
                        effectif_max=int(row["effectif_max"]),
                        type_salle=row["type_salle"],
                        disponibilite=disponibilite,
                    )
                )
    return salles


def charger_enseignants(fichier="data/enseignants.csv"):
    """Charge les enseignants depuis un fichier CSV."""
    enseignants = []
    with open(fichier, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (
                row["id"].strip() and "id" not in row["id"]
            ):  # Ignorer les lignes de commentaire
                # Charger les disponibilités depuis le CSV
                semaine_paire = (
                    int(row["semaine_paire"]) if "semaine_paire" in row else 1
                )
                semaine_impaire = (
                    int(row["semaine_impaire"]) if "semaine_impaire" in row else 1
                )
                disponibilite = {
                    "lundi": {
                        "matin": bool(int(row["lundi_matin"])),
                        "apres_midi": bool(int(row["lundi_apres_midi"])),
                    },
                    "mardi": {
                        "matin": bool(int(row["mardi_matin"])),
                        "apres_midi": bool(int(row["mardi_apres_midi"])),
                    },
                    "mercredi": {
                        "matin": bool(int(row["mercredi_matin"])),
                        "apres_midi": bool(int(row["mercredi_apres_midi"])),
                    },
                    "jeudi": {
                        "matin": bool(int(row["jeudi_matin"])),
                        "apres_midi": bool(int(row["jeudi_apres_midi"])),
                    },
                    "vendredi": {
                        "matin": bool(int(row["vendredi_matin"])),
                        "apres_midi": bool(int(row["vendredi_apres_midi"])),
                    },
                }
                enseignant = model.Enseignant(
                    id=int(row["id"]),
                    nom=row["nom"],
                    besoin_salle=row["besoin_salle"],
                    semaine_paire=semaine_paire,
                    semaine_impaire=semaine_impaire,
                    disponibilite=disponibilite,
                )
                enseignants.append(enseignant)
                print(
                    enseignant.nom,
                    enseignant.semaine_paire,
                    enseignant.semaine_impaire,
                    enseignant.disponibilite,
                )
    return enseignants


def charger_groupes(fichier="data/groupe.csv"):
    """
    Charge les groupes depuis un fichier CSV avec gestion des relations parent-enfant.

    Le fichier doit contenir les colonnes: id_groupe, nom, effectif, parent_id
    Les groupes sont chargés en trois étapes:
    1. Chargement initial de tous les groupes
    2. Établissement des relations parent-enfant
    3. Calcul des effectifs des groupes parents
    """
    # Dictionnaire pour stocker temporairement les groupes par ID
    groupes_dict = {}

    # Première étape : chargement initial des groupes
    with open(fichier, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Ignorer les lignes de commentaire ou vides
            if not row.get("id_groupe", "").strip() or "id" in row.get("id_groupe", ""):
                continue

            try:
                id_groupe = row["id_groupe"].strip()
                nom = row["nom"].strip()

                # Déterminer l'effectif (0 si non spécifié)
                effectif = 0
                if row.get("effectif", "").strip():
                    effectif = int(row["effectif"])

                # Récupérer le parent_id s'il existe
                parent_id = None
                if row.get("parent_id", "").strip():
                    parent_id = row["parent_id"].strip()

                # Créer le groupe selon le cas
                if parent_id:
                    # Cas 3: groupe avec parent
                    groupe = model.Groupe(
                        id_groupe=id_groupe,
                        nom=nom,
                        effectif=effectif,
                        id_parent=parent_id,
                    )
                elif effectif > 0:
                    # Cas 1: groupe avec effectif
                    groupe = model.Groupe(
                        id_groupe=id_groupe, nom=nom, effectif=effectif
                    )
                else:
                    # Cas 2: groupe sans effectif
                    groupe = model.Groupe(id_groupe=id_groupe, nom=nom)

                # Ajouter au dictionnaire
                groupes_dict[id_groupe] = groupe

            except (ValueError, KeyError) as e:
                print(
                    f"Erreur lors du chargement du groupe {row.get('id_groupe', 'inconnu')} - {row.get('nom', 'inconnu')}: {e}"
                )

    # Deuxième étape : établir les relations parent-enfant
    for groupe_id, groupe in groupes_dict.items():
        if groupe.id_parent and groupe.id_parent in groupes_dict:
            parent = groupes_dict[groupe.id_parent]

            # Initialiser la liste des sous-groupes si nécessaire
            if not hasattr(parent, "sous_groupes") or parent.sous_groupes is None:
                parent.sous_groupes = []

            # Ajouter ce groupe aux sous-groupes du parent
            parent.sous_groupes.append(groupe)

    # Troisième étape : calculer les effectifs des groupes parents
    for groupe in groupes_dict.values():
        if (
            hasattr(groupe, "sous_groupes")
            and groupe.sous_groupes
            and groupe.effectif == 0
        ):
            # Utiliser la méthode de calcul d'effectif total définie dans la classe Groupe
            groupe.effectif = groupe.total_effectif()

    # Convertir le dictionnaire en liste
    groupes = list(groupes_dict.values())

    # Afficher la liste des groupes pour débogage
    print(f"Liste des groupes chargés:")
    for g in groupes:
        sous_groupes_info = ""
        if hasattr(g, "sous_groupes") and g.sous_groupes:
            sous_groupes_info = (
                f", sous-groupes: {[sg.id_groupe for sg in g.sous_groupes]}"
            )
        parent_info = (
            f", parent: {g.id_parent}"
            if hasattr(g, "id_parent") and g.id_parent
            else ""
        )
        print(
            f"  {g.nom} (ID: {g.id_groupe}, Effectif: {g.effectif}{parent_info}{sous_groupes_info})"
        )

    return groupes


def charger_cours(fichier="data/cours.csv", enseignants=None, groupes=None):
    """
    Charge les informations des cours depuis un fichier CSV.
    Toutes les durées du fichier CSV sont supposées être en heures et
    sont converties en minutes.

    Args:
        fichier: Chemin vers le fichier CSV des cours
        enseignants: Liste des enseignants chargés
        groupes: Liste des groupes chargés

    Returns:
        list: Liste d'objets Cours sans séances associées
    """
    if enseignants is None or groupes is None:
        raise ValueError("Les listes d'enseignants et de groupes doivent être fournies")

    # Créer des dictionnaires pour faciliter la recherche
    enseignants_dict = {e.id: e for e in enseignants}
    groupes_dict = {g.id_groupe: g for g in groupes}

    # Liste pour stocker tous les cours créés
    cours_liste = []

    with open(fichier, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Ignorer les lignes de commentaire ou vides
            if (
                not row.get("id_cours", "").strip()
                or row.get("id_cours", "").lower() == "id_cours"
            ):
                continue

            try:
                id_cours = row["id_cours"].strip()
                nom_cours = row["nom"].strip()
                id_enseignant = int(row["enseignant"].strip())

                # Convertir toutes les durées de heures en minutes
                # Toutes les durées dans le CSV sont considérées comme des heures
                duree_str = row["duree_total"].strip()
                duree_heures = float(duree_str)
                duree_total = int(duree_heures * 60)  # Convertir en minutes

                max_dur_str = row["max_duration"].strip()
                max_heures = float(max_dur_str)
                max_duration = int(max_heures * 60)  # Convertir en minutes

                type_cours = row["type_cours"].strip().upper()

                # Récupérer les IDs des groupes associés
                ids_groupes = [g.strip() for g in row["groupes"].split(",")]

                # Vérifier que l'enseignant existe
                if id_enseignant not in enseignants_dict:
                    print(
                        f"Erreur: Enseignant {id_enseignant} non trouvé pour le cours {id_cours}"
                    )
                    continue

                enseignant = enseignants_dict[id_enseignant]

                # Créer l'objet cours sans séances
                cours = model.Cours(
                    id_cours=id_cours,
                    nom=nom_cours,
                    enseignant=enseignant,
                    groupes=None,  # Sera rempli par generer_seance
                    duree_total=duree_total,
                    max_duration=max_duration,
                    type_cours=type_cours,
                )

                # Stocker temporairement la liste des IDs de groupe
                cours.ids_groupes = ids_groupes

                # Afficher les durées pour vérification
                print(
                    f"Cours {id_cours}: durée totale={duree_total} min, max={max_duration} min"
                )

                cours_liste.append(cours)

            except (ValueError, KeyError) as e:
                print(
                    f"Erreur lors du chargement du cours {row.get('id_cours', 'inconnu')}: {e}"
                )

    print(f"Chargement de {len(cours_liste)} cours")
    return cours_liste


def generer_seance(cours, groupes):
    """
    Génère des séances pour chaque cours en fonction de son type, des groupes associés,
    et découpe les cours en séances selon leur durée maximale.
    """
    import math

    seances = []
    compteur_seance = 1

    # Créer un dictionnaire pour faciliter la recherche des groupes
    groupes_dict = {g.id_groupe: g for g in groupes}

    for c in cours:
        # Déterminer les groupes concernés selon le type de cours
        groupes_pour_seances = []

        if c.type_cours == "CM":
            # Pour un CM, inclure tous les groupes mentionnés
            for id_groupe in c.ids_groupes:
                if id_groupe in groupes_dict:
                    groupes_pour_seances.append((id_groupe, groupes_dict[id_groupe]))
                else:
                    print(
                        f"Attention: Groupe {id_groupe} non trouvé pour le CM {c.id_cours}"
                    )

        elif c.type_cours == "TD":
            # Pour un TD, vérifier chaque groupe
            for id_groupe in c.ids_groupes:
                if id_groupe not in groupes_dict:
                    print(
                        f"Attention: Groupe {id_groupe} non trouvé pour le TD {c.id_cours}"
                    )
                    continue

                groupe = groupes_dict[id_groupe]

                # Si le groupe a des sous-groupes, créer des séances pour chaque sous-groupe
                if hasattr(groupe, "sous_groupes") and groupe.sous_groupes:
                    for sous_groupe in groupe.sous_groupes:
                        groupes_pour_seances.append(
                            (sous_groupe.id_groupe, sous_groupe)
                        )
                else:
                    # Sinon, créer une séance pour ce groupe
                    groupes_pour_seances.append((id_groupe, groupe))

        # Calculer le nombre de séances nécessaires et leurs durées
        duree_totale_min = c.duree_total  # Durée totale en minutes
        duree_max_min = c.max_duration  # Durée maximale par séance en minutes

        # Nombre de séances complètes (de durée max_duration)
        nb_seances_completes = int(duree_totale_min // duree_max_min)

        # Durée de la dernière séance (potentiellement plus courte)
        duree_derniere_seance_min = duree_totale_min % duree_max_min

        # Nombre total de séances
        nb_seances_total = nb_seances_completes + (
            1 if duree_derniere_seance_min > 0 else 0
        )

        # Si la durée totale est inférieure à la durée maximale, créer une seule séance
        if duree_totale_min <= duree_max_min:
            nb_seances_completes = 0
            nb_seances_total = 1
            duree_derniere_seance_min = duree_totale_min

        print(
            f"Cours {c.id_cours} ({c.nom}): durée totale={duree_totale_min/60:.1f}h, "
            f"max={duree_max_min/60:.1f}h, "
            f"{nb_seances_completes} séances complètes + "
            f"{'1 séance de '+str(duree_derniere_seance_min/60)+'h' if duree_derniere_seance_min > 0 else 'aucune séance partielle'}"
        )

        # Créer les séances
        if c.type_cours == "CM":
            # Pour un CM, créer plusieurs séances pour tous les groupes
            if groupes_pour_seances:
                tous_groupes = [g[1] for g in groupes_pour_seances]

                # MODIFICATION: Stocker directement la liste des groupes réels
                # au lieu de créer un groupe composite
                c.groupes = tous_groupes

                # Créer les séances complètes (durée maximale)
                for num_seance in range(1, nb_seances_completes + 1):
                    duree_h = duree_max_min / 60  # Convertir en heures
                    seance = Seance(
                        id_seance=f"S{compteur_seance}_{c.id_cours}_{num_seance}",
                        cours=c,
                        duree=duree_h,  # Durée en heures
                        groupes=tous_groupes,  # Passer la liste des groupes
                    )
                    seances.append(seance)
                    compteur_seance += 1
                    print(f"  Séance CM créée: {seance.id_seance} ({duree_h:.1f}h)")

                # Créer la dernière séance (si nécessaire)
                if duree_derniere_seance_min > 0:
                    duree_h = duree_derniere_seance_min / 60  # Convertir en heures
                    seance = Seance(
                        id_seance=f"S{compteur_seance}_{c.id_cours}_{nb_seances_total}",
                        cours=c,
                        duree=duree_h,  # Durée en heures
                        groupes=tous_groupes,  # Passer la liste des groupes
                    )
                    seances.append(seance)
                    compteur_seance += 1
                    print(
                        f"  Dernière séance CM créée: {seance.id_seance} ({duree_h:.1f}h)"
                    )

        elif c.type_cours == "TD":
            # Pour un TD, créer nb_seances_total séances pour chaque groupe/sous-groupe
            for id_groupe, groupe in groupes_pour_seances:
                # Associer le groupe au cours pour le premier groupe seulement
                if not hasattr(c, "groupes") or c.groupes is None:
                    c.groupes = [groupe]  # Stocker comme liste pour cohérence
                else:
                    c.groupes.append(groupe)

                # Créer les séances complètes (durée maximale)
                for num_seance in range(1, nb_seances_completes + 1):
                    duree_h = duree_max_min / 60  # Convertir en heures
                    seance = Seance(
                        id_seance=f"S{compteur_seance}_{c.id_cours}_{id_groupe}_{num_seance}",
                        cours=c,
                        duree=duree_h,  # Durée en heures
                        groupes=[groupe],  # Passer une liste contenant le groupe
                    )
                    seances.append(seance)
                    compteur_seance += 1
                    print(f"  Séance TD créée: {seance.id_seance} ({duree_h:.1f}h)")

                # Créer la dernière séance (si nécessaire)
                if duree_derniere_seance_min > 0:
                    duree_h = duree_derniere_seance_min / 60  # Convertir en heures
                    seance = Seance(
                        id_seance=f"S{compteur_seance}_{c.id_cours}_{id_groupe}_{nb_seances_total}",
                        cours=c,
                        duree=duree_h,  # Durée en heures
                        groupes=[groupe],  # Passer une liste contenant le groupe
                    )
                    seances.append(seance)
                    compteur_seance += 1
                    print(
                        f"  Dernière séance TD créée: {seance.id_seance} ({duree_h:.1f}h)"
                    )

    print(f"Génération de {len(seances)} séances")
    return seances


class EmploiDuTemps:
    def __init__(
        self,
        annee=2025,
        mois=4,
        semaines=None,
        jours_feries=None,
        date_debut=None,
        date_fin=None,
    ):
        """
        Initialise l'emploi du temps pour un mois et des semaines spécifiques.

        Args:
            annee: Année du planning
            mois: Mois du planning (1-12)
            semaines: Liste des numéros de semaine à planifier (ex: [15, 16, 17, 18])
            jours_feries: Liste des dates fériées au format 'YYYY-MM-DD'
            date_debut: Date de début au format 'YYYY-MM-DD' (pour ignorer les jours avant cette date)
            date_fin: Date de fin au format 'YYYY-MM-DD' (pour ignorer les jours après cette date)
        """
        self.annee = annee
        self.mois = mois
        self.jours_feries = jours_feries or []
        self.date_debut = date_debut
        self.date_fin = date_fin

        # Constantes pour l'emploi du temps
        self.JOURS_SEMAINE = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]

        # Déterminer les semaines du mois si non spécifiées
        if semaines:
            self.SEMAINES = semaines
        else:
            # Obtenir toutes les semaines du mois
            premier_jour = datetime(annee, mois, 1)
            dernier_jour = datetime(annee, mois, calendar.monthrange(annee, mois)[1])
            self.SEMAINES = list(
                set(
                    [
                        d.isocalendar()[1]
                        for d in [
                            premier_jour + timedelta(days=i)
                            for i in range((dernier_jour - premier_jour).days + 1)
                        ]
                    ]
                )
            )

        # Créer le calendrier complet des jours ouvrables
        self.calendrier = {}
        for semaine in self.SEMAINES:
            self.calendrier[semaine] = {}
            for jour_idx, jour_nom in enumerate(self.JOURS_SEMAINE):
                # Trouver la date correspondante
                date = self._trouver_date(
                    semaine, jour_idx + 1
                )  # jour_idx + 1 car lundi = 1 dans isocalendar

                # Vérifier si c'est un jour férié ou hors des limites de date_debut/date_fin
                if (
                    date.strftime("%Y-%m-%d") not in self.jours_feries
                    and (
                        not self.date_debut
                        or date >= datetime.strptime(self.date_debut, "%Y-%m-%d")
                    )
                    and (
                        not self.date_fin
                        or date <= datetime.strptime(self.date_fin, "%Y-%m-%d")
                    )
                ):
                    self.calendrier[semaine][jour_idx] = date
                else:
                    # Jour férié ou hors des limites = None
                    self.calendrier[semaine][jour_idx] = None

        # Si une date de début est spécifiée, ignorer les jours avant cette date
        if self.date_debut:
            date_debut_obj = datetime.strptime(self.date_debut, "%Y-%m-%d")
            for semaine in self.SEMAINES:
                for jour_idx in list(self.calendrier[semaine].keys()):
                    if (
                        self.calendrier[semaine][jour_idx]
                        and self.calendrier[semaine][jour_idx] < date_debut_obj
                    ):
                        self.calendrier[semaine][jour_idx] = None

        # Créneaux de 30 minutes de 8h à 20h
        self.CRENEAUX_30MIN = []
        for h in range(8, 20):
            self.CRENEAUX_30MIN.append(f"{h}:00")
            self.CRENEAUX_30MIN.append(f"{h}:30")

        # Pour l'affichage, nous gardons les créneaux de 2h
        self.CRENEAUX_AFFICHAGE = [f"{h}h00" for h in range(8, 20, 2)]

        self.NB_JOURS = len(self.JOURS_SEMAINE)
        self.NB_SEMAINES = len(self.SEMAINES)
        self.NB_CRENEAUX_30MIN = len(self.CRENEAUX_30MIN)

        # Définir les créneaux de pause déjeuner (de 12h à 14h)
        self.PAUSE_DEJEUNER_DEBUT = 8  # Index du créneau 12:00 (8 * 30min après 8h)
        self.PAUSE_DEJEUNER_FIN = 12  # Index du créneau 14:00 (12 * 30min après 8h)

    def _trouver_date(self, semaine, jour_semaine):
        """
        Trouve la date correspondant à un numéro de semaine et jour de la semaine.

        Args:
            semaine: Numéro de semaine ISO
            jour_semaine: Jour de la semaine (1=lundi, 7=dimanche)

        Returns:
            datetime: La date correspondante
        """
        # Trouver une date dans la semaine spécifiée
        jan1 = datetime(self.annee, 1, 1)
        # Si le 1er janvier n'est pas un lundi, reculer pour trouver le lundi de la semaine
        while jan1.isocalendar()[1] != semaine:
            jan1 += timedelta(days=1)

        # Trouver le jour spécifié dans cette semaine
        date = jan1
        while date.isocalendar()[2] != jour_semaine:
            date += timedelta(days=1)

        return date

    def generer(self, seances, salles, enseignants, groupes):
        """Génère un emploi du temps optimal pour les séances spécifiées."""
        # Importation du module de contraintes
        from contraintes import ajouter_toutes_contraintes

        # Création du modèle
        model = cp_model.CpModel()

        # Variables: pour chaque séance, on crée une variable pour chaque combinaison
        # (semaine, jour, créneau, salle) possible
        seance_vars = {}

        # Pour chaque séance, on crée des variables pour tous les créneaux de début possibles
        print("Création des variables de séance...")
        # Pour chaque séance, on crée des variables pour tous les créneaux de début possibles

        print("Création des variables de séance...")
        for s in seances:
            # Récupérer les propriétés de la séance
            cours = s.cours
            groupe = s.groupes

            # Durée de la séance en minutes (convertir les heures en minutes)
            duree_minutes = int(s.duree * 60)

            # Création des variables pour le placement des séances
            for s_idx, semaine in enumerate(self.SEMAINES):
                for j in range(self.NB_JOURS):
                    # Vérifier si le jour est disponible (non férié)
                    if self.calendrier[semaine][j] is None:
                        continue

                    # Convertir la durée en nombre de créneaux de 30 minutes
                    duree_creneaux = int(duree_minutes / 30)
                    if duree_creneaux == 0:  # Pour éviter les séances trop courtes
                        duree_creneaux = 1

                    # Pour chaque créneau de début possible
                    for cr_debut in range(self.NB_CRENEAUX_30MIN - duree_creneaux + 1):
                        # Vérifier que la séance ne dépasse pas 20h
                        heure_fin_index = cr_debut + duree_creneaux - 1
                        if heure_fin_index >= self.NB_CRENEAUX_30MIN:
                            continue

                        # Convertir les indices en heures réelles pour débogage
                        heure_debut = 8 + cr_debut // 2
                        minute_debut = 30 if cr_debut % 2 else 0

                        # Calculer l'heure de fin directement à partir de la durée
                        heure_fin = heure_debut + (duree_minutes // 60)
                        minute_fin = minute_debut + (duree_minutes % 60)
                        if minute_fin >= 60:
                            heure_fin += 1
                            minute_fin -= 60

                        # Si l'heure de fin est après 20h, on ne crée pas de variable
                        if heure_fin > 20 or (heure_fin == 20 and minute_fin > 0):
                            continue

                        for salle in salles:
                            # Calculer l'effectif total des groupes
                            # Pour une liste de groupes (CM) ou un groupe unique (TD)
                            effectif_total = 0
                            if isinstance(groupe, list):
                                # Si c'est une liste de groupes (cas des CM)
                                for g in groupe:
                                    effectif_total += g.effectif
                            else:
                                # Si c'est un seul groupe (cas des TD)
                                effectif_total = groupe.effectif

                            # Vérifier si la salle peut accueillir le groupe
                            if salle.effectif_max >= effectif_total:
                                # Pour les TD, vérifier que la salle n'est pas un amphi
                                if (
                                    cours.type_cours == "TD"
                                    and salle.type_salle == "Amphi"
                                ):
                                    continue

                                # Pour les CM, privilégier les amphis
                                if (
                                    cours.type_cours == "CM"
                                    and salle.type_salle != "Amphi"
                                ):
                                    # Créer quand même la variable, mais avec une préférence moindre
                                    pass

                                seance_vars[
                                    (s.id_seance, s_idx, j, cr_debut, salle.id)
                                ] = model.NewBoolVar(
                                    f"seance_{s.id_seance}_semaine_{semaine}_jour_{j}_creneau_{cr_debut}_salle_{salle.id}"
                                )

        print("Création des variables de séance terminée.")
        # Ajouter toutes les contraintes au modèle
        ajouter_toutes_contraintes(
            model=model,
            seance_vars=seance_vars,
            seances=seances,
            salles=salles,
            calendrier=self.calendrier,
            semaines=self.SEMAINES,
            nb_jours=self.NB_JOURS,
            nb_creneaux_30min=self.NB_CRENEAUX_30MIN,
            enseignants=enseignants,
            groupes=groupes,
            pause_debut=self.PAUSE_DEJEUNER_DEBUT,
            pause_fin=self.PAUSE_DEJEUNER_FIN,
        )

        # Résolution avec modifications pour améliorer le suivi
        # Réduire le nombre de threads si nécessaire
        cores = multiprocessing.cpu_count()
        threads = min(
            16, cores - 1
        )  # Utiliser moins de threads pour éviter de surcharger le système

        # Configuration du solveur
        solver = cp_model.CpSolver()
        solver.parameters.cp_model_probing_level = (
            0  # Désactiver le probing pour faciliter la détection des conflits
        )
        solver.parameters.enumerate_all_solutions = (
            False  # Ne pas chercher toutes les solutions
        )
        solver.parameters.log_search_progress = True  # Afficher les logs de progression
        solver.parameters.max_time_in_seconds = 7200  # Timeout de 2 heures
        solver.parameters.cp_model_presolve = (
            True  # Activer la simplification du modèle
        )

        solver.parameters.log_search_progress = True

        print("\n" + "=" * 80)
        print(f"DÉMARRAGE DE LA RÉSOLUTION AVEC {threads} THREADS PARALLÈLES")
        print("=" * 80)
        print(f"Heure de début: {datetime.now().strftime('%H:%M:%S')}")
        print(f"Nombre de cœurs disponibles: {cores}")

        try:
            print("Lancement de la résolution...")
            callback = SolutionCallback()
            start_time = datetime.now()
            status = solver.SolveWithSolutionCallback(model, callback)
            end_time = datetime.now()
            duration = end_time - start_time

            print(
                f"Résolution terminée! {callback.solution_count()} solutions trouvées."
            )
            print(f"Heure de fin: {end_time.strftime('%H:%M:%S')}")
            print(f"Durée totale de résolution: {duration}")
            print("=" * 80)

        except KeyboardInterrupt:
            print("\n⚠️ Résolution interrompue manuellement par l'utilisateur")
            return None
        except MemoryError:
            print("\n❌ ERREUR: Mémoire insuffisante pour résoudre le problème")
            print(
                "Essayez de réduire le nombre de séances ou d'assouplir les contraintes"
            )
            return None
        except Exception as e:
            print(f"\n❌ ERREUR lors de la résolution: {str(e)}")
            traceback.print_exc()
            return None

        # Afficher les statistiques du solveur
        print(f"Nombre de branches explorées: {solver.NumBranches()}")
        print(f"Nombre de conflits: {solver.NumConflicts()}")
        print(f"Nombre de solutions trouvées: {solver.ResponseStats()}")
        if status == cp_model.OPTIMAL:
            print(
                "✅ Solution OPTIMALE trouvée ! Toutes les contraintes sont satisfaites."
            )
        elif status == cp_model.FEASIBLE:
            print(
                "⚠️ Solution FAISABLE trouvée, mais elle n'est peut-être pas optimale."
            )
            print("   Certaines contraintes souples peuvent ne pas être satisfaites.")
        elif status == cp_model.INFEASIBLE:
            print(
                "❌ Problème INFAISABLE - Aucune solution ne satisfait toutes les contraintes."
            )
            print("   Analyse des conflits pour identifier les causes...")
            expliquer_infeasibilite(model, solver)
            return None
        elif status == cp_model.MODEL_INVALID:
            print("❌ Modèle INVALIDE - Le modèle contient des erreurs.")
        else:
            print("❓ Statut INCONNU - Le solveur n'a pas pu déterminer le statut.")
            # Récupération des résultats
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            emploi_du_temps = {}
            for s in seances:
                cours = s.cours
                groupe = s.groupes
                duree_minutes = int(s.duree * 60)

                for s_idx, semaine in enumerate(self.SEMAINES):
                    for j in range(self.NB_JOURS):
                        # Vérifier si le jour est disponible
                        if self.calendrier[semaine][j] is None:
                            continue

                        for cr_debut in range(self.NB_CRENEAUX_30MIN):
                            for salle in salles:
                                if (
                                    s.id_seance,
                                    s_idx,
                                    j,
                                    cr_debut,
                                    salle.id,
                                ) in seance_vars and solver.Value(
                                    seance_vars[
                                        (s.id_seance, s_idx, j, cr_debut, salle.id)
                                    ]
                                ):
                                    # Calculer les heures de début et de fin
                                    heure_debut = 8 + cr_debut // 2
                                    minute_debut = 30 if cr_debut % 2 else 0

                                    # Calculer directement l'heure de fin à partir de la durée en minutes
                                    heure_fin = heure_debut + (duree_minutes // 60)
                                    minute_fin = minute_debut + (duree_minutes % 60)
                                    if minute_fin >= 60:
                                        heure_fin += 1
                                        minute_fin -= 60

                                    # Pour l'affichage des créneaux par bloc de 2h
                                    creneau_affichage = self.CRENEAUX_AFFICHAGE[
                                        cr_debut // 4
                                    ]

                                    # Obtenir la date exacte
                                    date = self.calendrier[semaine][j].strftime(
                                        "%Y-%m-%d"
                                    )

                                    # Clé unique avec semaine et jour
                                    cle = f"{s.id_seance}_{semaine}_{j}"

                                    # Modifier pour gérer les listes de groupes
                                    groupe_noms = (
                                        ", ".join([g.nom for g in groupe])
                                        if isinstance(groupe, list)
                                        else groupe.nom
                                    )

                                    emploi_du_temps[cle] = {
                                        "semaine": semaine,
                                        "jour": self.JOURS_SEMAINE[j],
                                        "date": date,
                                        "creneau": creneau_affichage,
                                        "salle": salle.nom,
                                        "cours": cours.nom,
                                        "seance": s.id_seance,
                                        "enseignant": cours.enseignant.nom,
                                        "groupe": groupe_noms,
                                        "heure_debut": f"{heure_debut}:{minute_debut:02d}",
                                        "heure_fin": f"{heure_fin}:{minute_fin:02d}",
                                        "duree": duree_minutes,
                                        "type": cours.type_cours,
                                    }
            return emploi_du_temps
        else:
            return None

    def exporter_vers_ics(
        self,
        emploi_du_temps,
        cours,
        chemin_fichier="output/emploi_du_temps_mensuel.ics",
    ):
        """Exporte l'emploi du temps vers un fichier ICS (iCalendar)."""
        if not emploi_du_temps:
            print("Aucune solution trouvée, pas d'export ICS.")
            return False

        try:
            # Créer un calendrier
            cal = Calendar()
            cal.add("prodid", "-//Emploi du Temps IngeMedia//ingemedia.fr//")
            cal.add("version", "2.0")

            # Fuseau horaire local
            local_tz = pytz.timezone("Europe/Paris")

            # Ajouter chaque cours comme un événement
            for c_key, details in emploi_du_temps.items():
                event = Event()

                # Informations de base
                type_cours = details.get("type", "")
                event.add(
                    "summary",
                    f"{details['cours']} ({type_cours}) - {details['groupe']} - Séance: {details['seance']}",
                )
                event.add(
                    "description",
                    (
                        f"Séance: {details['seance']}\n"
                        f"Enseignant: {details['enseignant']}\n"
                        f"Groupe: {details['groupe']}\n"
                        f"Type: {type_cours}\n"
                        f"Durée: {details['duree']} minutes"
                    ),
                )
                event.add("location", f"Salle {details['salle']}")

                # Date et heure
                date_str = details["date"]
                start_time_str = details["heure_debut"]
                end_time_str = details["heure_fin"]

                # Parser la date et heure
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

                # Heure de début
                start_hour, start_minute = map(int, start_time_str.split(":"))
                start_dt = datetime.combine(
                    date_obj,
                    datetime.min.time().replace(hour=start_hour, minute=start_minute),
                )
                start_dt = local_tz.localize(start_dt)

                # Heure de fin
                end_hour, end_minute = map(int, end_time_str.split(":"))
                end_dt = datetime.combine(
                    date_obj,
                    datetime.min.time().replace(hour=end_hour, minute=end_minute),
                )
                end_dt = local_tz.localize(end_dt)

                event.add("dtstart", start_dt)
                event.add("dtend", end_dt)

                # Générer un identifiant unique pour l'événement
                event_id = f"{c_key}@ingemedia.fr"
                event.add("uid", event_id)

                # Ajouter l'événement au calendrier
                cal.add_component(event)

            # Sauvegarder le calendrier dans un fichier en mode binaire (important pour ICS)
            os.makedirs(os.path.dirname(chemin_fichier), exist_ok=True)
            with open(chemin_fichier, "wb") as f:  # Utiliser "wb" au lieu de "w"
                f.write(cal.to_ical())  # Ne pas faire de decode

            print(f"Emploi du temps exporté vers {chemin_fichier} (format ICS)")
            return True

        except Exception as e:
            print(f"Erreur lors de l'export ICS: {e}")
            return False

    def exporter_vers_html(
        self,
        emploi_du_temps,
        cours,
        chemin_fichier="output/emploi_du_temps.html",
    ):
        """Exporte l'emploi du temps vers un fichier HTML interactif."""
        if not emploi_du_temps:
            print("Aucune solution trouvée, pas d'export HTML.")
            return False

        try:
            # Créer la structure de base HTML avec CSS
            html = """
            <!DOCTYPE html>
            <html lang="fr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Emploi du temps IngeMedia</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    .calendar { width: 100%; border-collapse: collapse; }
                    .calendar th { background-color: #4CAF50; color: white; padding: 8px; text-align: center; }
                    .calendar td { border: 1px solid #ddd; padding: 8px; height: 100px; vertical-align: top; }
                    .event { margin-bottom: 5px; padding: 5px; border-radius: 4px; overflow: hidden; }
                    .CM { background-color: #e3f2fd; }
                    .TD { background-color: #fff9c4; }
                    .filters { margin-bottom: 20px; }
                    button { padding: 5px 10px; margin-right: 5px; }
                    .hidden { display: none; }
                    .header { background-color: #f5f5f5; position: sticky; top: 0; }
                    @media print {
                        .filters { display: none; }
                        .calendar { font-size: 10px; }
                        .event { page-break-inside: avoid; }
                    }
                </style>
            </head>
            <body>
                <h1>Emploi du temps IngeMedia</h1>
                
                <div class="filters">
                    <h3>Filtres :</h3>
                    <div>
                        <button onclick="filterByType('all')">Tous</button>
                        <button onclick="filterByType('CM')">CM</button>
                        <button onclick="filterByType('TD')">TD</button>
                    </div>
                    <div id="groupe-filters">
                        <h4>Groupes :</h4>
                        <!-- Sera rempli dynamiquement -->
                    </div>
                    <div id="enseignant-filters">
                        <h4>Enseignants :</h4>
                        <!-- Sera rempli dynamiquement -->
                    </div>
                </div>
            """

            # Organiser les données par semaine et jour
            calendar_data = {}
            groupes_uniques = set()
            enseignants_uniques = set()

            for details in emploi_du_temps.values():
                semaine = details["semaine"]
                jour = details["jour"]
                groupe = details["groupe"]
                enseignant = details["enseignant"]

                if semaine not in calendar_data:
                    calendar_data[semaine] = {}

                if jour not in calendar_data[semaine]:
                    calendar_data[semaine][jour] = []

                calendar_data[semaine][jour].append(details)

                for g in groupe.split(", "):
                    groupes_uniques.add(g.strip())

                enseignants_uniques.add(enseignant.strip())

            # Créer les filtres de groupe
            html += """<script>
                function filterByType(type) {
                    const events = document.querySelectorAll('.event');
                    events.forEach(event => {
                        if (type === 'all' || event.classList.contains(type)) {
                            event.classList.remove('hidden');
                        } else {
                            event.classList.add('hidden');
                        }
                    });
                }
                
                function filterByGroupe(groupe) {
                    const events = document.querySelectorAll('.event');
                    events.forEach(event => {
                        if (groupe === 'all' || event.getAttribute('data-groupe').includes(groupe)) {
                            event.classList.remove('hidden');
                        } else {
                            event.classList.add('hidden');
                        }
                    });
                }

                function filterByEnseignant(enseignant) {
                    const events = document.querySelectorAll('.event');
                    events.forEach(event => {
                        if (enseignant === 'all' || event.getAttribute('data-enseignant') === enseignant) {
                            event.classList.remove('hidden');
                        } else {
                            event.classList.add('hidden');
                        }
                    });
                }
            </script>"""

            html += "<script>window.onload = function() {"
            html += "const groupeFilters = document.getElementById('groupe-filters');"
            html += "let filterHtml = '<button onclick=\"filterByGroupe(\\'all\\')\">Tous les groupes</button>';"

            for groupe in sorted(groupes_uniques):
                html += f"filterHtml += '<button onclick=\"filterByGroupe(\\'{groupe}\\')\">{groupe}</button>';"

            html += "groupeFilters.innerHTML = filterHtml;"

            html += "const enseignantFilters = document.getElementById('enseignant-filters');"
            html += "let enseignantFilterHtml = '<button onclick=\"filterByEnseignant(\\'all\\')\">Tous les enseignants</button>';"

            for enseignant in sorted(enseignants_uniques):
                html += f"enseignantFilterHtml += '<button onclick=\"filterByEnseignant(\\'{enseignant}\\')\">{enseignant}</button>';"

            html += "enseignantFilters.innerHTML = enseignantFilterHtml;"
            html += "}</script>"

            # Générer le tableau par semaine
            for semaine in sorted(calendar_data.keys()):
                html += f"<h2>Semaine {semaine}</h2>"
                html += "<table class='calendar'>"
                html += "<tr class='header'><th>Heure</th>"

                for jour in self.JOURS_SEMAINE:
                    if jour in calendar_data[semaine]:
                        date = calendar_data[semaine][jour][0]["date"]
                        html += f"<th>{jour}<br>{date}</th>"
                    else:
                        html += f"<th>{jour}</th>"

                html += "</tr>"

                # Créneaux horaires
                for creneau in self.CRENEAUX_AFFICHAGE:
                    html += f"<tr><td class='header'>{creneau}</td>"

                    for jour in self.JOURS_SEMAINE:
                        html += "<td>"

                        if jour in calendar_data[semaine]:
                            for event in calendar_data[semaine][jour]:
                                if event["creneau"] == creneau:
                                    type_cours = event.get("type", "")
                                    html += f"""<div class='event {type_cours}' data-groupe='{event["groupe"]}' data-enseignant='{event["enseignant"]}'>
                                        <strong>{event["heure_debut"]}-{event["heure_fin"]}</strong>: {event["cours"]}<br>
                                        <small>
                                            Séance: {event["seance"]}<br>
                                            {type_cours} - {event["salle"]}<br>
                                            {event["enseignant"]}<br>
                                            Groupe: {event["groupe"]}
                                        </small>
                                    </div>"""

                        html += "</td>"

                    html += "</tr>"

                html += "</table>"

            html += """
            </body>
            </html>
            """

            # Enregistrer le fichier HTML
            os.makedirs(os.path.dirname(chemin_fichier), exist_ok=True)
            with open(chemin_fichier, "w", encoding="utf-8") as f:
                f.write(html)

            print(f"Emploi du temps exporté vers {chemin_fichier} (format HTML)")
            return True

        except Exception as e:
            print(f"Erreur lors de l'export HTML: {e}")
            return False


def expliquer_infeasibilite(model, solver):
    """Explique pourquoi le modèle est infaisable."""
    print("\n=== Analyse des conflits ===")
    infeasibility_report = solver.ResponseStats()
    print(infeasibility_report)
    print("=== Fin de l'analyse ===")


# Exemple d'utilisation
if __name__ == "__main__":
    # Chargement des données depuis les fichiers CSV
    try:
        salles = charger_salles()
        print(f"Chargement de {len(salles)} salles")

        enseignants = charger_enseignants()
        print(f"Chargement de {len(enseignants)} enseignants")

        groupes = charger_groupes()
        print(f"Chargement de {len(groupes)} groupes")

        cours = charger_cours(enseignants=enseignants, groupes=groupes)
        print(f"Chargement de {len(cours)} cours")

        # Générer les séances à partir des cours
        seances = generer_seance(cours, groupes)
        print(f"Génération de {len(seances)} séances")

        # Jours fériés en septembre 2025 (aucun)
        jours_feries = holidays.France(years=[2024, 2025])

        # Pour afficher tous les jours fériés récupérés
        print("Liste des jours fériés pour l'année scolaire:")
        for date, nom in sorted(jours_feries.items()):
            print(f"- {date.strftime('%d/%m/%Y')} : {nom}")

        # Génération de l'emploi du temps à partir du 12 septembre 2025
        scheduler = EmploiDuTemps(
            annee=2025,
            mois=9,
            semaines=[
                37,
                38,
                39,
                41,
                42,
                43,
                45,
                46,
                47,
                48,
                50,
                51,
                1,
                2,
                3,
                4,
                5,
                6,
            ],  # Semaines du 9 septembre 2025 au 16 janvier 2026 (exclusions appliquées)
            jours_feries=jours_feries,
            date_debut="2025-09-09",  # Commencer le 9 septembre
            date_fin="2026-01-16",
        )

        print("Génération de l'emploi du temps à partir du 12 septembre 2025...")
        # Utiliser les séances au lieu des cours directement
        edt = scheduler.generer(seances, salles, enseignants, groupes)

        print("Export de l'emploi du temps vers un fichier ICS...")
        # Export vers ICS (iCalendar)
        scheduler.exporter_vers_ics(
            edt, cours, "output/emploi_du_temps_septembre2025.ics"
        )
        print("Export de l'emploi du temps vers un fichier HTML interactif...")
        scheduler.exporter_vers_html(
            edt, cours, "output/emploi_du_temps_septembre2025.html"
        )

        print("Fin de la génération de l'emploi du temps.")
    except FileNotFoundError as e:
        print(f"Erreur: Fichier non trouvé - {e}")
    except Exception as e:
        print(f"Erreur: {e}")
        traceback.print_exc()
