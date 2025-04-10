class Salle:
    """Représente une salle de classe avec ses caractéristiques."""

    def __init__(
        self, id, nom, effectif_max, type_salle="standard", disponibilite=None
    ):
        """
        Initialise une salle de classe.

        Args:
            id: Identifiant unique de la salle
            nom: Nom de la salle (ex: "B202")
            effectif_max: Nombre maximum d'étudiants
            type_salle: Type de salle (standard, amphi, labo, etc.)
            disponibilite: Dictionnaire représentant la disponibilité de la salle.
                           Ex: {
                               "lundi": {"matin": True, "apres_midi": False},
                               "mardi": {"matin": False, "apres_midi": True},
                               ...
                           }
                           Si None, la salle est considérée comme toujours disponible.
        """
        self.id = id
        self.nom = nom
        self.effectif_max = effectif_max
        self.type_salle = type_salle
        self.disponibilite = disponibilite

    def est_disponible(self, jour, periode):
        """
        Vérifie si la salle est disponible à un jour et période donnés.

        Args:
            jour: Jour de la semaine (ex: "lundi")
            periode: Période de la journée ("matin" ou "apres_midi")

        Returns:
            True si la salle est disponible, False sinon.
        """
        if self.disponibilite is None:
            return True  # Salle toujours disponible

        if jour not in self.disponibilite:
            return False  # Jour non défini, donc non disponible

        if periode not in self.disponibilite[jour]:
            return False  # Période non définie pour ce jour

        return self.disponibilite[jour][periode]

    def __str__(self):
        return (
            f"Salle {self.nom} (capacité: {self.effectif_max}, type: {self.type_salle})"
        )


class Enseignant:
    """Représente un enseignant."""

    def __init__(
        self,
        id,
        nom,
        besoin_salle,
        semaine_paire=True,
        semaine_impaire=True,
        disponibilite=None,
    ):
        """
        Initialise un enseignant.

        Args:
            id: Identifiant unique de l'enseignant
            nom: Nom de l'enseignant
            besoin_salle: Type de salle dont l'enseignant a besoin (standard, amphi, labo, etc.)
            semaine_paire: True si l'enseignant est disponible les semaines paires, False sinon.
            semaine_impaire: True si l'enseignant est disponible les semaines impaires, False sinon.
            disponibilite: Dictionnaire représentant la disponibilité de l'enseignant.
                           Ex: {
                               "lundi": {"matin": True, "apres_midi": False},
                               "mardi": {"matin": False, "apres_midi": True},
                               ...
                           }
                           Si None, l'enseignant est considéré comme toujours disponible.
        """
        self.id = id
        self.nom = nom
        self.besoin_salle = besoin_salle
        self.semaine_paire = semaine_paire
        self.semaine_impaire = semaine_impaire
        self.disponibilite = disponibilite

    def est_disponible(self, jour, periode):
        """
        Vérifie si l'enseignant est disponible à un jour et période donnés.

        Args:
            jour: Jour de la semaine (ex: "lundi")
            periode: Période de la journée ("matin" ou "apres_midi")

        Returns:
            True si l'enseignant est disponible, False sinon.
        """
        if self.disponibilite is None:
            return True  # Enseignant toujours disponible

        if jour not in self.disponibilite:
            return False  # Jour non défini, donc non disponible

        if periode not in self.disponibilite[jour]:
            return False  # Période non définie pour ce jour

        return self.disponibilite[jour][periode]

    def __str__(self):
        return f"Enseignant {self.nom} (besoin salle: {self.besoin_salle})"


class Groupe:
    """Représente un groupe d'étudiants."""

    def __init__(self, id_groupe, nom, effectif=0, id_parent=None, sous_groupes=None):
        """
        Initialise un groupe d'étudiants.

        Args:
            id_groupe: Identifiant unique du groupe
            nom: Nom du groupe (ex: "Master CDE")
            effectif: (optionnel) Nombre d'étudiants dans le groupe
            id_parent: (optionnel) Identifiant du groupe parent
            sous_groupes: (optionnel) Liste de sous-groupes
        """
        self.id = id_groupe  # Pour compatibilité avec le reste du code
        self.id_groupe = id_groupe
        self.nom = nom
        self.effectif = effectif
        self.id_parent = id_parent
        self.sous_groupes = sous_groupes if sous_groupes is not None else []

        # Calculer l'effectif si non fourni mais qu'il y a des sous-groupes
        if self.effectif == 0 and self.sous_groupes:
            self.effectif = self.total_effectif()

    def total_effectif(self):
        """
        Calcule l'effectif total en tenant compte des sous-groupes.
        Si le groupe a des sous-groupes, l'effectif total sera la somme des effectifs des sous-groupes.
        """
        if self.sous_groupes:
            return sum(sg.effectif for sg in self.sous_groupes)
        return self.effectif

    def __str__(self):
        effectif = self.total_effectif()
        parent_info = f", parent: {self.id_parent}" if self.id_parent else ""
        return f"Groupe {self.nom} (id: {self.id_groupe}, effectif: {effectif}{parent_info})"


class Cours:
    """Représente un cours."""

    def __init__(
        self, id_cours, nom, enseignant, groupes, duree_total, max_duration, type_cours
    ):
        """
        Initialise un cours.

        Args:
            id: Identifiant unique du cours
            nom: Nom du cours (ex: "Mathématiques")
            enseignant: Enseignant responsable du cours
            groupes: Liste de groupes d'étudiants inscrits au cours
            type_cours: Type de cours (TD, TP, CM, etc.)
            duree_total: Durée totale du cours en heures
            max_duration: Durée maximale d'une séance (en heures)
            type_cours: Type de cours (TD, TP, CM, etc.)
        """
        self.id_cours = id_cours
        self.nom = nom
        self.enseignant = enseignant
        self.groupes = groupes  # Liste de groupes
        self.duree_total = duree_total
        self.max_duration = max_duration
        self.type_cours = type_cours

    def __str__(self):
        groupes_str = ", ".join([g.nom for g in self.groupes])
        return f"Cours {self.nom} (enseignant: {self.enseignant.nom}, groupes: {groupes_str},type: {self.type_cours})"


class Seance:
    """Classe pour modéliser une séance."""

    def __init__(self, id_seance, cours, duree, groupes, type_seance=None):
        """
        Initialise une séance.

        Args:
            id_seance: Identifiant unique de la séance
            cours: Objet Cours auquel cette séance est associée
            duree: Durée de la séance en heures
            groupes: Liste des groupes participant à cette séance ou un seul groupe
            type_seance: Type de la séance (optionnel)
        """
        self.id_seance = id_seance
        self.cours = cours
        self.duree = duree

        # Assurer que groupes est toujours une liste
        if not isinstance(groupes, list):
            self.groupes = [groupes]
        else:
            self.groupes = groupes

        # Si type_seance n'est pas fourni, utiliser le type du cours
        self.type_seance = type_seance if type_seance else cours.type_cours
