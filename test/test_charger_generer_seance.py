import os
import sys
import unittest
import csv

# Ajout du répertoire parent au chemin pour l'importation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import charger_cours, charger_enseignants, charger_groupes, generer_seance
from model import Seance


class TestGenererSeance(unittest.TestCase):

    def setUp(self):
        """Configure le chemin vers les fichiers de données et charge les dépendances."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Chemins des fichiers
        self.fichier_cours = os.path.join(base_dir, "data", "cours.csv")
        self.fichier_enseignants = os.path.join(base_dir, "data", "enseignants.csv")
        self.fichier_groupes = os.path.join(base_dir, "data", "groupe.csv")

        # Vérifier que les fichiers existent
        self.assertTrue(
            os.path.exists(self.fichier_cours),
            f"Le fichier {self.fichier_cours} n'existe pas",
        )
        self.assertTrue(
            os.path.exists(self.fichier_enseignants),
            f"Le fichier {self.fichier_enseignants} n'existe pas",
        )
        self.assertTrue(
            os.path.exists(self.fichier_groupes),
            f"Le fichier {self.fichier_groupes} n'existe pas",
        )

        # Charger les dépendances
        self.enseignants = charger_enseignants(self.fichier_enseignants)
        self.groupes = charger_groupes(self.fichier_groupes)
        self.cours = charger_cours(self.fichier_cours, self.enseignants, self.groupes)

    def test_generation_seances(self):
        """Test de base de la génération de séances."""
        seances = generer_seance(self.cours, self.groupes)

        # Vérification du nombre total de séances
        expected_total_seances = 35  # Nombre total attendu de séances
        self.assertEqual(
            len(seances),
            expected_total_seances,
            f"Le nombre de séances générées devrait être {expected_total_seances}, mais est de {len(seances)}",
        )

        # Calculer la répartition des séances par type
        seances_cm = [s for s in seances if s.cours.type_cours == "CM"]
        seances_td = [s for s in seances if s.cours.type_cours == "TD"]

        # Vérifier la répartition
        expected_cm = 25  # Nombre attendu de séances CM
        expected_td = 10  # Nombre attendu de séances TD
        self.assertEqual(
            len(seances_cm),
            expected_cm,
            f"Le nombre de séances CM devrait être {expected_cm}, mais est de {len(seances_cm)}",
        )
        self.assertEqual(
            len(seances_td),
            expected_td,
            f"Le nombre de séances TD devrait être {expected_td}, mais est de {len(seances_td)}",
        )

        # Afficher des informations de diagnostic détaillées
        print("\nRépartition des séances générées :")
        print(f"Total: {len(seances)} séances (attendu: {expected_total_seances})")
        print(f"  - CM: {len(seances_cm)} séances (attendu: {expected_cm})")
        print(f"  - TD: {len(seances_td)} séances (attendu: {expected_td})")

        # Compter les séances par cours
        seances_par_cours = {}
        for s in seances:
            cours_id = s.cours.id_cours
            if cours_id not in seances_par_cours:
                seances_par_cours[cours_id] = []
            seances_par_cours[cours_id].append(s.id_seance)

        # Afficher le nombre de séances par cours
        print("\nNombre de séances par cours :")
        for cours_id, seances_ids in seances_par_cours.items():
            cours = next((c for c in self.cours if c.id_cours == cours_id), None)
            if cours:
                print(
                    f"  - Cours {cours_id} ({cours.nom}, {cours.type_cours}): {len(seances_ids)} séances"
                )
                for seance_id in seances_ids:
                    print(f"      - {seance_id}")

        # Afficher la liste des séances pour débogage
        print("\nListe des séances générées :")
        print("-" * 100)
        print(
            f"{'ID SÉANCE':<25} {'COURS':<15} {'TYPE':<5} {'DURÉE':<10} {'GROUPE':<25} {'EFFECTIF':<10}"
        )
        print("-" * 100)
        for s in seances:
            print(
                f"{s.id_seance:<25} {s.cours.nom:<15} {s.cours.type_cours:<5} {s.duree:<10} {s.groupes.nom:<25} {s.groupes.effectif:<10}"
            )
        print("-" * 100)

        # Vérifier que chaque séance a les attributs attendus
        for s in seances:
            self.assertTrue(hasattr(s, "id_seance"))
            self.assertTrue(hasattr(s, "cours"))
            self.assertTrue(hasattr(s, "duree"))
            self.assertTrue(hasattr(s, "groupes"))

            # Vérifier la référence au cours
            self.assertIsNotNone(s.cours)

            # Vérifier le groupe
            self.assertIsNotNone(s.groupes)
            self.assertTrue(hasattr(s.groupes, "effectif"))
            self.assertGreater(s.groupes.effectif, 0)

    def test_seances_cm(self):
        """Vérifie que les séances de type CM sont correctement générées."""
        seances = generer_seance(self.cours, self.groupes)

        # Identifier les séances de type CM
        seances_cm = [s for s in seances if s.cours.type_cours == "CM"]

        # Vérifier qu'il y a le bon nombre de séances CM
        expected_cm = 25  # Ajustez selon vos données
        self.assertEqual(
            len(seances_cm),
            expected_cm,
            f"Il devrait y avoir {expected_cm} séances CM, mais il y en a {len(seances_cm)}",
        )

        # Pour chaque CM, vérifier que le groupe contient tous les groupes concernés
        for seance in seances_cm:
            self.assertEqual(seance.cours.type_cours, "CM")

            # Si plusieurs groupes étaient associés au cours, on a normalement un groupe composite
            # qui a un ID commençant par "COMP_"
            if len(seance.cours.ids_groupes) > 1:
                self.assertTrue(
                    seance.groupes.id_groupe.startswith("COMP_"),
                    f"Le groupe de la séance CM {seance.id_seance} devrait être composite",
                )

            # Vérifier que l'effectif total est positif
            self.assertGreater(
                seance.groupes.effectif,
                0,
                f"L'effectif du groupe pour la séance CM {seance.id_seance} est 0",
            )

    def test_structure_ids_seances(self):
        """Vérifie que les IDs des séances sont correctement structurés."""
        seances = generer_seance(self.cours, self.groupes)

        for seance in seances:
            # Vérifier le format de l'ID des séances
            if seance.cours.type_cours == "CM":
                # Format attendu: S{compteur}_{id_cours}
                self.assertRegex(
                    seance.id_seance,
                    r"^S\d+_[A-Za-z0-9_]+$",
                    f"Format d'ID incorrect pour la séance CM: {seance.id_seance}",
                )
            elif seance.cours.type_cours == "TD":
                # Format attendu: S{compteur}_{id_cours}_{id_groupe}
                self.assertRegex(
                    seance.id_seance,
                    r"^S\d+_[A-Za-z0-9_]+_[A-Za-z0-9_]+$",
                    f"Format d'ID incorrect pour la séance TD: {seance.id_seance}",
                )

    def test_liaison_cours_groupes(self):
        """Vérifie que les cours sont correctement liés à leurs groupes après génération des séances."""
        seances = generer_seance(self.cours, self.groupes)

        # Vérifier que chaque cours a maintenant un groupe assigné
        for c in self.cours:
            self.assertIsNotNone(
                c.groupes, f"Le cours {c.id_cours} n'a pas de groupe assigné"
            )
            self.assertTrue(hasattr(c.groupes, "effectif"))
            self.assertGreater(c.groupes.effectif, 0)

            # Vérifier qu'au moins une séance fait référence à ce cours
            seances_du_cours = [s for s in seances if s.cours.id_cours == c.id_cours]
            self.assertGreater(
                len(seances_du_cours),
                0,
                f"Aucune séance n'a été générée pour le cours {c.id_cours}",
            )


if __name__ == "__main__":
    unittest.main()
