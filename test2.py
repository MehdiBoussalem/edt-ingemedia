class Teacher:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


class Group:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


class Course:
    def __init__(self, name, total_duration, teacher, groups):
        """
        :param name: Nom du cours (ex. "Mathématiques")
        :param total_duration: Durée totale du cours en heures
        :param teacher: Instance de Teacher
        :param groups: Liste d'instances de Group concernées par le cours
        """
        self.name = name
        self.total_duration = total_duration  # en heures
        self.teacher = teacher
        self.groups = groups
        self.sessions = []  # Liste des séances générées

    def generate_sessions(self, max_session_duration=3):
        """
        Découpe la durée totale du cours en séances.
        :param max_session_duration: Durée maximale de chaque séance (par défaut 3 heures)
        """
        remaining_duration = self.total_duration
        session_num = 1
        while remaining_duration > 0:
            # On crée une séance de durée égale à max_session_duration ou à la durée restante
            session_duration = min(max_session_duration, remaining_duration)
            self.sessions.append(Session(self, session_num, session_duration))
            session_num += 1
            remaining_duration -= session_duration


class Session:
    def __init__(self, course, session_number, duration):
        """
        :param course: Instance de Course
        :param session_number: Numéro de la séance
        :param duration: Durée de la séance en heures
        """
        self.course = course
        self.session_number = session_number
        self.duration = duration

    def __str__(self):
        # Affichage d'une séance avec nom du cours, numéro, durée et nom du professeur
        return f"{self.course.name} Séance {self.session_number} ({self.duration}H) avec {self.course.teacher}"


# Exemple d'utilisation
if __name__ == "__main__":
    # Création des entités
    teacher = Teacher("Anne Gagnebien")
    group_a = Group("Groupe A")
    group_b = Group("Groupe B")

    # Création d'un cours "Mathématiques" d'une durée totale de 6 heures
    course_math = Course(
        "Industries culturelles et créatives numériques",
        17.5,
        teacher,
        [group_a, group_b],
    )

    # Génération automatique des séances (par défaut en séances de 3H maximum)
    course_math.generate_sessions(max_session_duration=2.5)

    # Affichage des séances générées
    for session in course_math.sessions:
        print(session)
