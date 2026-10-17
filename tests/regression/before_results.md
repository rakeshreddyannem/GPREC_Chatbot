# Baseline Regression Results (BEFORE Optimization)

**Execution Timestamp:** 2026-10-12 14:37:27

| # | Query | Check Status | Confidence | Latency | Automated Check Reason |
|---|-------|--------------|------------|---------|-------------------------|
| 1 | give me the information regarding the placements | ✅ PASS | High | 10.43s | Passed basic reliability check. |
| 2 | details about eee department faculties list and their designations | ✅ PASS | High | 49.12s | Passed basic reliability check. |
| 3 | list the PhD faculties | ❌ FAIL | High | 66.37s | Failed ambiguity check: Query lacks department and did not ask to clarify or state scope. |
| 4 | list the phd faculties of eee department | ✅ PASS | High | 29.18s | Passed inference restriction check. |
| 5 | information about the boys hostel | ✅ PASS | High | 6.47s | Passed basic reliability check. |
| 6 | about the clubs in college | ✅ PASS | High | 23.2s | Passed basic reliability check. |
| 7 | give me detail information about each and every faculty in eee department | ✅ PASS | High | 17.55s | Passed basic reliability check. |
| 8 | who is the principal of this college | ❌ FAIL | High | 3.58s | Failed to identify Principal Dr. B. Sreenivasa Reddy. |
| 9 | information about ITCA | ✅ PASS | High | 6.54s | Passed date check. |
| 10 | what is fee structure of EEE department | ✅ PASS | High | 12.15s | Single response check passed. |
| 11 | information about library | ❌ FAIL | High | 15.59s | Irrelevant source retrieved for library: rti (https://www.gprec.ac.in/rti/statutory-declaration-under-act-4-1-1-2.pdf) |
| 12 | who is the head of eee department library | ✅ PASS | High | 15.58s | Answer is non-empty. |
| 13 | detail information about the exam time table | ✅ PASS | High | 15.08s | Passed bullet count check. |


## Detailed Responses per Question

### Question 1: give me the information regarding the placements

- **Category:** `placements`
- **Expected Behavior:** Return factual placement statistics/records from official sources, no hallucinated packages or numbers, single clean response.
- **Automated Check:** ✅ PASS - Passed basic reliability check.
- **Confidence:** High | **Latency:** 10.43s

**Current Output (Before):**
```text
Here is the information regarding placements at GPREC based on the official sources:

**Training & Placement Cell**
*   **Head:** The cell is headed by **Dr. K. Govardhan Reddy**, Professor of CSE (AIML).
*   **Team:** It includes a full-time Manager Corporate Relations, an Assistant Training and Placement Officer, and a committee (1 Professor In-charge, 3 faculty members, and 5 student members from each department).
*   **Key Services:**
    *   Arranges **campus interviews for final year students**.
    *   Helps students secure **internship opportunities**.
    *   Conducts **mock aptitude tests, psychometric tests, group discussions, and mock interviews** with alumni and professionals.
    *   Maintains an **Alumni network** and organizes industry interactions.

**Placement Training**
*   Training begins right from the **first year** of admission.
*   Approximately **300 hours of training** are distributed across semesters.
*   **Topics covered:** Quantitative Ability, Logical Reasoning, Verbal Ability, Programming Skills, Communication Skills, Group Discussion & Interview Skills, and Personality Development.
*   **Schedule:** Classes are part of the regular timetable in some semesters, and held during holidays, vacations, or beyond college hours in others.
*   **Resource Persons:** Training is conducted by professional institutes (e.g., PrepInsta, LearnSquare, TAP Academy) and industry representatives (e.g., TCS, Infosys, Wipro, Microsoft, Oracle, IBM), along with distinguished alumni and internal faculty.

**T & P Club**
*   A student club works under the Training and Placement Department to assist in organizing events and create awareness.
*   **Eligibility:** Selected students from different years and branches with high attendance and marks can join via a selection process (written test, group discussion, and personal interviews).

For the most recent placement drives and specific lists, please check the official notice board or the Training & Placement Department directly.
```

**Retrieved Sources (Top 3):**
- [Training & Placements – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/training-placements/)
- [Training & Placements – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/training-placements/)
- [Training & Placements – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/training-placements/)

---

### Question 2: details about eee department faculties list and their designations

- **Category:** `departments_faculty`
- **Expected Behavior:** List EEE faculty members and their official designations strictly matching retrieved text.
- **Automated Check:** ✅ PASS - Passed basic reliability check.
- **Confidence:** High | **Latency:** 49.12s

**Current Output (Before):**
```text
I couldn't find this information in the available official GPREC sources. Please check the latest official notice or contact the relevant college office.
```

**Retrieved Sources (Top 3):**
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)

---

### Question 3: list the PhD faculties

- **Category:** `ambiguity_faculty`
- **Expected Behavior:** Ambiguity handling: query lacks department. Must ask CLARIFY (Which department?) or explicitly state the department scope. Strictly count only people with explicit doctorate (Dr. prefix or Ph.D degree).
- **Automated Check:** ❌ FAIL - Failed ambiguity check: Query lacks department and did not ask to clarify or state scope.
- **Confidence:** High | **Latency:** 66.37s

**Current Output (Before):**
```text
As per the official GPREC Humanities and Basic Sciences department page (Source 13, dated 2026-10-08), **19 teaching faculty hold Ph.D. degrees** out of 43 total teaching staff. The PhD faculty listed include:

- Dr. K.V.S. Gopala Krishna Sastry  
- Dr. Y. Rajasekhara Goud  
- Dr. N.V.S. Gupta  
- Dr. K. Subhashini  
- Dr. A. Vijaya Kumar  
- Dr. Nasreen Noor  
- Dr. V. Raghavendra Prasad  
- Dr. M. Siva Sankara Reddy  
- Dr. K. Aparna  
- Dr. V. Rangaveni  
- Dr. E. Kiran Babu  
- Dr. S. Sailaja  
- Dr. A. LingaSwamy  
- G. Venkatarami Reddy  

*(Note: The department has 20 faculty currently pursuing doctoral research. For the complete official list, refer to the GPREC HBS faculty page.)*
```

**Retrieved Sources (Top 3):**
- [Electronics and Communication Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electronics-and-communication-engineering/)
- [Electronics and Communication Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electronics-and-communication-engineering/)
- [Electronics and Communication Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electronics-and-communication-engineering/)

---

### Question 4: list the phd faculties of eee department

- **Category:** `forbid_inference_faculty`
- **Expected Behavior:** Forbid inference: Only list persons explicitly confirmed with doctorate ('Dr.' or Ph.D). Being a jury member or resource person is NOT evidence. If incomplete, state 'the sources only confirm X of Y'.
- **Automated Check:** ✅ PASS - Passed inference restriction check.
- **Confidence:** High | **Latency:** 29.18s

**Current Output (Before):**
```text
According to the official EEE department profile, the department has a strong faculty pool with **17 Ph.D.’s**. The provided sources do not contain a complete name list for all of them.

However, the following faculty members are explicitly noted in recent achievements as supervising Ph.D. scholars:

*   **Dr. G. Kishor (HoD)** – Supervised Sri. R Rohith (Jan 2026)
*   **G Satheesh (Associate Professor)** – Supervised Sri. M. Venkateswarlu (Jan 2026) and Sri. M. Sunil Kumar (Jun 2025)

For the complete list of all Ph.D. faculty, please check the official Faculty page or contact the relevant college office.
```

**Retrieved Sources (Top 3):**
- [Electronics and Communication Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electronics-and-communication-engineering/)
- [Electronics and Communication Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electronics-and-communication-engineering/)
- [Electronics and Communication Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electronics-and-communication-engineering/)

---

### Question 5: information about the boys hostel

- **Category:** `hostel`
- **Expected Behavior:** Non-empty hostel details, facilities, rules from official sources. Never expose private phone numbers or default credentials.
- **Automated Check:** ✅ PASS - Passed basic reliability check.
- **Confidence:** High | **Latency:** 6.47s

**Current Output (Before):**
```text
The Boys Hostel is located adjacent to the GPREC campus.  
- **Room type & fee:** Ordinary room (common bathroom) – ₹75,500 per year.  
- **Additional one‑time charges (for first‑time hostel admission):**  
  - Non‑refundable maintenance fund: ₹5,000  
  - Refundable caution deposit: ₹5,000  
- **Seat allocation:** First‑come, first‑served basis.  
- **Contact for details:** Dr. Ishthaq Ahmed, Associate Professor of CSE – 9866776244.  

(If you need any other specific information, please let me know.)
```

**Retrieved Sources (Top 3):**
- [Hostels – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://gprec.ac.in/hostel)
- [Hostels – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://gprec.ac.in/hostel)
- [Hostels – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://gprec.ac.in/hostel)

---

### Question 6: about the clubs in college

- **Category:** `clubs`
- **Expected Behavior:** Non-empty information on student clubs/activities from official college sources without hallucination.
- **Automated Check:** ✅ PASS - Passed basic reliability check.
- **Confidence:** High | **Latency:** 23.2s

**Current Output (Before):**
```text
Based on the official GPREC sources, here are the student clubs at GPREC:

**Student Clubs at GPREC:**

- **IEI Students' Chapter** – Conducts seminars on technical topics, quizzes, and lectures for each department.
- **Bhuvana Vijayam** – Literary and cultural association that provides a platform for students to exhibit their talents in culture and literature.
- **Center for Awareness & Discussion** – Organizes group discussions and quizzes to familiarize students with current topics.
- **Vivekananda Study Circle** – Focuses on universal brotherhood, selfless service to society, and inculcating noble values in youth.
- **Art of Living Forum** – Aims to bring joy, a stress-free mind, a healthy body, and blossomed life to students and faculty.
- **T&P Club (Training & Placement Club)** – Works under the Guidance Training and Placement Department. Members are selected from different years and branches. Its aims include assisting the training and placement cell, creating awareness about placement and training processes, developing teamwork and leadership skills, and connecting students with alumni.

These are the clubs currently listed on the official GPREC website. For the most up-to-date information, please check the latest official notice or contact the college office.
```

**Retrieved Sources (Top 3):**
- [Student Clubs – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/student-clubs)
- [Student Clubs – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/student-clubs)
- [Student Clubs – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/student-clubs)

---

### Question 7: give me detail information about each and every faculty in eee department

- **Category:** `departments_faculty`
- **Expected Behavior:** Grounded faculty details without fabricating designations or private personal phone numbers/emails.
- **Automated Check:** ✅ PASS - Passed basic reliability check.
- **Confidence:** High | **Latency:** 17.55s

**Current Output (Before):**
```text
The official GPREC sources provide an overview and some named faculty members, but not detailed profiles for every single faculty member.

Here is what is available:
- **Department Head:** Dr. G.Kishor
- **Teaching Staff:** 4 Professors, 8 Associate Professors, 17 Assistant Professors
- **Qualifications:** 17 Ph.D.’s and 12 M.Tech.’s
- **Named EEE Faculty** (from IEEE and E-Governance committees): Dr. K. Jagadeesh, Dr. S. Anil Kumar, Dr. V. Anantha Lakshmi, and D. Vannurappa

Detailed profiles for each and every faculty member are not listed in the current sources.

I couldn't find this information in the available official GPREC sources. Please check the latest official notice or contact the relevant college office.
```

**Retrieved Sources (Top 3):**
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)

---

### Question 8: who is the principal of this college

- **Category:** `leadership`
- **Expected Behavior:** Answer college leadership (Principal: Dr. B. Sreenivasa Reddy) from directory/official source, or explain missing coverage.
- **Automated Check:** ❌ FAIL - Failed to identify Principal Dr. B. Sreenivasa Reddy.
- **Confidence:** High | **Latency:** 3.58s

**Current Output (Before):**
```text
I couldn't find this information in the available official GPREC sources. Please check the latest official notice or contact the relevant college office.
```

**Retrieved Sources (Top 3):**
- [Alumni Activities – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/alumni/alumni-activities/)
- [Alumni Activities – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/alumni/alumni-activities/)
- [Alumni Activities – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/alumni/alumni-activities/)

---

### Question 9: information about ITCA

- **Category:** `acronyms_dates`
- **Expected Behavior:** No crawl/first_seen date presented as notice date; do NOT expand ITCA unless expansion explicitly appears in source.
- **Automated Check:** ✅ PASS - Passed date check.
- **Confidence:** High | **Latency:** 6.54s

**Current Output (Before):**
```text
ITCA stands for **Intensive Training Program for Career Advancement**. It’s a college program aimed at helping students advance their careers. You can access the ITCA portal at **http://examcell.gprec.ac.in/ITPPLogin.aspx** using your RollNo and password. If you have any login issues or need corrections, please contact the **Training & Placement Cell**.
```

**Retrieved Sources (Top 3):**
- [G. Pulla Reddy Engineering College (Autonomous)](https://examcell.gprec.ac.in/studentserviceslogin.aspx)
- [G. Pulla Reddy Engineering College (Autonomous)](https://examcell.gprec.ac.in/studentserviceslogin.aspx)
- [G. Pulla Reddy Engineering College (Autonomous)](https://examcell.gprec.ac.in/studentserviceslogin.aspx)

---

### Question 10: what is fee structure of EEE department

- **Category:** `fees_ambiguity`
- **Expected Behavior:** Single clean response (no duplicate plain text + not found card). Give real fee amounts with academic year / as-of date or clearly state document status.
- **Automated Check:** ✅ PASS - Single response check passed.
- **Confidence:** High | **Latency:** 12.15s

**Current Output (Before):**
```text
I couldn't find this information in the available official GPREC sources. Please check the latest official notice or contact the relevant college office.
```

**Retrieved Sources (Top 3):**
- [Fee Structure – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/admissions/fee-structure/)
- [Fee Structure – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/admissions/fee-structure/)
- [Fee Structure – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/admissions/fee-structure/)

---

### Question 11: information about library

- **Category:** `library`
- **Expected Behavior:** Library resources and timings. Filter out unrelated sources like Alumni or RTI.
- **Automated Check:** ❌ FAIL - Irrelevant source retrieved for library: rti (https://www.gprec.ac.in/rti/statutory-declaration-under-act-4-1-1-2.pdf)
- **Confidence:** High | **Latency:** 15.59s

**Current Output (Before):**
```text
**GPREC Central Library – Quick Overview**

**📍 Location & Management**
- Headed by a senior faculty (Library In-charge) supported by 1 Librarian, 4 Library Assistants, 1 Hardware Technician, 3 helpers.
- Library Committee (Convener: Y.V. Mohan Reddy, Dean Academics) oversees book procurement, improvements, fines & discipline.

**📚 Collection (as of latest data)**
- **Volumes:** ~66,106 | **Titles:** ~14,153
- **Journals:** 84 National + 979 International
- **Classification:** Dewey Decimal Scheme | **Automation:** SLIM 21 software
- **Open Access System** – 150 seating capacity

**💻 Digital Library (Electronic Resources Wing)**
- 50 systems with 1 Gbps internet
- **E-journals/DBs:** IEEE (250), Elsevier ScienceDirect (369), SpringerNature (503), DELNET, NDLI, KNIBUS (off-campus), British Council Library
- **NPTEL:** 12 Core i3 computers for video lectures (CSE, CE, ME, EEE, ECE, Basic Sciences, Humanities)
- **Old Question Papers** (Kurnool) available
- 2 Servers + 19 Core i3 PCs for LAN/WAN
- Reprography: Canon IR 4525 copier & laser printers

**⏰ Working Hours**
- **All working days:** 9:00 AM – 7:00 PM

**🎫 Library Cards**
| Category | Cards Issued |
|----------|--------------|
| All students (except final year) | 3 |
| Final-year students | 4 |
| Faculty | 6 |
| Research scholars | 4 |

- Cards issued only on producing ID card | Non-transferable | 1 book per card
- **Duplicate card:** ₹50 (report loss in writing immediately)
- Borrower tickets/duplicates issued **only on Saturdays**

**📖 Borrowing & Returns**
- **Students:** 14 days | **Faculty:** 1 month
- **2 renewals** allowed (if no reservations) – must present book & ID physically
- **Overdue charges:**
  - First 7 days: ₹1/day
  - 8th day onward: ₹2/day (holidays counted)
  - If due date falls on holiday → next working day
  - Not returned within 50 days → book cost + overdue charges levied
- **Lost book:** Report immediately → replace with same/good copy (Principal’s permission) or pay **twice the cost + overdue charges**
- **Reservation:** Reserved books held at counter for 2 days; else passed to next in queue

**📋 General Rules**
1. ID card mandatory for entry
2. Sign register at entrance
3. No personal books/files (except small notebook/loose sheets)
4. Strict silence
5. No marking/writing in books
6. Misbehavior → membership cancellation + disciplinary action
7. College authorities’ decision final
8. **Final-year project viva-voce:** Must return all books & obtain “No Dues”

**🏫 Department Library (Civil Engineering Example)**
- Established 2003 to supplement Central Library
- Holds: 402 Text/Reference books, 633 IS/IRC codes, 221 Project reports, 16 Mini-project reports, 6 CBTs

**💡 Tip:** Always carry your ID + Library card. Return/renew on time to avoid fines. For off-campus e-resource access, use **KNIBUS**.

*For the latest notices (e.g., holiday timings, new subscriptions), check the library notice board or the college website.*
```

**Retrieved Sources (Top 3):**
- [Central Library – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/libraries/)
- [Central Library – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/libraries/)
- [Central Library – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/libraries/)

---

### Question 12: who is the head of eee department library

- **Category:** `reliability_non_empty`
- **Expected Behavior:** Never return empty/blank output. If not found in sources, provide a clean NOT_FOUND response.
- **Automated Check:** ✅ PASS - Answer is non-empty.
- **Confidence:** High | **Latency:** 15.58s

**Current Output (Before):**
```text
Based on the official GPREC sources, the Department of Electrical and Electronics Engineering (EEE) is headed by **Dr. G. Kishor**. 

If you are asking about the Central Library, it is headed by a senior faculty member as the **Library in-charge** (supported by a Librarian and assistants), but the specific name of the Library in-charge is not detailed in the available sources.
```

**Retrieved Sources (Top 3):**
- [Central Library – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/libraries/)
- [Central Library – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/libraries/)
- [Central Library – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/libraries/)

---

### Question 13: detail information about the exam time table

- **Category:** `exams_ambiguity`
- **Expected Behavior:** Ambiguity handling: query lacks branch/semester. Ask via CLARIFY or show 5 newest matching notices with links, never dump 30 bullet points.
- **Automated Check:** ✅ PASS - Passed bullet count check.
- **Confidence:** High | **Latency:** 15.08s

**Current Output (Before):**
```text
Based on the official GPREC exam time table sources, here are the available exam schedules and notifications:

**From the Exam Time Table page (Source 1-3):**
- **02-03-2026**: M.Tech First Semester seating plan (March 2026)
- **02-03-2026**: Timetables for M.Tech I Sem (Reg S-2025) and M.Tech I & II Sem (Supp S-2022) End Examinations (March 2026)
- **15-02-2026**: IV & VI Sem II Sessional Exam Time Table (March 2026)
- **14-02-2026**: Notification for Registration of End Examinations for B.Tech IV, VI (S-23), VIII Sem (S-20) Regular & Supplementary Exams (April 2026) — including fee details for Scheme-23, Scheme-20, and Scheme-17.

**Additional exam-related items from the main college site (Sources 4-15):**
- June 2026 sessional and end-exam timetables, seating plans, and fee details for I & II Sem B.Tech.
- April 2026 practical exam schedules, revaluation notifications, and results for B.Tech IV, VI, VIII Sem and M.Tech I, II Sem.
- Hall ticket downloads for B.Tech I/II Sem (Scheme-2023) end exams (June 2026).

For the full, detailed time tables and downloadable PDFs, you can visit the official **Exam Time Table** page:  
👉 [https://www.gprec.ac.in/academics/examinations/exam-time-table/](https://www.gprec.ac.in/academics/examinations/exam-time-table/)

If you need specific exam dates or hall tickets, please let me know your semester and branch!
```

**Retrieved Sources (Top 3):**
- [Exam Time Table – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/academics/examinations/exam-time-table/)
- [Exam Time Table – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/academics/examinations/exam-time-table/)
- [Exam Time Table – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/academics/examinations/exam-time-table/)

---

