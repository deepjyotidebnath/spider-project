"""Tiny built-in sample so the app and tests work without any download."""
from __future__ import annotations

from .schema import Column, ForeignKey, Schema, Table


def _t(name, cols, pk=()):
    return Table(name, [Column(n, ty, n in pk) for n, ty in cols])


SAMPLE_SCHEMAS: dict[str, Schema] = {
    "concert_singer": Schema(
        "concert_singer",
        [
            _t("stadium", [("Stadium_ID", "number"), ("Location", "text"), ("Name", "text"),
                           ("Capacity", "number"), ("Highest", "number"), ("Lowest", "number"),
                           ("Average", "number")], pk=("Stadium_ID",)),
            _t("singer", [("Singer_ID", "number"), ("Name", "text"), ("Country", "text"),
                          ("Song_Name", "text"), ("Song_release_year", "text"), ("Age", "number"),
                          ("Is_male", "others")], pk=("Singer_ID",)),
            _t("concert", [("concert_ID", "number"), ("concert_Name", "text"), ("Theme", "text"),
                           ("Stadium_ID", "text"), ("Year", "text")], pk=("concert_ID",)),
            _t("singer_in_concert", [("concert_ID", "number"), ("Singer_ID", "text")],
               pk=("concert_ID", "Singer_ID")),
        ],
        [
            ForeignKey("concert", "Stadium_ID", "stadium", "Stadium_ID"),
            ForeignKey("singer_in_concert", "concert_ID", "concert", "concert_ID"),
            ForeignKey("singer_in_concert", "Singer_ID", "singer", "Singer_ID"),
        ],
    ),
    "pets_1": Schema(
        "pets_1",
        [
            _t("Student", [("StuID", "number"), ("LName", "text"), ("Fname", "text"),
                           ("Age", "number"), ("Sex", "text"), ("Major", "number"),
                           ("Advisor", "number"), ("city_code", "text")], pk=("StuID",)),
            _t("Has_Pet", [("StuID", "number"), ("PetID", "number")]),
            _t("Pets", [("PetID", "number"), ("PetType", "text"), ("pet_age", "number"),
                        ("weight", "number")], pk=("PetID",)),
        ],
        [
            ForeignKey("Has_Pet", "StuID", "Student", "StuID"),
            ForeignKey("Has_Pet", "PetID", "Pets", "PetID"),
        ],
    ),
}

# (db_id, question, query, split)
SAMPLE_EXAMPLES = [
    ("concert_singer", "How many singers do we have?", "SELECT count(*) FROM singer", "train"),
    ("concert_singer", "What are the names of all singers?", "SELECT name FROM singer", "train"),
    ("concert_singer", "Show name, country, age for all singers ordered by age from the oldest to the youngest.",
     "SELECT name, country, age FROM singer ORDER BY age DESC", "train"),
    ("concert_singer", "What is the average, minimum, and maximum age of all singers from France?",
     "SELECT avg(age), min(age), max(age) FROM singer WHERE country = 'France'", "train"),
    ("concert_singer", "Show the name and the release year of the song by the youngest singer.",
     "SELECT song_name, song_release_year FROM singer ORDER BY age LIMIT 1", "train"),
    ("concert_singer", "Show the stadium name and the number of concerts in each stadium.",
     "SELECT T2.name, count(*) FROM concert AS T1 JOIN stadium AS T2 ON T1.stadium_id = T2.stadium_id GROUP BY T1.stadium_id",
     "train"),
    ("concert_singer", "Show the names of stadiums without any concert.",
     "SELECT name FROM stadium WHERE stadium_id NOT IN (SELECT stadium_id FROM concert)", "train"),
    ("concert_singer", "Show countries where a singer above age 40 and a singer below 30 are from.",
     "SELECT country FROM singer WHERE age > 40 INTERSECT SELECT country FROM singer WHERE age < 30",
     "validation"),
    ("pets_1", "Find the number of pets whose weight is heavier than 10.",
     "SELECT count(*) FROM pets WHERE weight > 10", "train"),
    ("pets_1", "Find the first name of students who have cat or dog pet.",
     "SELECT DISTINCT T1.fname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid = T2.stuid "
     "JOIN pets AS T3 ON T3.petid = T2.petid WHERE T3.pettype = 'cat' OR T3.pettype = 'dog'", "train"),
    ("pets_1", "How many pets are owned by students that have an age greater than 20?",
     "SELECT count(*) FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid = T2.stuid "
     "JOIN pets AS T3 ON T3.petid = T2.petid WHERE T1.age > 20", "validation"),
    ("pets_1", "Find the average and maximum age for each type of pet.",
     "SELECT avg(pet_age), max(pet_age), pettype FROM pets GROUP BY pettype", "validation"),
    ("pets_1", "Find the id of students who do not have a cat pet.",
     "SELECT stuid FROM student EXCEPT SELECT T1.stuid FROM student AS T1 JOIN has_pet AS T2 "
     "ON T1.stuid = T2.stuid JOIN pets AS T3 ON T3.petid = T2.petid WHERE T3.pettype = 'cat'",
     "validation"),
]
