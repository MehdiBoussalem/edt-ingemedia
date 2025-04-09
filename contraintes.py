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
    calendrier,
    semaines,
    nb_jours,
    nb_creneaux_30min,
    groupes,
    salles,
):
    """
    Version optimisée avec moins de contraintes en mémoire,
    tenant compte des relations parent-enfant entre les groupes.
    """
    contraintes_ajoutees = 0

    # Créer un dictionnaire pour retrouver rapidement les sous-groupes d'un groupe
    sous_groupes_par_parent = {}
    for groupe in groupes:
        if hasattr(groupe, "sous_groupes") and groupe.sous_groupes:
            sous_groupes_par_parent[groupe.id_groupe] = [
                sg.id_groupe for sg in groupe.sous_groupes
            ]

    # Regrouper les variables par créneau horaire pour chaque groupe
    for s_idx in range(len(semaines)):
        for j in range(nb_jours):
            if calendrier[semaines[s_idx]][j] is None:
                continue

            # Créer un dictionnaire indexé par (groupe_id, créneau)
            groupe_creneau_vars = {}

            # Remplir le dictionnaire
            for (s_id, si, jour, cr_debut, sa_id), var in seance_vars.items():
                if si == s_idx and jour == j:
                    s = next(
                        (seance for seance in seances if seance.id_seance == s_id), None
                    )
                    if s:
                        duree_creneaux = int(s.duree * 60 / 30)
                        groupes_seance = (
                            s.groupes if isinstance(s.groupes, list) else [s.groupes]
                        )

                        for g in groupes_seance:
                            # Pour chaque créneau occupé par la séance
                            for cr in range(cr_debut, cr_debut + duree_creneaux):
                                # Ajouter une contrainte pour le groupe lui-même
                                key = (g.id_groupe, cr)
                                if key not in groupe_creneau_vars:
                                    groupe_creneau_vars[key] = []
                                groupe_creneau_vars[key].append(var)

                                # Si le groupe a des sous-groupes, ajouter aussi la contrainte pour eux
                                if g.id_groupe in sous_groupes_par_parent:
                                    for sous_groupe_id in sous_groupes_par_parent[
                                        g.id_groupe
                                    ]:
                                        key_sous_groupe = (sous_groupe_id, cr)
                                        if key_sous_groupe not in groupe_creneau_vars:
                                            groupe_creneau_vars[key_sous_groupe] = []
                                        groupe_creneau_vars[key_sous_groupe].append(var)

            # Ajouter une contrainte pour chaque groupe/créneau avec plusieurs variables
            for (g_id, cr), vars_list in groupe_creneau_vars.items():
                if len(vars_list) > 1:
                    model.Add(sum(vars_list) <= 1)
                    contraintes_ajoutees += 1

    print(
        f"Contraintes d'unicité optimisées pour les groupes: {contraintes_ajoutees} contraintes ajoutées"
    )
    return contraintes_ajoutees


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


def ajouter_contrainte_capacite_salle(
    model,
    seance_vars,
    seances,
    salles,
    calendrier,
    semaines,
    nb_jours,
    nb_creneaux_30min,
):
    """
    Contrainte: La capacité de la salle doit être suffisante pour accueillir tous les groupes participant à la séance.
    """
    contraintes_ajoutees = 0

    for s in seances:
        # Calculer l'effectif total des groupes participant à la séance
        effectif_total = 0
        for groupe in s.groupes:
            effectif_total += groupe.effectif

        for sa in salles:
            # Si la capacité de la salle est inférieure à l'effectif total,
            # on empêche l'affectation de cette séance à cette salle
            if sa.effectif_max < effectif_total:
                for s_idx in range(len(semaines)):
                    for j in range(nb_jours):
                        for cr_debut in range(nb_creneaux_30min):
                            if (s.id_seance, s_idx, j, cr_debut, sa.id) in seance_vars:
                                model.Add(
                                    seance_vars[
                                        (s.id_seance, s_idx, j, cr_debut, sa.id)
                                    ]
                                    == 0
                                )
                                contraintes_ajoutees += 1

    print(
        f"Contraintes de capacité des salles: {contraintes_ajoutees} contraintes ajoutées"
    )
    return contraintes_ajoutees


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
        calendrier,  # Modifier l'ordre ici
        semaines,
        nb_jours,
        nb_creneaux_30min,
        groupes,
        salles,  # Mettre salles en dernier
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
    # 7. Contrainte de capacité des salles
    print("Ajout de la contrainte de capacité des salles...")
    ajouter_contrainte_capacite_salle(
        model,
        seance_vars,
        seances,
        salles,
        calendrier,
        semaines,
        nb_jours,
        nb_creneaux_30min,
    )
    print("Toutes les contraintes ont été ajoutées au modèle.")
