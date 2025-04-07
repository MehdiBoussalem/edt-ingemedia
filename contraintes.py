"""Module contenant les contraintes pour la génération d'emploi du temps."""


def ajouter_contrainte_seance_unique(
    model, seance_vars, seances, salles, nb_semaines, nb_jours, nb_creneaux_30min
):
    """Contrainte 1: Chaque séance doit être planifiée exactement une fois dans le mois."""
    for s in seances:
        model.Add(
            sum(
                seance_vars.get((s.id_seance, s_idx, j, cr_debut, sa.id), 0)
                for s_idx in range(nb_semaines)
                for j in range(nb_jours)
                for cr_debut in range(nb_creneaux_30min)
                for sa in salles
                if (s.id_seance, s_idx, j, cr_debut, sa.id) in seance_vars
            )
            == 1  # Chaque séance est planifiée exactement une fois
        )


def ajouter_contrainte_enseignant_unicite(
    model,
    seance_vars,
    seances,
    salles,
    calendrier,
    semaines,
    nb_jours,
    nb_creneaux_30min,
    enseignants,
):
    """Contrainte 2: Un enseignant ne peut pas donner deux séances qui se chevauchent."""
    for e in enseignants:
        for s_idx in range(len(semaines)):
            for j in range(nb_jours):
                # Vérifier si le jour est disponible (non férié)
                if calendrier[semaines[s_idx]][j] is None:
                    continue

                for cr in range(nb_creneaux_30min):
                    # Trouver toutes les séances de cet enseignant qui utilisent ce créneau
                    seances_utilisant_creneau = []

                    for s in seances:
                        if s.cours.enseignant.id == e.id:
                            duree_creneaux = int(
                                s.duree * 60 / 30
                            )  # Convertir heures en créneaux de 30 min

                            for cr_debut in range(
                                max(0, cr - duree_creneaux + 1), cr + 1
                            ):
                                for sa in salles:
                                    if (
                                        s.id_seance,
                                        s_idx,
                                        j,
                                        cr_debut,
                                        sa.id,
                                    ) in seance_vars:
                                        seances_utilisant_creneau.append(
                                            seance_vars[
                                                (s.id_seance, s_idx, j, cr_debut, sa.id)
                                            ]
                                        )

                    if len(seances_utilisant_creneau) > 1:
                        model.Add(sum(seances_utilisant_creneau) <= 1)


def ajouter_contrainte_groupe_unicite(
    model,
    seance_vars,
    seances,
    salles,
    calendrier,
    semaines,
    nb_jours,
    nb_creneaux_30min,
    groupes,
):
    """
    Contrainte 3: Un groupe ne peut pas suivre deux séances qui se chevauchent.
    Un groupe parent et ses sous-groupes ne peuvent pas avoir cours en même temps.
    """
    # Créer un dictionnaire pour stocker les relations parent-enfant
    relations_groupes = {}

    # Créer un dictionnaire inverse pour trouver facilement le parent d'un groupe
    relations_inverse = {}

    for g in groupes:
        if hasattr(g, "sous_groupes") and g.sous_groupes:
            sous_groupes_ids = [sg.id_groupe for sg in g.sous_groupes]
            relations_groupes[g.id_groupe] = sous_groupes_ids

            for sg in g.sous_groupes:
                relations_inverse[sg.id_groupe] = g.id_groupe

    # Pour chaque créneau horaire, vérifier les conflits
    total_contraintes_ajoutees = 0

    for s_idx in range(len(semaines)):
        semaine = semaines[s_idx]

        for j in range(nb_jours):
            # Vérifier si le jour est disponible (non férié)
            if calendrier[semaine][j] is None:
                continue

            for cr in range(nb_creneaux_30min):
                # Dictionnaire pour stocker les séances par groupe
                groupes_seances = {}

                # Parcourir toutes les séances
                for s in seances:
                    duree_creneaux = int(s.duree * 60 / 30)

                    # Pour chaque groupe participant à cette séance
                    try:
                        if not hasattr(s, "groupes") or not isinstance(s.groupes, list):
                            continue

                        for groupe in s.groupes:
                            if not hasattr(groupe, "id_groupe"):
                                continue

                            groupe_id = groupe.id_groupe

                            # Vérifier si cette séance utilise le créneau actuel
                            for cr_debut in range(
                                max(0, cr - duree_creneaux + 1), cr + 1
                            ):
                                if cr_debut < 0 or cr_debut >= nb_creneaux_30min:
                                    continue

                                for sa in salles:
                                    key = (s.id_seance, s_idx, j, cr_debut, sa.id)
                                    if key in seance_vars:
                                        if groupe_id not in groupes_seances:
                                            groupes_seances[groupe_id] = []

                                        groupes_seances[groupe_id].append(
                                            (
                                                seance_vars[key],
                                                cr_debut,
                                                cr_debut + duree_creneaux - 1,
                                                s.id_seance,  # Stocker l'ID de la séance
                                            )
                                        )
                    except Exception:
                        pass

                # 1. Contrainte : un même groupe ne peut pas avoir plus d'une séance à la fois
                for groupe_id, seances_groupe in groupes_seances.items():
                    if len(seances_groupe) > 1:
                        model.Add(sum(var[0] for var in seances_groupe) <= 1)
                        total_contraintes_ajoutees += 1

                # 2. Contrainte : un groupe parent et ses sous-groupes ne peuvent pas avoir cours en même temps
                for parent_id, enfants_ids in relations_groupes.items():
                    if parent_id in groupes_seances:
                        seances_parent = groupes_seances[parent_id]

                        for enfant_id in enfants_ids:
                            if enfant_id in groupes_seances:
                                seances_enfant = groupes_seances[enfant_id]

                                for sp_idx, (
                                    sp,
                                    debut_p,
                                    fin_p,
                                    id_seance_p,
                                ) in enumerate(seances_parent):
                                    for se_idx, (
                                        se,
                                        debut_e,
                                        fin_e,
                                        id_seance_e,
                                    ) in enumerate(seances_enfant):
                                        # Vérifier si c'est la même séance (cas d'un CM avec parent et enfant)
                                        if id_seance_p != id_seance_e:
                                            # Contrainte simple : pas de chevauchement
                                            model.Add(sp + se <= 1)
                                            total_contraintes_ajoutees += 1

                                            # Contrainte temporelle bidirectionnelle :
                                            if fin_e >= debut_p:
                                                model.Add(se + sp <= 1)
                                                total_contraintes_ajoutees += 1
                                                model.Add(sp + se <= 1)
                                                total_contraintes_ajoutees += 1

    return total_contraintes_ajoutees


def ajouter_contrainte_salle_unicite(
    model,
    seance_vars,
    seances,
    salles,
    calendrier,
    semaines,
    nb_jours,
    nb_creneaux_30min,
):
    """Contrainte 4: Une salle ne peut pas accueillir deux séances qui se chevauchent."""
    for sa in salles:
        for s_idx in range(len(semaines)):
            for j in range(nb_jours):
                # Vérifier si le jour est disponible (non férié)
                if calendrier[semaines[s_idx]][j] is None:
                    continue

                for cr in range(nb_creneaux_30min):
                    # Trouver toutes les séances dans cette salle qui utilisent ce créneau
                    seances_utilisant_creneau = []

                    for s in seances:
                        duree_creneaux = int(
                            s.duree * 60 / 30
                        )  # Convertir heures en créneaux de 30 min

                        for cr_debut in range(max(0, cr - duree_creneaux + 1), cr + 1):
                            if (s.id_seance, s_idx, j, cr_debut, sa.id) in seance_vars:
                                seances_utilisant_creneau.append(
                                    seance_vars[
                                        (s.id_seance, s_idx, j, cr_debut, sa.id)
                                    ]
                                )

                    if len(seances_utilisant_creneau) > 1:
                        model.Add(sum(seances_utilisant_creneau) <= 1)


def ajouter_contrainte_pause_dejeuner_enseignant(
    model,
    seance_vars,
    seances,
    salles,
    calendrier,
    semaines,
    nb_jours,
    enseignants,
    pause_debut,
    pause_fin,
):
    """Contrainte 5: Pause déjeuner pour chaque enseignant - OBLIGATOIRE 1h entre 12h et 14h."""
    for e in enseignants:
        for s_idx in range(len(semaines)):
            for j in range(nb_jours):
                # Vérifier si le jour est disponible (non férié)
                if calendrier[semaines[s_idx]][j] is None:
                    continue

                # Variables pour indiquer si un créneau est utilisé par l'enseignant
                creneau_utilise = {}
                for cr in range(pause_debut, pause_fin + 1):
                    utilisation = []
                    for s in seances:
                        if s.cours.enseignant.id == e.id:
                            duree_creneaux = int(
                                s.duree * 60 / 30
                            )  # Convertir heures en créneaux de 30 min

                            for cr_debut in range(
                                max(0, cr - duree_creneaux + 1), cr + 1
                            ):
                                for sa in salles:
                                    if (
                                        s.id_seance,
                                        s_idx,
                                        j,
                                        cr_debut,
                                        sa.id,
                                    ) in seance_vars:
                                        utilisation.append(
                                            seance_vars[
                                                (s.id_seance, s_idx, j, cr_debut, sa.id)
                                            ]
                                        )

                    # Si aucune séance n'utilise ce créneau, il est libre
                    if utilisation:
                        creneau_utilise[cr] = model.NewBoolVar(
                            f"enseignant_{e.id}_semaine_{s_idx}_jour_{j}_creneau_{cr}_utilise"
                        )
                        model.Add(sum(utilisation) >= 1).OnlyEnforceIf(
                            creneau_utilise[cr]
                        )
                        model.Add(sum(utilisation) == 0).OnlyEnforceIf(
                            creneau_utilise[cr].Not()
                        )
                    else:
                        creneau_utilise[cr] = model.NewConstant(0)

                # Nous avons besoin d'au moins 2 créneaux consécutifs libres (1h)
                # Vérifier toutes les possibilités de 2 créneaux consécutifs
                pause_valide = model.NewBoolVar(
                    f"pause_dejeuner_valide_{e.id}_{s_idx}_{j}"
                )

                # Différentes possibilités pour 1h de pause
                options_pause = []
                for start in range(pause_debut, pause_fin):
                    option = model.NewBoolVar(
                        f"pause_option_{e.id}_{s_idx}_{j}_{start}"
                    )
                    # Deux créneaux consécutifs doivent être libres
                    model.AddBoolAnd(
                        [
                            creneau_utilise[start].Not(),
                            creneau_utilise[start + 1].Not(),
                        ]
                    ).OnlyEnforceIf(option)

                    # Si cette option n'est pas choisie, au moins un des créneaux est utilisé
                    model.AddBoolOr(
                        [creneau_utilise[start], creneau_utilise[start + 1]]
                    ).OnlyEnforceIf(option.Not())

                    options_pause.append(option)

                # Au moins une des options de pause doit être valide
                model.AddBoolOr(options_pause).OnlyEnforceIf(pause_valide)
                model.AddBoolAnd(
                    [option.Not() for option in options_pause]
                ).OnlyEnforceIf(pause_valide.Not())

                # Rendre la pause obligatoire
                model.Add(pause_valide == 1)


def ajouter_contrainte_pause_dejeuner_groupe(
    model,
    seance_vars,
    seances,
    salles,
    calendrier,
    semaines,
    nb_jours,
    groupes,
    pause_debut,
    pause_fin,
):
    """Contrainte 6: Pause déjeuner pour chaque groupe - OBLIGATOIRE 1h entre 12h et 14h."""
    for g in groupes:
        for s_idx in range(len(semaines)):
            for j in range(nb_jours):
                # Vérifier si le jour est disponible (non férié)
                if calendrier[semaines[s_idx]][j] is None:
                    continue

                # Variables pour indiquer si un créneau est utilisé par le groupe
                creneau_utilise = {}
                for cr in range(pause_debut, pause_fin + 1):
                    utilisation = []
                    for s in seances:
                        # Vérifier si le groupe fait partie des groupes de la séance
                        groupe_present = False

                        if isinstance(s.groupes, list):
                            # Si c'est une liste, vérifier si le groupe est dans la liste
                            for groupe_seance in s.groupes:
                                if groupe_seance.id_groupe == g.id_groupe:
                                    groupe_present = True
                                    break
                        else:
                            # Si c'est un objet unique, comparer les ID
                            if (
                                hasattr(s.groupes, "id_groupe")
                                and s.groupes.id_groupe == g.id_groupe
                            ):
                                groupe_present = True

                        if groupe_present:
                            duree_creneaux = int(
                                s.duree * 60 / 30
                            )  # Convertir heures en créneaux de 30 min

                            for cr_debut in range(
                                max(0, cr - duree_creneaux + 1), cr + 1
                            ):
                                for sa in salles:
                                    if (
                                        s.id_seance,
                                        s_idx,
                                        j,
                                        cr_debut,
                                        sa.id,
                                    ) in seance_vars:
                                        utilisation.append(
                                            seance_vars[
                                                (s.id_seance, s_idx, j, cr_debut, sa.id)
                                            ]
                                        )

                    if utilisation:
                        creneau_utilise[cr] = model.NewBoolVar(
                            f"groupe_{g.id_groupe}_semaine_{s_idx}_jour_{j}_creneau_{cr}_utilise"
                        )
                        model.Add(sum(utilisation) >= 1).OnlyEnforceIf(
                            creneau_utilise[cr]
                        )
                        model.Add(sum(utilisation) == 0).OnlyEnforceIf(
                            creneau_utilise[cr].Not()
                        )
                    else:
                        creneau_utilise[cr] = model.NewConstant(0)

                # Nous avons besoin d'au moins 2 créneaux consécutifs libres (1h)
                pause_valide = model.NewBoolVar(
                    f"pause_dejeuner_valide_groupe_{g.id_groupe}_{s_idx}_{j}"
                )

                # Différentes possibilités pour 1h de pause
                options_pause = []
                for start in range(pause_debut, pause_fin):
                    option = model.NewBoolVar(
                        f"pause_option_groupe_{g.id_groupe}_{s_idx}_{j}_{start}"
                    )
                    # Deux créneaux consécutifs doivent être libres
                    model.AddBoolAnd(
                        [
                            creneau_utilise[start].Not(),
                            creneau_utilise[start + 1].Not(),
                        ]
                    ).OnlyEnforceIf(option)

                    # Si cette option n'est pas choisie, au moins un des créneaux est utilisé
                    model.AddBoolOr(
                        [creneau_utilise[start], creneau_utilise[start + 1]]
                    ).OnlyEnforceIf(option.Not())

                    options_pause.append(option)

                # Au moins une des options de pause doit être valide
                model.AddBoolOr(options_pause).OnlyEnforceIf(pause_valide)
                model.AddBoolAnd(
                    [option.Not() for option in options_pause]
                ).OnlyEnforceIf(pause_valide.Not())

                # Rendre la pause obligatoire
                model.Add(pause_valide == 1)


def ajouter_toutes_contraintes(
    model,
    seance_vars,
    seances,
    salles,
    calendrier,
    semaines,
    nb_jours,
    nb_creneaux_30min,
    enseignants,
    groupes,
    pause_debut=8,  # 12h00 (=8h00 + 4h00)
    pause_fin=12,  # 14h00 (=8h00 + 6h00)
):
    """
    Ajoute toutes les contraintes nécessaires au modèle d'emploi du temps.

    Args:
        model: Modèle CP-SAT
        seance_vars: Dictionnaire des variables de décision
        seances: Liste des séances à planifier
        salles: Liste des salles disponibles
        calendrier: Structure représentant le calendrier
        semaines: Liste des semaines à planifier
        nb_jours: Nombre de jours par semaine
        nb_creneaux_30min: Nombre de créneaux de 30 minutes par jour
        enseignants: Liste des enseignants
        groupes: Liste des groupes d'étudiants
        pause_debut: Indice du créneau de début de la pause déjeuner (défaut: 8 = 12h00)
        pause_fin: Indice du créneau de fin de la pause déjeuner (défaut: 12 = 14h00)
    """

    # 1. Chaque séance doit être planifiée exactement une fois
    print("Ajout de la contrainte de séance unique...")
    ajouter_contrainte_seance_unique(
        model, seance_vars, seances, salles, len(semaines), nb_jours, nb_creneaux_30min
    )

    # 2. Un enseignant ne peut pas donner deux séances qui se chevauchent
    print("Ajout de la contrainte d'unicité pour les enseignants...")
    ajouter_contrainte_enseignant_unicite(
        model,
        seance_vars,
        seances,
        salles,
        calendrier,
        semaines,
        nb_jours,
        nb_creneaux_30min,
        enseignants,
    )

    # 3. Un groupe ne peut pas suivre deux séances qui se chevauchent
    print("Ajout de la contrainte d'unicité pour les groupes...")
    ajouter_contrainte_groupe_unicite(
        model,
        seance_vars,
        seances,
        salles,
        calendrier,
        semaines,
        nb_jours,
        nb_creneaux_30min,
        groupes,
    )

    # 4. Une salle ne peut pas accueillir deux séances qui se chevauchent
    print("Ajout de la contrainte d'unicité pour les salles...")
    ajouter_contrainte_salle_unicite(
        model,
        seance_vars,
        seances,
        salles,
        calendrier,
        semaines,
        nb_jours,
        nb_creneaux_30min,
    )

    # 5. Pause déjeuner pour chaque enseignant
    print("Ajout de la contrainte de pause déjeuner pour les enseignants...")
    ajouter_contrainte_pause_dejeuner_enseignant(
        model,
        seance_vars,
        seances,
        salles,
        calendrier,
        semaines,
        nb_jours,
        enseignants,
        pause_debut,
        pause_fin,
    )

    # 6. Pause déjeuner pour chaque groupe*
    print("Ajout de la contrainte de pause déjeuner pour les groupes...")
    ajouter_contrainte_pause_dejeuner_groupe(
        model,
        seance_vars,
        seances,
        salles,
        calendrier,
        semaines,
        nb_jours,
        groupes,
        pause_debut,
        pause_fin,
    )

    print("Toutes les contraintes ont été ajoutées au modèle.")
