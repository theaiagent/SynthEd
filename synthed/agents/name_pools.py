"""
Culturally diverse name pools organized by regional context.

Provides name selection from region-appropriate pools keyed by
``country_context`` values used in backstory_templates.py.  All data
is immutable (frozen dataclasses, tuples).  No external dependencies
(no Faker).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class NamePool:
    """A collection of first and last names for a cultural region.

    Parameters
    ----------
    region_label : str
        Human-readable label for the cultural region (e.g. ``"western_european"``).
    male_first : tuple[str, ...]
        Male first names common in the region.
    female_first : tuple[str, ...]
        Female first names common in the region.
    last_names : tuple[str, ...]
        Surnames common in the region.
    """

    region_label: str
    male_first: tuple[str, ...]
    female_first: tuple[str, ...]
    last_names: tuple[str, ...]


# ─────────────────────────────────────────────
# Valid country_context values
# ─────────────────────────────────────────────

_COUNTRY_CONTEXTS: tuple[str, ...] = (
    "developed_economy",
    "developing_economy",
    "transitional_economy",
    "post_industrial",
)


# ─────────────────────────────────────────────
# Name pools by region
# ─────────────────────────────────────────────

_WESTERN_EUROPEAN = NamePool(
    region_label="western_european",
    male_first=(
        "James", "Thomas", "Lucas", "Oliver", "William",
        "Henri", "Matteo", "Liam", "Noah", "Hugo",
        "Felix", "Oscar", "Elias", "Leo", "Arthur",
        "Jules", "Adam", "Ethan", "Louis", "Maximilian",
        "Sebastian", "Adrian", "Theo", "Raphael", "Jonas",
    ),
    female_first=(
        "Emma", "Sophie", "Olivia", "Charlotte", "Amelia",
        "Lea", "Mia", "Alice", "Clara", "Marie",
        "Isabelle", "Anna", "Elena", "Camille", "Louise",
        "Julia", "Nora", "Victoria", "Chloe", "Lina",
        "Hanna", "Ella", "Zoe", "Emilia", "Lena",
    ),
    last_names=(
        "Müller", "Schmidt", "Dubois", "Martin", "Bernard",
        "Rossi", "De Jong", "Johansson", "Andersen", "Garcia",
        "Fischer", "Weber", "Meyer", "Wagner", "Becker",
        "Laurent", "Moreau", "Lefebvre", "Eriksson", "Petersen",
        "Nilsson", "Jensen", "Larsen", "Hansen", "Pedersen",
    ),
)

_EAST_ASIAN = NamePool(
    region_label="east_asian",
    male_first=(
        "Wei", "Hiro", "Jian", "Tao", "Kenji",
        "Takeshi", "Ryu", "Riku", "Jun", "Min",
        "Seung", "Haruto", "Ren", "Kai", "Sho",
        "Daiki", "Minato", "Hiroshi", "Chen", "Liang",
        "Zhiming", "Sung", "Jin", "Hyun", "Souta",
    ),
    female_first=(
        "Yuki", "Mei", "Sakura", "Hana", "Aiko",
        "Ling", "Xin", "Jia", "Soo", "Minji",
        "Yuna", "Misaki", "Akari", "Himari", "Riko",
        "Nanami", "Xiaoli", "Fang", "Yan", "Mina",
        "Haruka", "Kokoro", "Yui", "Natsuki", "Sora",
    ),
    last_names=(
        "Wang", "Kim", "Tanaka", "Li", "Chen",
        "Park", "Suzuki", "Yamamoto", "Nakamura", "Zhang",
        "Liu", "Sato", "Lee", "Watanabe", "Ito",
        "Takahashi", "Huang", "Lin", "Wu", "Yang",
        "Choi", "Jeong", "Kobayashi", "Yoshida", "Sasaki",
    ),
)

_NORTH_AMERICAN = NamePool(
    region_label="north_american",
    male_first=(
        "Michael", "Christopher", "Matthew", "Joshua", "Daniel",
        "David", "Andrew", "Joseph", "Anthony", "Robert",
        "Brandon", "Tyler", "Ryan", "Justin", "Kevin",
        "Nathan", "Marcus", "Derek", "Aaron", "Brian",
        "Carlos", "Diego", "Alejandro", "Marco", "Jamal",
    ),
    female_first=(
        "Jennifer", "Jessica", "Sarah", "Ashley", "Emily",
        "Samantha", "Elizabeth", "Lauren", "Megan", "Rachel",
        "Hannah", "Brittany", "Nicole", "Amanda", "Stephanie",
        "Maria", "Andrea", "Jasmine", "Destiny", "Aaliyah",
        "Gabriela", "Kendra", "Priya", "Fatima", "Aisha",
    ),
    last_names=(
        "Smith", "Johnson", "Williams", "Brown", "Jones",
        "Davis", "Miller", "Wilson", "Moore", "Taylor",
        "Anderson", "Thomas", "Jackson", "White", "Harris",
        "Thompson", "Martinez", "Robinson", "Clark", "Lewis",
        "Rodriguez", "Walker", "Hall", "Young", "Allen",
    ),
)

_SOUTH_ASIAN = NamePool(
    region_label="south_asian",
    male_first=(
        "Aarav", "Vikram", "Raj", "Arjun", "Rohan",
        "Amir", "Siddharth", "Nikhil", "Kiran", "Anand",
        "Ravi", "Suresh", "Pradeep", "Manoj", "Arun",
        "Farhan", "Hassan", "Omar", "Bilal", "Imran",
        "Nuwan", "Kasun", "Dinesh", "Deepak", "Ramesh",
    ),
    female_first=(
        "Priya", "Ananya", "Meera", "Kavya", "Neha",
        "Aisha", "Fatima", "Zara", "Sana", "Nadia",
        "Deepa", "Lakshmi", "Sunita", "Pooja", "Rani",
        "Amara", "Devi", "Shreya", "Rekha", "Anjali",
        "Chamari", "Nilmini", "Sanduni", "Ruqaiya", "Hira",
    ),
    last_names=(
        "Sharma", "Patel", "Khan", "Singh", "Kumar",
        "Das", "Gupta", "Hussain", "Ahmed", "Ali",
        "Nair", "Reddy", "Joshi", "Mehta", "Shah",
        "Perera", "Fernando", "Silva", "Chowdhury", "Rahman",
        "Malik", "Thakur", "Mishra", "Verma", "Sinha",
    ),
)

_SUB_SAHARAN_AFRICAN = NamePool(
    region_label="sub_saharan_african",
    male_first=(
        "Kwame", "Oluwaseun", "Tendai", "Thabo", "Amadi",
        "Chinedu", "Kofi", "Sipho", "Jabari", "Emeka",
        "Obinna", "Yeboah", "Bongani", "Mandla", "Tunde",
        "Musa", "Ibrahim", "Adeola", "Nnamdi", "Osei",
        "Kagiso", "Lwazi", "Dumisani", "Adebayo", "Sekou",
    ),
    female_first=(
        "Amina", "Ngozi", "Nia", "Thandiwe", "Adaeze",
        "Chioma", "Fatou", "Zanele", "Wanjiku", "Abena",
        "Yaa", "Lindiwe", "Nkechi", "Folake", "Busisiwe",
        "Akosua", "Ama", "Nomsa", "Chiamaka", "Adetola",
        "Nalini", "Eshe", "Makena", "Zuri", "Ayanda",
    ),
    last_names=(
        "Okafor", "Mensah", "Nkosi", "Dlamini", "Mwangi",
        "Abiodun", "Ndlovu", "Boateng", "Kamara", "Osei",
        "Adeyemi", "Moyo", "Eze", "Asante", "Diallo",
        "Olawale", "Khumalo", "Nyathi", "Mbeki", "Owusu",
        "Traore", "Okwu", "Sibanda", "Cissé", "Banda",
    ),
)

_SOUTHEAST_ASIAN = NamePool(
    region_label="southeast_asian",
    male_first=(
        "Anh", "Bao", "Chai", "Datu", "Enrique",
        "Hoang", "Ismail", "Joko", "Kiet", "Luan",
        "Minh", "Nhat", "Phan", "Rizal", "Surin",
        "Thanh", "Vu", "Wira", "Arif", "Budi",
        "Dimas", "Faisal", "Gio", "Hadi", "Khai",
    ),
    female_first=(
        "Anh", "Binh", "Chau", "Dara", "Elisa",
        "Hoa", "Intan", "Jaya", "Kanya", "Linh",
        "Mai", "Nguyet", "Phuong", "Rosa", "Siti",
        "Thao", "Uyen", "Van", "Wati", "Yen",
        "Dewi", "Fitriani", "Gemma", "Hien", "Kamila",
    ),
    last_names=(
        "Nguyen", "Tran", "Le", "Pham", "Santos",
        "Reyes", "Cruz", "Garcia", "Suarez", "Lim",
        "Tan", "Chua", "Wijaya", "Suryadi", "Hartono",
        "Putra", "Sari", "Ismail", "Abdullah", "Rahman",
        "Bautista", "Ramos", "Mendoza", "Dela Cruz", "Aquino",
    ),
)

_EASTERN_EUROPEAN = NamePool(
    region_label="eastern_european",
    male_first=(
        "Alexei", "Boris", "Dmitri", "Ivan", "Nikolai",
        "Pavel", "Sergei", "Viktor", "Andrei", "Mikhail",
        "Oleg", "Roman", "Stanislav", "Yuri", "Bogdan",
        "Miroslav", "Tomasz", "Jakub", "Marek", "Petr",
        "Zoltan", "Laszlo", "Dragomir", "Stefan", "Vasile",
    ),
    female_first=(
        "Anastasia", "Natalia", "Ekaterina", "Irina", "Olga",
        "Tatiana", "Elena", "Svetlana", "Yulia", "Marina",
        "Oksana", "Darya", "Polina", "Vera", "Alina",
        "Katarzyna", "Marta", "Agnieszka", "Ivana", "Petra",
        "Magda", "Ludmila", "Renata", "Zuzana", "Ilona",
    ),
    last_names=(
        "Ivanov", "Petrov", "Smirnov", "Volkov", "Sokolov",
        "Kowalski", "Novak", "Horvat", "Popov", "Kuznetsov",
        "Kozlov", "Morozov", "Nowak", "Szabo", "Ionescu",
        "Popescu", "Stoica", "Kovalenko", "Shevchenko", "Bondarenko",
        "Grabowski", "Mazur", "Jankovic", "Milosevic", "Dimitrov",
    ),
)

_LATIN_AMERICAN = NamePool(
    region_label="latin_american",
    male_first=(
        "Mateo", "Santiago", "Sebastian", "Emiliano", "Diego",
        "Gabriel", "Angel", "Leonardo", "Samuel", "Nicolas",
        "Juan", "Carlos", "Pedro", "Rafael", "Fernando",
        "Alejandro", "Eduardo", "Ricardo", "Miguel", "Andres",
        "Gustavo", "Thiago", "Bruno", "Henrique", "Felipe",
    ),
    female_first=(
        "Valentina", "Camila", "Lucia", "Isabella", "Mariana",
        "Sofia", "Gabriela", "Daniela", "Ana", "Carolina",
        "Fernanda", "Natalia", "Paola", "Adriana", "Alejandra",
        "Juliana", "Lorena", "Monica", "Patricia", "Beatriz",
        "Leticia", "Renata", "Rafaela", "Larissa", "Bianca",
    ),
    last_names=(
        "Garcia", "Rodriguez", "Martinez", "Lopez", "Hernandez",
        "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres",
        "Flores", "Rivera", "Gomez", "Diaz", "Cruz",
        "Morales", "Reyes", "Gutierrez", "Ramos", "Vargas",
        "Silva", "Santos", "Oliveira", "Souza", "Costa",
    ),
)

_MIXED_NORTHERN_EUROPEAN = NamePool(
    region_label="mixed_northern_european",
    male_first=(
        "Erik", "Lars", "Sven", "Anders", "Mikkel",
        "Nils", "Olaf", "Henrik", "Bjorn", "Magnus",
        "Rasmus", "Emil", "Axel", "Kristian", "Petter",
        "Matti", "Jari", "Antti", "Eero", "Aleksi",
        "Tomas", "Gustav", "Sigurd", "Leif", "Ivar",
    ),
    female_first=(
        "Ingrid", "Astrid", "Sigrid", "Frida", "Linnea",
        "Elsa", "Maja", "Saga", "Wilma", "Ida",
        "Tuva", "Freya", "Signe", "Elin", "Liv",
        "Satu", "Aino", "Piia", "Kaisa", "Tiina",
        "Margit", "Helga", "Solveig", "Ragnhild", "Greta",
    ),
    last_names=(
        "Johansson", "Andersson", "Karlsson", "Nilsson", "Eriksson",
        "Larsson", "Olsson", "Persson", "Svensson", "Gustafsson",
        "Lindqvist", "Virtanen", "Korhonen", "Mäkinen", "Nieminen",
        "Hämäläinen", "Laine", "Heikkinen", "Koskinen", "Järvinen",
        "Haugen", "Berg", "Dahl", "Bakke", "Holm",
    ),
)

_RUST_BELT_AMERICAN = NamePool(
    region_label="rust_belt_american",
    male_first=(
        "Jake", "Kyle", "Cody", "Travis", "Dustin",
        "Shane", "Jesse", "Billy", "Tommy", "Bobby",
        "Ray", "Dale", "Wayne", "Troy", "Clint",
        "Darnell", "Tyrone", "Terrence", "Malik", "Andre",
        "Tomasz", "Janusz", "Grzegorz", "Donovan", "Corey",
    ),
    female_first=(
        "Crystal", "Amber", "Heather", "Tiffany", "Brandy",
        "Tammy", "Donna", "Brenda", "Sherry", "Tonya",
        "Latoya", "Keisha", "Monique", "Shanice", "Ebony",
        "Jolanta", "Beata", "Darlene", "Stacy", "Kristen",
        "Chelsey", "Kayla", "Paige", "Brooke", "Courtney",
    ),
    last_names=(
        "Kowalski", "Nowak", "Kaminski", "Wisnewski", "Jankowski",
        "O'Brien", "Murphy", "Sullivan", "McCarthy", "Kelly",
        "Steele", "Ford", "Mason", "Cooper", "Reed",
        "Washington", "Jefferson", "Freeman", "Brooks", "Coleman",
        "Tucker", "Dixon", "Porter", "Gibson", "Hayes",
    ),
)


# ─────────────────────────────────────────────
# Pool registry
# ─────────────────────────────────────────────

_POOLS: dict[str, tuple[NamePool, ...]] = {
    "developed_economy": (
        _WESTERN_EUROPEAN,
        _EAST_ASIAN,
        _NORTH_AMERICAN,
    ),
    "developing_economy": (
        _SOUTH_ASIAN,
        _SUB_SAHARAN_AFRICAN,
        _SOUTHEAST_ASIAN,
    ),
    "transitional_economy": (
        _EASTERN_EUROPEAN,
        _LATIN_AMERICAN,
    ),
    "post_industrial": (
        _MIXED_NORTHERN_EUROPEAN,
        _RUST_BELT_AMERICAN,
    ),
}

_FALLBACK_CONTEXT: str = "developed_economy"

assert set(_COUNTRY_CONTEXTS) == set(_POOLS.keys()), (
    "_COUNTRY_CONTEXTS and _POOLS keys are out of sync"
)


# ─────────────────────────────────────────────
# Public Functions
# ─────────────────────────────────────────────


def select_name(
    rng: np.random.Generator,
    gender: str,
    country_context: str,
) -> tuple[str, str]:
    """Select a (first_name, last_name) pair from the appropriate regional pool.

    A region is chosen uniformly at random from the pools mapped to the
    given *country_context*.  Then a first name (matched by *gender*)
    and a last name are drawn independently from that region's pool.

    Falls back to ``developed_economy`` pool for unknown *country_context*
    values.

    Parameters
    ----------
    rng : np.random.Generator
        NumPy random generator for reproducible selection.
    gender : str
        ``"male"`` or ``"female"``.  Any other value is treated as
        ``"female"`` with a logged warning.
    country_context : str
        One of the values in :data:`_COUNTRY_CONTEXTS`.

    Returns
    -------
    tuple[str, str]
        ``(first_name, last_name)`` drawn from the selected pool.
    """
    pools = _POOLS.get(country_context)
    if pools is None:
        logger.warning(
            "Unknown country_context %r — falling back to %r",
            country_context,
            _FALLBACK_CONTEXT,
        )
        pools = _POOLS[_FALLBACK_CONTEXT]

    # Pick a regional pool uniformly
    pool_idx = rng.integers(0, len(pools))
    pool = pools[pool_idx]

    # Resolve first-name list by gender
    if gender == "male":
        first_names = pool.male_first
    elif gender == "female":
        first_names = pool.female_first
    else:
        logger.warning("Unrecognised gender value — defaulting to female first-name pool")
        first_names = pool.female_first

    first_idx = rng.integers(0, len(first_names))
    last_idx = rng.integers(0, len(pool.last_names))

    return (first_names[first_idx], pool.last_names[last_idx])


def select_country_context(rng: np.random.Generator) -> str:
    """Select a random country_context using uniform distribution.

    Parameters
    ----------
    rng : np.random.Generator
        NumPy random generator for reproducible selection.

    Returns
    -------
    str
        One of the values in :data:`_COUNTRY_CONTEXTS`.
    """
    idx = rng.integers(0, len(_COUNTRY_CONTEXTS))
    return _COUNTRY_CONTEXTS[idx]

