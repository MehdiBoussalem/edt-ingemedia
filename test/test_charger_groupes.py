import os
import sys
import unittest
import csv

# Ajout du répertoire parent au chemin pour l'importation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import charger_groupes
import model


class TestChargerGroupes(unittest.TestCase):

    def setUp(self):
        """Configure le chemin vers le fichier de données pour les tests."""
        self.fichier_groupe = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "groupe.csv",
        )
        # Vérifier que le fichier existe
        self.assertTrue(
            os.path.exists(self.fichier_groupe),
            f"Le fichier {self.fichier_groupe} n'existe pas",
        )

    def test_chargement_groupes(self):
        """Test de chargement de tous les groupes depuis le fichier réel."""
        groupes = charger_groupes(self.fichier_groupe)

        # Vérifications de base
        self.assertIsNotNone(groupes)
        self.assertGreater(len(groupes), 0)

        # Vérifier que chaque groupe a bien les attributs requis
        for groupe in groupes:
            self.assertTrue(hasattr(groupe, "id_groupe"))
            self.assertTrue(hasattr(groupe, "nom"))
            self.assertTrue(hasattr(groupe, "effectif"))
            self.assertIsInstance(groupe.effectif, int)

    def test_relations_parent_enfant(self):
        """Vérifie que les relations parent-enfant sont correctement établies."""
        groupes = charger_groupes(self.fichier_groupe)

        # Créer un dictionnaire des groupes par ID pour faciliter la recherche
        groupes_par_id = {g.id_groupe: g for g in groupes}

        # Vérifier que chaque groupe avec un parent_id est bien dans les sous-groupes du parent
        for groupe in groupes:
            if hasattr(groupe, "id_parent") and groupe.id_parent:
                # Vérifier que le parent existe
                self.assertIn(
                    groupe.id_parent,
                    groupes_par_id,
                    f"Le parent {groupe.id_parent} du groupe {groupe.id_groupe} n'existe pas",
                )

                parent = groupes_par_id[groupe.id_parent]

                # Vérifier que le parent a des sous-groupes
                self.assertTrue(
                    hasattr(parent, "sous_groupes"),
                    f"Le parent {parent.id_groupe} n'a pas d'attribut sous_groupes",
                )

                # Vérifier que ce groupe est bien dans les sous-groupes du parent
                self.assertIn(
                    groupe,
                    parent.sous_groupes,
                    f"Le groupe {groupe.id_groupe} n'est pas dans les sous-groupes de {parent.id_groupe}",
                )

    def test_calcul_effectif_parents(self):
        """Vérifie que les effectifs des groupes parents sont correctement calculés."""
        groupes = charger_groupes(self.fichier_groupe)

        # Identifier les groupes qui ont des sous-groupes
        for groupe in groupes:
            if hasattr(groupe, "sous_groupes") and groupe.sous_groupes:
                # Calculer manuellement la somme des effectifs des sous-groupes
                somme_effectifs = sum(sg.effectif for sg in groupe.sous_groupes)

                # Vérifier que l'effectif du groupe parent correspond à la somme
                self.assertEqual(
                    groupe.effectif,
                    somme_effectifs,
                    f"L'effectif du groupe {groupe.id_groupe} ({groupe.effectif}) ne correspond pas "
                    f"à la somme des effectifs de ses sous-groupes ({somme_effectifs})",
                )

    def test_groupe_simple(self):
        """Vérifie que les groupes simples (sans parent ni sous-groupes) sont correctement chargés."""
        groupes = charger_groupes(self.fichier_groupe)

        # Identifier au moins un groupe simple
        groupes_simples = [
            g
            for g in groupes
            if (not hasattr(g, "sous_groupes") or not g.sous_groupes)
            and (not hasattr(g, "id_parent") or not g.id_parent)
        ]

        # Vérifier qu'il y a au moins un groupe simple
        if groupes_simples:
            # Les attributs de base sont présents et du bon type
            groupe = groupes_simples[0]
            self.assertIsInstance(groupe.id_groupe, str)
            self.assertIsInstance(groupe.nom, str)
            self.assertIsInstance(groupe.effectif, int)
            self.assertGreater(
                groupe.effectif, 0
            )  # Un groupe simple devrait avoir un effectif > 0


if __name__ == "__main__":
    unittest.main()
