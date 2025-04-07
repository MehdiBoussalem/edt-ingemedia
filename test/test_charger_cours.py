import os
import sys
import unittest
import csv

# Ajout du répertoire parent au chemin pour l'importation
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import charger_cours, charger_enseignants, charger_groupes
import model


class TestChargerCours(unittest.TestCase):

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

    def test_chargement_cours(self):
        """Test de chargement de tous les cours depuis le fichier réel."""
        cours = charger_cours(self.fichier_cours, self.enseignants, self.groupes)

        # Afficher la liste des cours chargés
        print("\nListe des cours chargés :")
        print("-" * 80)
        print(
            f"{'ID':<10} {'NOM':<20} {'TYPE':<5} {'DURÉE':<10} {'ENSEIGNANT':<15} {'GROUPES':<20}"
        )
        print("-" * 80)
        for c in cours:
            groupes_str = ", ".join(c.ids_groupes)
            print(
                f"{c.id_cours:<10} {c.nom:<20} {c.type_cours:<5} {c.duree_total:<10} {c.enseignant.nom:<15} {groupes_str:<20}"
            )
        print("-" * 80)

        # Vérifications de base
        self.assertIsNotNone(cours)
        self.assertGreater(len(cours), 0)

        # Vérifier que chaque cours a bien les attributs requis
        for c in cours:
            self.assertTrue(hasattr(c, "id_cours"))
            self.assertTrue(hasattr(c, "nom"))
            self.assertTrue(hasattr(c, "enseignant"))
            self.assertTrue(hasattr(c, "duree_total"))
            self.assertTrue(hasattr(c, "max_duration"))
            self.assertTrue(hasattr(c, "type_cours"))
            # Les groupes sont initialisés à None, mais ils devraient avoir des ids_groupes
            self.assertTrue(hasattr(c, "ids_groupes"))
            self.assertIsNone(c.groupes)  # Les groupes ne sont pas encore assignés

    def test_cours_par_type(self):
        """Vérifie que les cours sont correctement chargés par type (CM/TD)."""
        cours = charger_cours(self.fichier_cours, self.enseignants, self.groupes)

        # Compter les cours par type
        cours_cm = [c for c in cours if c.type_cours == "CM"]
        cours_td = [c for c in cours if c.type_cours == "TD"]

        # Vérifier qu'il y a des cours de chaque type
        self.assertGreater(len(cours_cm), 0, "Aucun cours de type CM trouvé")
        self.assertGreater(len(cours_td), 0, "Aucun cours de type TD trouvé")

        # Vérifier que chaque type de cours a les attributs attendus
        for c in cours_cm:
            self.assertEqual(c.type_cours, "CM")
            self.assertIsNotNone(c.enseignant)
            self.assertIsNotNone(c.ids_groupes)
            self.assertGreater(len(c.ids_groupes), 0)

        for c in cours_td:
            self.assertEqual(c.type_cours, "TD")
            self.assertIsNotNone(c.enseignant)
            self.assertIsNotNone(c.ids_groupes)
            self.assertGreater(len(c.ids_groupes), 0)

    def test_conversion_duree(self):
        """Vérifie que les durées sont correctement converties de heures en minutes."""
        cours = charger_cours(self.fichier_cours, self.enseignants, self.groupes)

        # Vérifier que toutes les durées sont en minutes (valeurs entières)
        for c in cours:
            self.assertTrue(
                isinstance(c.duree_total, int),
                f"La durée du cours {c.id_cours} n'est pas un entier: {c.duree_total}",
            )
            self.assertTrue(
                isinstance(c.max_duration, int),
                f"La durée max du cours {c.id_cours} n'est pas un entier: {c.max_duration}",
            )

            # Vérifier que les durées sont dans une plage raisonnable (5min à 20h)
            self.assertGreaterEqual(
                c.duree_total,
                5,  # Réduire de 10 à 5 minutes pour accepter les cours courts
                f"La durée du cours {c.id_cours} est trop courte: {c.duree_total} minutes",
            )
            self.assertLessEqual(
                c.duree_total,
                1200,  # 20 heures maximum
                f"La durée du cours {c.id_cours} est trop longue: {c.duree_total} minutes",
            )

    def test_parametres_invalides(self):
        """Vérifie que la fonction lève des exceptions appropriées pour des paramètres invalides."""
        # Tester sans enseignants
        with self.assertRaises(ValueError):
            charger_cours(self.fichier_cours, None, self.groupes)

        # Tester sans groupes
        with self.assertRaises(ValueError):
            charger_cours(self.fichier_cours, self.enseignants, None)

        # Tester avec un fichier inexistant
        fichier_inexistant = "fichier_inexistant.csv"
        with self.assertRaises(FileNotFoundError):
            charger_cours(fichier_inexistant, self.enseignants, self.groupes)


if __name__ == "__main__":
    unittest.main()
