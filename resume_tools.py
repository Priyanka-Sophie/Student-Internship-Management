import re


# Keep this list understandable and editable for a college project. Add skills as
# your course or internship sources require them.
KNOWN_SKILLS = [
    "Python", "Java", "C++", "C", "JavaScript", "TypeScript", "HTML", "CSS",
    "SQL", "MySQL", "PostgreSQL", "MongoDB", "React", "Angular", "Flutter",
    "Django", "Flask", "Git", "GitHub", "REST API", "AWS", "Azure", "Linux",
    "Docker", "Kubernetes", "Excel", "Power BI", "Tableau", "Figma",
    "Machine Learning", "Data Analysis", "Data Visualization", "Pandas", "NumPy",
    "Communication", "Problem Solving", "Networking", "Cybersecurity",
]


def extract_skills(resume_text):
    """Return known skills mentioned in resume text, once each, in display order."""
    normalized = " ".join(resume_text.lower().split())
    found = []
    for skill in KNOWN_SKILLS:
        pattern = r"(?<![a-z0-9+#])" + re.escape(skill.lower()) + r"(?![a-z0-9+#])"
        if re.search(pattern, normalized) and skill not in found:
            found.append(skill)
    return found


def split_skills(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def match_score(student_skills, required_skills):
    """Score required-skill overlap; roles without requirements are not recommended."""
    required = {skill.casefold() for skill in required_skills}
    student = {skill.casefold() for skill in student_skills}
    if not required:
        return 0
    return round((len(student & required) / len(required)) * 100)
