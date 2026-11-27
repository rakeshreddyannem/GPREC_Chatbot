import sys
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import config

db_path = config.DB_PATH
print(f"Connecting to database at: {db_path}")

conn = sqlite3.connect(db_path)
c = conn.cursor()

# 1. Delete previous EEE subjects for sem 3, 5, 7
c.execute("DELETE FROM timetable_subjects WHERE UPPER(branch) = 'EEE' AND semester IN (3, 5, 7)")

# 2. Semester 3 (10 Subjects from Image 1)
sem3 = [
    ('BS205', 'Complex Variables & Numerical Methods (CVNM)'),
    ('HSM201', 'Universal Human Values (UHV)'),
    ('EE201', 'Electromagnetic Field Theory (EMF)'),
    ('EE202', 'Electrical Circuit Analysis-II (ECA2)'),
    ('EE204', 'DC Machines & Transformers (DCMT)'),
    ('EE203', 'Electrical Circuit Analysis-II and Simulation Lab (ECA2&S(P))'),
    ('EE205', 'DC Machines & Transformers Lab (DCMT(P))'),
    ('SCCS05', 'Data Structures (SOC) (DS(P))'),
    ('ESCM01', 'Design Thinking & Innovation (DT&I)'),
    ('MOOCS', 'Massive Open Online Course (Digital Learning) (MOOCS)'),
]

for code, name in sem3:
    c.execute("""
        INSERT INTO timetable_subjects 
        (branch, year, semester, section, academic_year, course_code, subject_name, faculty, source_file, page_num, needs_review, is_current_semester)
        VALUES ('EEE', 2, 3, 'A', '2026-2027', ?, ?, '', 'Official EEE Timetable', 1, 0, 1)
    """, (code, name))

# 3. Semester 5 (10 Subjects from Image 2)
sem5 = [
    ('EE301', 'Power Electronics (PE)'),
    ('EC306', 'Digital Circuits (DC)'),
    ('EE302', 'Power Systems-II (PS2)'),
    ('BS301', 'Introduction to Quantum Technologies & Applications (IQTA)'),
    ('EE303', 'Signals & Systems (S&S) (PE-1)'),
    ('SCEE01', 'Introduction to Python Programming (IPP) (SEC)'),
    ('ESCM02', 'Tinkering Lab (TL(P))'),
    ('EE306', 'Power Electronics Lab (PE(P))'),
    ('EC307', 'Analog & Digital Circuits Lab (A&DC(P))'),
    ('MOOCS', 'Massive Open Online Course (Digital Learning) (MOOCS)'),
]

for code, name in sem5:
    c.execute("""
        INSERT INTO timetable_subjects 
        (branch, year, semester, section, academic_year, course_code, subject_name, faculty, source_file, page_num, needs_review, is_current_semester)
        VALUES ('EEE', 3, 5, 'A', '2026-2027', ?, ?, '', 'Official EEE Timetable', 1, 0, 1)
    """, (code, name))

# 4. Semester 7 (10 Subjects from Image 3)
sem7 = [
    ('EE401', 'Power System Operation & Control (PSOC)'),
    ('HSM403', 'Management Science (MS) (MC-II)'),
    ('EE402', 'Elements of Digital Signal Processing (EDSP) (PE-IV)'),
    ('EE405', 'Utilization of Electrical Energy (UEE) (PE-V)'),
    ('OE-III', 'Open Elective-III'),
    ('OE-IV', 'Open Elective-IV'),
    ('AC402', 'Constitution of India (COI) (AC)'),
    ('SCEE03', 'Power Systems & Simulation Lab (PSS(P)) (SEC)'),
    ('PROJ', 'Project'),
    ('MENTOR', 'Mentoring'),
]

for code, name in sem7:
    c.execute("""
        INSERT INTO timetable_subjects 
        (branch, year, semester, section, academic_year, course_code, subject_name, faculty, source_file, page_num, needs_review, is_current_semester)
        VALUES ('EEE', 4, 7, 'A', '2026-2027', ?, ?, '', 'Official EEE Timetable', 1, 0, 1)
    """, (code, name))

conn.commit()

c.execute("SELECT semester, COUNT(*) FROM timetable_subjects WHERE UPPER(branch) = 'EEE' GROUP BY semester")
counts = c.fetchall()
print("Updated EEE counts per semester:", counts)

conn.close()
print("Database updated successfully.")
