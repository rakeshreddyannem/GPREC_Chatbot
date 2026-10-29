import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.database import DatabaseManager
from src.faculty_parser import (
    parse_faculty_page, clean_faculty_name, 
    is_hod_designation, is_guest_designation
)
from src.faculty_router import handle_faculty_query, resolve_department


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    # Build a temporary self-contained database from tests/fixtures
    temp_dir = tmp_path_factory.mktemp("faculty_db")
    temp_db_path = temp_dir / "test_knowledge.db"
    test_db = DatabaseManager(db_path=temp_db_path)

    fixtures_dir = Path(__file__).parent / "fixtures"

    # 1. CE fixture
    ce_path = fixtures_dir / "faculty_ce.html"
    ce_records = parse_faculty_page(
        ce_path.read_text(encoding="utf-8"),
        "Civil Engineering",
        "https://www.gprec.ac.in/programs-offered/civil-engineering/"
    )
    test_db.upsert_faculty_batch(ce_records)

    # 2. CSE fixture (includes Dr. N. Kasiviswanath, Dr. S. Zahoor-ul-Huq, Dr. C. Sreedhar)
    cse_path = fixtures_dir / "faculty_cse.html"
    cse_records = parse_faculty_page(
        cse_path.read_text(encoding="utf-8"),
        "Computer Science and Engineering",
        "https://www.gprec.ac.in/programs-offered/computer-science-and-engineering/"
    )
    test_db.upsert_faculty_batch(cse_records)

    # 3. EEE fixture (Dr. G. Kishor as HOD + regular and guest members)
    eee_path = fixtures_dir / "faculty_eee.html"
    eee_records = parse_faculty_page(
        eee_path.read_text(encoding="utf-8"),
        "Electrical and Electronics Engineering",
        "https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/"
    )
    for r in eee_records:
        if "kishor" in r["name"].lower():
            r["photo_path"] = "data/faculty_photos/electrical_and_electronics_engineering/dr_g_kishor.jpg"
    test_db.upsert_faculty_batch(eee_records)

    # 4. Small records for ME and CST to ensure all faculty routing tests pass independently
    me_records = [
        {
            "name": "Dr. K. Madhava Reddy",
            "designation": "Professor & HOD",
            "qualification": "M.Tech., Ph.D",
            "department": "Mechanical Engineering",
            "email": "hodme@gprec.ac.in",
            "profile_url": "https://www.gprec.ac.in/images/me/madhava_reddy.pdf",
            "photo_url": "https://www.gprec.ac.in/images/me/madhava_reddy.jpg",
            "photo_path": "data/faculty_photos/mechanical_engineering/dr_k_madhava_reddy.jpg",
            "is_hod": 1,
            "is_guest": 0,
            "source_url": "https://www.gprec.ac.in/programs-offered/mechanical-engineering/",
            "is_active": 1
        }
    ]
    test_db.upsert_faculty_batch(me_records)

    cst_records = [
        {
            "name": "Dr. N.Kasiviswanath",
            "designation": "Professor & HoD",
            "qualification": "Ph.D",
            "department": "Computer Science and Technology",
            "email": "hodcse@gprec.ac.in",
            "profile_url": "https://www.gprec.ac.in/images/cse%20faculty%20profiles/Kasiviswanth.pdf",
            "photo_url": "https://www.gprec.ac.in/images/CSE/nkv.jpeg",
            "is_hod": 1,
            "is_guest": 0,
            "source_url": "https://www.gprec.ac.in/computer-science-and-technology/",
            "is_active": 1
        }
    ]
    test_db.upsert_faculty_batch(cst_records)

    return test_db


@pytest.fixture(scope="module")
def ce_html():
    fixture_path = Path(__file__).parent / "fixtures" / "faculty_ce.html"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cse_html():
    fixture_path = Path(__file__).parent / "fixtures" / "faculty_cse.html"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def eee_html():
    fixture_path = Path(__file__).parent / "fixtures" / "faculty_eee.html"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def csd_html():
    fixture_path = Path(__file__).parent / "fixtures" / "faculty_csd.html"
    return fixture_path.read_text(encoding="utf-8")


# --- 1. Parser & Field Extraction Tests (Offline) ---

def test_parse_ce_fixture(ce_html):
    records = parse_faculty_page(
        ce_html, 
        dept_name="Civil Engineering", 
        source_url="https://www.gprec.ac.in/programs-offered/civil-engineering/"
    )
    assert len(records) >= 2
    
    # First record should be HOD
    hod = records[0]
    assert "CHINNAPA REDDY" in hod["name"].upper()
    assert hod["designation"] == "Professor & HOD"
    assert hod["qualification"] == "M. Tech., Ph.D"
    assert hod["email"] == "hodce@gprec.ac.in"
    assert hod["is_hod"] == 1
    assert hod["is_guest"] == 0
    assert hod["profile_url"] is not None
    assert hod["profile_url"].endswith(".pdf")

    # Second record is Assoc HOD (must NOT be marked as is_hod = 1)
    assoc_hod = records[1]
    assert "VARAPRASAD" in assoc_hod["name"].upper()
    assert assoc_hod["is_hod"] == 0
    assert assoc_hod["qualification"] == "M. Tech., Ph.D"
    assert assoc_hod["email"] == "drbjsvp.ce@gprec.ac.in"


def test_parse_cse_fixture(cse_html):
    records = parse_faculty_page(
        cse_html, 
        dept_name="Computer Science and Engineering", 
        source_url="https://www.gprec.ac.in/programs-offered/computer-science-and-engineering/"
    )
    assert len(records) >= 2
    
    # Dr. N. Kasiviswanath is HOD
    hod = records[0]
    assert "Kasiviswanath" in hod["name"]
    assert hod["is_hod"] == 1
    assert hod["email"] == "hodcse@gprec.ac.in"

    # Dr. S. Zahoor-ul-Huq is ordinary Professor
    prof = records[1]
    assert "Zahoor" in prof["name"]
    assert prof["is_hod"] == 0


def test_parse_eee_fixture(eee_html):
    """Verify EEE fixture parses exactly 29 regular and 5 guest faculty members."""
    records = parse_faculty_page(
        eee_html,
        dept_name="Electrical and Electronics Engineering",
        source_url="https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/"
    )
    regular = sum(1 for r in records if not r["is_guest"])
    guest = sum(1 for r in records if r["is_guest"])
    assert len(records) == 34
    assert regular == 29
    assert guest == 5


def test_parse_csd_fixture(csd_html):
    """Verify CSD fixture parses exactly 43 regular and 4 guest faculty members."""
    records = parse_faculty_page(
        csd_html,
        dept_name="CSE - Data Science",
        source_url="https://www.gprec.ac.in/cse-data-science/"
    )
    regular = sum(1 for r in records if not r["is_guest"])
    guest = sum(1 for r in records if r["is_guest"])
    assert len(records) == 47
    assert regular == 43
    assert guest == 4


def test_faculty_list_says_regular_and_guest_separately(db):
    """Verify faculty list answers say 'regular faculty' and 'guest faculty' separately."""
    res = handle_faculty_query("list electrical and electronics engineering faculty", db)
    assert res is not None
    assert res["response_type"] == "ANSWERED"
    ans_lower = res["answer"].lower()
    assert "regular faculty" in ans_lower
    assert "guest faculty" in ans_lower


def test_hod_detection_logic():
    # Only true HOD is 1
    assert is_hod_designation("Professor & HOD") == 1
    assert is_hod_designation("Professor & Head of the Department") == 1
    assert is_hod_designation("Head of Department") == 1
    assert is_hod_designation("Professor & HoD") == 1
    
    # Associate HOD is NOT primary HOD
    assert is_hod_designation("Professor & Associate HoD") == 0
    assert is_hod_designation("Professor & Assoc.HOD") == 0
    assert is_hod_designation("Assoc.Prof & Assoc.HOD") == 0
    assert is_hod_designation("Associate Professor & Associate HoD") == 0
    
    # Ordinary professors
    assert is_hod_designation("Professor") == 0
    assert is_hod_designation("Associate Professor") == 0
    assert is_hod_designation("Assistant Professor") == 0
    assert is_hod_designation(None) == 0


def test_guest_detection_logic():
    assert is_guest_designation("Visiting Faculty") == 1
    assert is_guest_designation("Guest Lecturer") == 1
    assert is_guest_designation("Adjunct Professor") == 1
    assert is_guest_designation("Adjunct Faculty") == 1
    
    assert is_guest_designation("Professor") == 0
    assert is_guest_designation("Assistant Professor") == 0
    assert is_guest_designation(None) == 0


def test_null_handling_in_parser():
    # Synthetic HTML missing qualification, email, and photo
    html_snippet = """
    <table>
        <tr>
            <td>
                <table>
                    <tr><td>Name of the faculty</td><td>Dr. Sample Person</td></tr>
                    <tr><td>Designation</td><td>Assistant Professor</td></tr>
                    <tr><td>Qualifications</td><td>-</td></tr>
                    <tr><td>EmailID</td><td>N/A</td></tr>
                </table>
            </td>
        </tr>
    </table>
    """
    records = parse_faculty_page(html_snippet, "Civil Engineering", "https://www.gprec.ac.in")
    assert len(records) == 1
    r = records[0]
    assert r["name"] == "Dr. Sample Person"
    assert r["qualification"] is None
    assert r["email"] is None
    assert r["photo_url"] is None
    assert r["photo_path"] is None


# --- 2. Deterministic Question Routing Tests (10 Sample Questions) ---

def test_q1_who_is_hod_of_eee(db):
    res = handle_faculty_query("who is the hod of eee", db)
    assert res is not None
    assert res["response_type"] == "ANSWERED"
    assert "Dr. G. Kishor" in res["answer"]
    assert "Electrical and Electronics Engineering" in res["answer"]
    assert len(res["faculty_records"]) == 1
    assert res["faculty_records"][0]["is_hod"] == 1


def test_q2_who_is_dr_kishor(db):
    res = handle_faculty_query("who is dr kishor", db)
    assert res is not None
    assert res["response_type"] == "ANSWERED"
    assert "Kishor" in res["answer"]
    assert "Electrical and Electronics Engineering" in res["answer"]
    assert len(res["faculty_records"]) >= 1


def test_q3_profile_of_dr_c_sreedhar(db):
    res = handle_faculty_query("profile of dr c sreedhar", db)
    assert res is not None
    assert res["response_type"] == "ANSWERED"
    assert "Sreedhar" in res["answer"]
    assert len(res["faculty_records"]) >= 1


def test_q4_list_civil_engineering_faculty(db):
    res = handle_faculty_query("list civil engineering faculty", db)
    assert res is not None
    assert res["response_type"] == "ANSWERED"
    assert "Professors" in res["answer"]
    assert "CHINNAPA REDDY" in res["answer"].upper()
    assert "Civil Engineering" in res["answer"]


def test_q5_how_many_faculty_members_in_cse(db):
    res = handle_faculty_query("how many faculty members in cse", db)
    assert res is not None
    assert res["response_type"] == "ANSWERED"
    assert "Computer Science and Engineering" in res["answer"]
    assert "regular faculty members" in res["answer"]


def test_q6_faculty_of_mechanical(db):
    res = handle_faculty_query("faculty of mechanical", db)
    assert res is not None
    assert res["response_type"] == "ANSWERED"
    assert "Mechanical Engineering" in res["answer"]
    assert "Professors" in res["answer"]


def test_q7_show_me_dr_kishor_photo(db):
    res = handle_faculty_query("show me dr kishor photo", db)
    assert res is not None
    assert res["response_type"] == "ANSWERED"
    assert "Kishor" in res["answer"]
    assert len(res["faculty_records"]) >= 1
    # Check that photo_path is provided in faculty record
    assert res["faculty_records"][0]["photo_path"] is not None
    assert res.get("is_particular_faculty") is True

    # Test possessive 's and "show me" pronoun handling
    res_possessive = handle_faculty_query("show me Dr. Kishor's photo", db)
    assert res_possessive is not None
    assert res_possessive["response_type"] == "ANSWERED"
    assert "Kishor" in res_possessive["answer"]
    assert res_possessive.get("is_particular_faculty") is True

    res_of = handle_faculty_query("show me the photo of Dr. Kishor", db)
    assert res_of is not None
    assert res_of["response_type"] == "ANSWERED"
    assert "Kishor" in res_of["answer"]
    assert res_of.get("is_particular_faculty") is True


def test_me_department_vs_pronoun(db):
    # 'me' in 'who is the hod of me' should resolve to Mechanical Engineering
    res_dept = handle_faculty_query("who is the hod of me", db)
    assert res_dept is not None
    assert res_dept["response_type"] == "ANSWERED"
    assert "Mechanical Engineering" in res_dept["answer"]
    assert "Madhava Reddy" in res_dept["answer"]
    assert res_dept.get("is_particular_faculty") is True


def test_q8_hod_of_unknown_department(db):
    res = handle_faculty_query("who is the hod of an unknown department", db)
    assert res is not None
    assert res["response_type"] == "NOT_FOUND"
    assert "does not have an 'unknown' department" in res["answer"]


def test_q9_name_matching_two_departments(db):
    # Dr. N. Kasiviswanath is listed in CSE and CST
    res = handle_faculty_query("who is dr n kasiviswanath", db)
    assert res is not None
    assert res["response_type"] == "ANSWERED"
    # Should display both matches clearly
    assert len(res["faculty_records"]) >= 2
    depts = [f["department"] for f in res["faculty_records"]]
    assert "Computer Science and Engineering" in depts
    assert "Computer Science and Technology" in depts
    assert "different departments" in res["answer"]


def test_q10_nonexistent_person(db):
    res = handle_faculty_query("tell me about xyznonexistent", db)
    assert res is not None
    assert res["response_type"] == "NOT_FOUND"
    assert "could not find a faculty member named 'xyznonexistent'" in res["answer"]


def test_ambiguous_hod_without_department(db):
    res = handle_faculty_query("who is the hod", db)
    assert res is not None
    assert res["response_type"] == "CLARIFY"
    assert "Which department's HOD are you looking for?" in res["answer"]


def test_is_particular_faculty_flag(db):
    """Verify is_particular_faculty is True only for specific faculty/HOD queries."""
    # 1. HOD query -> particular faculty
    hod_res = handle_faculty_query("who is the hod of eee", db)
    assert hod_res.get("is_particular_faculty") is True
    assert len(hod_res["faculty_records"]) == 1

    # 2. Single person query -> particular faculty
    person_res = handle_faculty_query("who is dr kishor", db)
    assert person_res.get("is_particular_faculty") is True
    assert len(person_res["faculty_records"]) >= 1

    # 3. Department faculty list -> NOT particular faculty
    list_res = handle_faculty_query("list civil engineering faculty", db)
    assert list_res.get("is_particular_faculty") is not True

    # 4. Count query -> NOT particular faculty
    count_res = handle_faculty_query("how many faculty members in cse", db)
    assert count_res.get("is_particular_faculty") is not True


def test_sidebar_pages_structure():
    """Verify legacy single-topic pages (departments, examinations, placements, hostels, library) are removed."""
    from pathlib import Path
    app_text = Path("app.py").read_text(encoding="utf-8")
    # Check that removed pages are not in the sidebar pages dictionary
    removed_items = ["Departments", "Examination", "Placements", "Hostel", "Library"]
    for item in removed_items:
        assert f'"{item}":' not in app_text

