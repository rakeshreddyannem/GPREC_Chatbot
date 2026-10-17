# Regression Results (AFTER_STEP3_RESULTS)

**Execution Timestamp:** 2026-10-15 09:46:52

| # | Query | Check Status | Confidence | Latency | Automated Check Reason |
|---|-------|--------------|------------|---------|-------------------------|
| 1 | give me the information regarding the placements | ✅ PASS | High | 37.66s | Passed basic reliability check. |
| 2 | details about eee department faculties list and their designations | ✅ PASS | High | 91.21s | Passed basic reliability check. |
| 3 | list the PhD faculties | ✅ PASS | High | 0.02s | Passed ambiguity check. |
| 4 | list the phd faculties of eee department | ✅ PASS | High | 30.4s | Passed inference restriction check. |
| 5 | information about the boys hostel | ✅ PASS | High | 30.31s | Passed basic reliability check. |
| 6 | about the clubs in college | ✅ PASS | High | 22.15s | Passed basic reliability check. |
| 7 | give me detail information about each and every faculty in eee department | ✅ PASS | High | 105.88s | Passed basic reliability check. |
| 8 | who is the principal of this college | ✅ PASS | High | 9.52s | Correctly identified Principal Dr. B. Sreenivasa Reddy. |
| 9 | information about ITCA | ✅ PASS | High | 5.99s | Passed date check. |
| 10 | what is fee structure of EEE department | ✅ PASS | High | 30.32s | Single response check passed. |
| 11 | information about library | ✅ PASS | High | 56.3s | Passed library source relevance check. |
| 12 | who is the head of eee department library | ✅ PASS | High | 13.91s | Answer is non-empty. |
| 13 | detail information about the exam time table | ✅ PASS | High | 0.0s | Passed bullet count check. |


## Detailed Responses per Question

### Question 1: give me the information regarding the placements

- **Category:** `placements`
- **Expected Behavior:** Return factual placement statistics/records from official sources, no hallucinated packages or numbers, single clean response.
- **Automated Check:** ✅ PASS - Passed basic reliability check.
- **Confidence:** High | **Latency:** 37.66s

**Output (after_step3_results):**
```text
Based on the official GPREC sources, here is the information regarding placements:

### **Training & Placement Cell**
The Training and Placement Cell is the central department responsible for campus placements and training. It is headed by the Training and Placement Officer (TPO).

*   **TPO:** Dr. K. Govardhan Reddy, Professor of CSE(AIML).
*   **Committee Composition:** The cell is supported by a full-time Manager Corporate Relations, an Assistant Training and Placement Officer, and a committee comprising one Professor In-charge, three faculty members, and five student members from each department.

### **Objectives of the Cell**
The main goals are to:
*   Prepare students to meet industry skill requirements.
*   Bridge the gap between academic teaching and industry needs.
*   Provide training in technical skills, soft skills, and management skills.
*   Conduct mock tests, group discussions, and mock interviews.
*   Arrange campus interviews for final-year students.
*   Facilitate internship opportunities.
*   Maintain an alumni network.

### **Placement Training**
The college provides extensive training to all students from their first year.
*   **Total Training:** Approximately 300 hours of training are distributed across all semesters.
*   **Training Areas:** Quantitative Ability, Logical Reasoning, Verbal Ability, Programming Skills, Communication Skills, Group Discussion, Interview Skills, and Personality Development.
*   **Resource Persons:** Training is conducted by faculty from professional training institutes (like PrepInsta, LearnSquare Technologies, etc.), distinguished alumni, and internal faculty.

### **Internships**
The college has a dedicated committee for Internships and Industrial Training, led by Dr. Y.V.Siva Reddy. The committee helps students secure summer and final semester internships in government organizations, R&D labs, IT companies, core companies, and other reputable institutions.

### **T&P Club**
A student club, the T&P Club, operates under the guidance of the Training and Placement Department. Its aim is to assist in organizing placement events, create awareness about the process, and connect students with alumni.

**Please Note:** The provided sources do not contain specific data on recent placement statistics, a list of visiting companies, or the highest/average salary packages. For the most current placement records and details on specific companies, you are advised to contact the Training and Placement Cell directly or visit the official GPREC website for any published placement reports.
```

**Retrieved Sources (Top 3):**
- [Verified Fact: Training and Placement Officer (Verified by admin on 2026-10-12)](https://gprec.ac.in/training-placements/)
- [Official Directory: Training & Placement Officer - Dr. K. Govardhan Reddy](https://gprec.ac.in/training-placements/)
- [Training & Placements – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/training-placements/)

---

### Question 2: details about eee department faculties list and their designations

- **Category:** `departments_faculty`
- **Expected Behavior:** List EEE faculty members and their official designations strictly matching retrieved text.
- **Automated Check:** ✅ PASS - Passed basic reliability check.
- **Confidence:** High | **Latency:** 91.21s

**Output (after_step3_results):**
```text
**Verified Aggregate Statistics (Official GPREC EEE Department Page – Source 1)**  
- Department Head: **Dr. G. Kishor**  
- Total teaching faculty: **29** (breakdown: **4 Professors, 8 Associate Professors, 17 Assistant Professors**)  
- Explicitly confirmed Ph.D. faculty count: **17** (as directly stated in the source)  
- *Note:* The source provides this aggregate breakdown but does not list individual faculty names beyond the head of department.

**Individually Confirmed EEE Faculty with Explicit Doctorate (Dr. prefix) and Designations**  
These entries are verified across multiple official GPREC sources where the “Dr.” prefix or explicit “Ph.D.” qualification appears in staff listings:

| Faculty Name | Designation & Department | Source(s) |
|--------------|--------------------------|-----------|
| Dr. G. Kishor | Professor & Head, Dept of EEE | Source 1, Source 3/4 |
| Dr. K. Jagadeesh | Assistant Professor, Dept of EEE | Source 3, Source 4, Source 6 |
| Dr. S. Anil Kumar | Assistant Professor, Dept of EEE | Source 6 |
| Dr. V. Anantha Lakshmi | Associate Professor, Dept of EEE | Source 6 |
| Dr. G. Sreenivasa Reddy | Associate Professor, Dept of EEE | Source 5 |
| Dr. K. Sree Gowri | Professor, Dept of EEE | Source 5 |
| Dr. K. Rajesh | Assistant Professor, Dept of EEE | Source 9 (Internship committee) |
| Dr. Y. V. Siva Reddy | Dean, Internships and Industrial Trainings (college-wide role associated with EEE) | Source 9 |

**Important Reliability Note**  
Per GPREC chatbot rules: *A person counts as Ph.D. faculty ONLY if the source explicitly states a doctorate (a “Dr.” prefix in staff lists or explicit “Ph.D.” qualification).* Being a jury member, reviewer, resource person, or Ph.D. supervisor is **not** evidence that the faculty holds a doctorate.  

The sources list numerous EEE faculty with designations (Professor, Associate Professor, Assistant Professor) **without** the “Dr.” prefix. For those entries, Ph.D. status is **not** confirmed in official sources, and such qualification must not be inferred.

**Availability of Full Faculty Directory**  
The official GPREC sources do **not** publish a complete, individual-name faculty directory beyond the aggregate statistics and the explicitly confirmed entries above. For a full staff list, designations, or detailed qualification records, please contact the EEE department office or refer to the official GPREC administrative portals/staff directories.
```

**Retrieved Sources (Top 3):**
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)
- [Humanities and Basic Sciences – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/humanities-and-basic-sciences/)
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)

---

### Question 3: list the PhD faculties

- **Category:** `ambiguity_faculty`
- **Expected Behavior:** Ambiguity handling: query lacks department. Must ask CLARIFY (Which department?) or explicitly state the department scope. Strictly count only people with explicit doctorate (Dr. prefix or Ph.D degree).
- **Automated Check:** ✅ PASS - Passed ambiguity check.
- **Confidence:** High | **Latency:** 0.02s

**Output (after_step3_results):**
```text
Which department's Ph.D. faculties would you like to see?
```

**Retrieved Sources (Top 3):**
- *None*

---

### Question 4: list the phd faculties of eee department

- **Category:** `forbid_inference_faculty`
- **Expected Behavior:** Forbid inference: Only list persons explicitly confirmed with doctorate ('Dr.' or Ph.D). Being a jury member or resource person is NOT evidence. If incomplete, state 'the sources only confirm X of Y'.
- **Automated Check:** ✅ PASS - Passed inference restriction check.
- **Confidence:** High | **Latency:** 30.4s

**Output (after_step3_results):**
```text
Based on the official GPREC sources provided, the following **EEE faculty members are explicitly confirmed with a "Dr." prefix** (indicating a doctorate):

| Name | Designation | Source(s) |
|------|-------------|-----------|
| Dr. G. Kishor | Professor & Head of Department | Source 2, Source 3 |
| Dr. K. Sri Gowri | Professor | Source 3 |
| Dr. T. Brahmananda Reddy | Professor | Source 3 |
| Dr. V. Anantha Lakshmi | Associate Professor | Source 3, Source 8 |
| Dr. G. Sreenivas Reddy | Associate Professor | Source 3, Source 4 |
| Dr. G. Satheesh | Associate Professor | Source 3 |
| Dr. C. Harinatha Reddy | Associate Professor | Source 3 |
| Dr. K. Jagadeesh | Assistant Professor | Source 3, Source 8 |
| Dr. S. Anil Kumar | Assistant Professor | Source 3, Source 8 |
| Dr. G. VenkataSubba Reddy | (Designation not explicitly stated in snippet) | Source 3 |

**Total explicitly confirmed:** **10 faculty members** (9 with clear designations + 1 with Dr. prefix only).

**Department-wide figure:** The EEE department page states the department has **“17 Ph.D.’s and 12 M.Tech.’s”** (Source 2).  
**Therefore, the sources only confirm 10 of the 17 Ph.D. faculty members by name.** The remaining 7 Ph.D. holders are not individually named in the provided excerpts.
```

**Retrieved Sources (Top 3):**
- [Electronics and Communication Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electronics-and-communication-engineering/)
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)

---

### Question 5: information about the boys hostel

- **Category:** `hostel`
- **Expected Behavior:** Non-empty hostel details, facilities, rules from official sources. Never expose private phone numbers or default credentials.
- **Automated Check:** ✅ PASS - Passed basic reliability check.
- **Confidence:** High | **Latency:** 30.31s

**Output (after_step3_results):**
```text
Based on the official GPREC sources provided:

**Boys Hostel**

*   **Location:** The Boys Hostel is located adjacent to the college campus.
*   **Availability:** It is available for B.Tech boys.
*   **Fees:**
    *   **Ordinary Room (Common Bathroom):** Rs. 75,500 per year.
    *   **Additional Charges:** Upon first-time admission, students must pay a non-refundable maintenance fund of Rs. 5,000 and a refundable caution deposit of Rs. 5,000.
*   **Contact:** For further details, you may contact Dr. Ishthaq Ahmed, Associate Professor of CSE, at [Contact the department office for details].
```

**Retrieved Sources (Top 3):**
- [Verified Fact: Boys Hostel (Verified by admin on 2026-10-12)](https://gprec.ac.in/hostel/)
- [Hostels – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://gprec.ac.in/hostel)
- [NASHA MUKT COMMITTEE (NMC) – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/nasha-mukt-committee-nmc)

---

### Question 6: about the clubs in college

- **Category:** `clubs`
- **Expected Behavior:** Non-empty information on student clubs/activities from official college sources without hallucination.
- **Automated Check:** ✅ PASS - Passed basic reliability check.
- **Confidence:** High | **Latency:** 22.15s

**Output (after_step3_results):**
```text
Based on the official GPREC sources, the college has several active clubs and forums for student development. Here is a summary:

*   **IEI Students' Chapter:** Conducts seminars on technical topics, quizzes, and lectures.
*   **Bhuvana Vijayam:** The literary and cultural association that provides a platform for students to exhibit talents in culture and literature.
*   **Center for Awareness & Discussion:** Works to familiarize students with current topics through group discussions and quizzes.
*   **Vivekananda Study Circle:** Focuses on universal brotherhood, selfless service to society, and inculcating noble values in youth.
*   **Art of Living Forum:** Aims to bring joy, a stress-free mind, a healthy body, and a blossomed life to students and faculty.
*   **T&P Club (Training & Placement Club):** This club operates under the guidance of the Training and Placement Department. Its members are selected students from different years and branches who maintain high attendance and marks. The club's objectives are to:
    1.  Assist the training and placement cell in organizing events.
    2.  Create awareness about placement and training processes.
    3.  Provide opportunities for students to learn teamwork and event organization.
    4.  Promote managerial and leadership skills.
    5.  Connect students with alumni.

The sources confirm these specific clubs. For a complete and official list, you can visit the [Student Clubs page](https://www.gprec.ac.in/campus-life/student-clubs) on the GPREC website.
```

**Retrieved Sources (Top 3):**
- [Student Clubs – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/student-clubs)
- [T & P Club – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/campus-life/student-clubs/t-p-club)
- [GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://gprec.ac.in)

---

### Question 7: give me detail information about each and every faculty in eee department

- **Category:** `departments_faculty`
- **Expected Behavior:** Grounded faculty details without fabricating designations or private personal phone numbers/emails.
- **Automated Check:** ✅ PASS - Passed basic reliability check.
- **Confidence:** High | **Latency:** 105.88s

**Output (after_step3_results):**
```text
**Official GPREC Source Aggregation (Rule 1 & 2 Compliance):**
Per Source 1, the Department of Electrical and Electronics Engineering (EEE) at G. Pulla Reddy Engineering College has **29 teaching faculty** with the following verified breakup:  
- **4 Professors**  
- **8 Associate Professors**  
- **17 Assistant Professors**  

The sources aggregate state that **17 faculty hold Ph.D. degrees** and **12 hold M.Tech. degrees**, but **the official sources do not provide a per‑faculty breakdown of who holds which qualification unless explicitly marked with a `"Dr."` prefix in a staff list or official directory entry** (Rule 3).

**Reliability Rule 3 – Ph.D. Status Confirmation:**  
Only faculty with an explicit `"Dr."` prefix in staff lists or an explicit `"Ph.D."` qualification are confirmed to hold a doctorate. Being a jury member, reviewer, resource person, or Ph.D. supervisor is **not** evidence of a doctorate. Accordingly, only the faculty listed below have their doctorate status verified from the sources.

---

### **Confirmed Ph.D. Faculty (Explicit `"Dr."` Prefix in Sources)**
| Faculty Name | Designation (as in source) | Source(s) | Doctorate Status |
|--------------|----------------------------|-----------|------------------|
| Dr. G. Kishor | HoD, EEE Department | Source 1 ("The department is headed by Dr. G.Kishor.") | Explicit `"Dr."` prefix confirms Ph.D. |
| Dr. C. Harinatha Reddy | Associate Professor, EEE | Source 2 ("1 Dr.C. Harinatha Reddy, Assoc Prof of EEE Convener") | Explicit `"Dr."` prefix confirms Ph.D. |
| Dr. K. Jagadeesh | Assistant Professor, EEE | Source 3 ("Dr. K. Jagadeesh Asst. Prof. of EEE"); Source 6 activity lines | Explicit `"Dr."` prefix confirms Ph.D. |
| Dr. S. Anil Kumar | Assistant Professor, EEE | Source 3 ("Dr. S. Anil Kumar, Asst. Prof. of EEE"); Source 6 activity lines | Explicit `"Dr."` prefix confirms Ph.D. |
| Dr. V. Anantha Lakshmi | Associate Professor, EEE | Source 3 ("Dr. V. Anantha Lakshmi, Assoc. Prof. of EEE"); Source 6 activity lines | Explicit `"Dr."` prefix confirms Ph.D. |
| Dr. K. Rajesh | Assistant Professor, EEE | Source 8 ("Dr.K.Rajesh, Asst Prof of EEE : Member") | Explicit `"Dr."` prefix confirms Ph.D. |

---

### **Faculty Named in Official Sources with Designations (Doctoral Status Not Confirmed per Rule 3)**
The sources list several EEE faculty by name and rank, but **without an explicit `"Dr."` prefix** in the provided lines. Their doctoral status cannot be inferred (Rule 3).

**Professors (aggregate 4; 2 explicitly named):**  
- **T. Brahmananda Reddy**, Professor, EEE Dept (Source 6: `"T Brahmananda Reddy, Professor, EEE Dept..."`)  
- **K. Sri Gowri**, Professor, EEE Dept (Source 6: `"K Sri Gowri, Professor, EEE Dept acted as SPOC rated-A under SWAYAM-NPTEL..."`)

**Associate Professors (aggregate 8; some already listed above with confirmed Ph.D.):**  
- **G. Sreenivasa Reddy**, Associate Professor, EEE (Source 6: `"G. Sreenivasa Reddy, Associate Professor, Department of Electrical and Electronics Engineering (EEE)"`)  
- **G. Satheesh**, Associate Professor, EEE Dept (Source 6: `"G Satheesh, Associate Professor, EEE Dept of GPREC..."`)  
- *(Dr. C. Harinatha Reddy and Dr. V. Anantha Lakshmi are already listed above with confirmed Ph.D. status.)*

**Assistant Professors (aggregate 17; some already listed above with confirmed Ph.D.):**  
- **Mrs. G. Haritha**, Assistant Professor, EEE Dept (Sources 6, 7; no `"Dr."` prefix in the provided lines)  
- **B. Amarnath Naidu**, Assistant Professor, EEE Dept (Source 6: `"B Amarnath Naidu, Assistant Professor, EEE Dept completed AICTE-QIP-PG..."`)  
- **K. Niteesh Kumar**, Assistant Professor, EEE Dept (Source 6: `"K Niteesh Kumar, Assistant Professor, EEE Dept completed AICTE-QIP-PG..."`)  
- **D. Vannurappa**, Assistant Professor, EEE Dept (Source 5: `"D. Vannurappa, Asst. Professor, EEE Dept : Member"`)  
- *(Dr. K. Jagadeesh, Dr. S. Anil Kumar, and Dr. V. Anantha Lakshmi are already listed above with confirmed Ph.D. status.)*

---

### **Critical Compliance Notes (Rules 7 & 3)**
1. **Complete per‑faculty directory unavailable:** The official GPREC sources provided do **not** contain a comprehensive, per‑faculty directory listing all 29 EEE faculty members with individual qualifications, contact details, or complete assignment lists. For the remaining faculty not explicitly named above, their specific details are **not available in the official sources** (Rule 7).  
2. **No inference of Ph.D. status:** Activities such as supervising Ph.D. candidates, serving as jury members, or receiving awards do **not** confirm a faculty member holds a doctorate (Rule 3). Only the 6 faculty listed under *"Confirmed Ph.D. Faculty"* have explicit `"Dr."` prefixes in the sources.  
3. **No generic fallbacks:** This response states clearly where information is missing from the official sources, per Rule 7, without combining partial text with a generic `"I couldn't find"` fallback.  

*All information above is drawn exclusively from the official GPREC context sources provided (Sources 1–9). No external data, inferences, or invented details have been included.*
```

**Retrieved Sources (Top 3):**
- [Electrical and Electronics Engineering – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)
- [CAA Cell – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/caa-cell/)
- [Extra Academic Activities (EAA) Cell – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/i-eee)

---

### Question 8: who is the principal of this college

- **Category:** `leadership`
- **Expected Behavior:** Answer college leadership (Principal: Dr. B. Sreenivasa Reddy) from directory/official source, or explain missing coverage.
- **Automated Check:** ✅ PASS - Correctly identified Principal Dr. B. Sreenivasa Reddy.
- **Confidence:** High | **Latency:** 9.52s

**Output (after_step3_results):**
```text
Based on the verified GPREC entity directory and official college sources, the Principal of G. Pulla Reddy Engineering College is **Dr. B. Sreenivasa Reddy**. 

This is confirmed by two authoritative records:
- Entity: Principal (Administration) – Name: Dr. B. Sreenivasa Reddy | Designation: Principal & Professor | Qualification: M.Tech., Ph.D. (Source: https://gprec.ac.in)
- Principal – Name: Dr. B. Sreenivasa Reddy [Verified by admin on 2026-10-12] (Source: https://gprec.ac.in)
```

**Retrieved Sources (Top 3):**
- [Verified Fact: Principal (Verified by admin on 2026-10-12)](https://gprec.ac.in)
- [Official Directory: Principal - Dr. B. Sreenivasa Reddy](https://gprec.ac.in)
- [Helping Hands – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/alumni/helping-hands/)

---

### Question 9: information about ITCA

- **Category:** `acronyms_dates`
- **Expected Behavior:** No crawl/first_seen date presented as notice date; do NOT expand ITCA unless expansion explicitly appears in source.
- **Automated Check:** ✅ PASS - Passed date check.
- **Confidence:** High | **Latency:** 5.99s

**Output (after_step3_results):**
```text
Based on the official GPREC sources provided, here is the information about ITCA:

## ITCA (Intensive Training Program for Career Advancement)

**What is ITCA?**
ITCA stands for "Intensive Training Program for Career Advancement" at G. Pulla Reddy Engineering College (Autonomous).

**Login Information:**
- The ITCA portal can be accessed at: `http://examcell.gprec.ac.in/ITPPLogin.aspx`
- Students need their **Roll Number** and **Password** (in DDMMYYYY format) to log in.

**Login Issues:**
If students encounter any problems with login, they are instructed to **contact the Training & Placement Cell**.

**Corrections:**
Any corrections related to ITCA should be reported to the **Training & Placement Cell**.

---
*Note: The sources indicate that ITCA is a career advancement training program, but specific details about the program content, schedule, or eligibility criteria are not available in the provided official sources.*
```

**Retrieved Sources (Top 3):**
- [G. Pulla Reddy Engineering College (Autonomous)](https://examcell.gprec.ac.in/studentserviceslogin.aspx)
- [CSE- Data Science (CSD) – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/cse-data-science/)
- [Computer Science and Technology – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/computer-science-and-technology/)

---

### Question 10: what is fee structure of EEE department

- **Category:** `fees_ambiguity`
- **Expected Behavior:** Single clean response (no duplicate plain text + not found card). Give real fee amounts with academic year / as-of date or clearly state document status.
- **Automated Check:** ✅ PASS - Single response check passed.
- **Confidence:** High | **Latency:** 30.32s

**Output (after_step3_results):**
```text
Based on the official GPREC sources and verified ground truth:

## Fee Structure for EEE Department (B.Tech)

**Tuition Fee (Academic Year 2024-25 & 2025-26):**
- **Category-A (Convenor Quota through EAPCET):** ₹70,000 per annum
- **Category-B (Management/NRI Quota):** As per AP State Government guidelines

**Important Notes:**
- The tuition fee structure is prescribed by the Andhra Pradesh Higher Education Regulatory and Monitoring Commission (APHERMC) / Government of Andhra Pradesh for Autonomous Engineering Colleges.
- This fee applies college-wide across all engineering branches, including EEE, CSE, ECE, ME, and CE.
- Additional university, examination, and hostel fees apply separately.

**For Academic Year 2026-27:**
- The tuition fee is subject to revision by the Government of Andhra Pradesh.

**Source:** [GPREC Admissions - Fee Structure](https://gprec.ac.in/admissions/) | Verified by admin on 2026-10-13

For the most current and detailed fee breakdown, please refer to the official APHERMC notifications or visit the GPREC admissions office.
```

**Retrieved Sources (Top 3):**
- [Verified Fact: Fee Structure (Verified by admin on 2026-10-13)](https://gprec.ac.in/admissions/)
- [Verified Fact: Fee Structure (Verified by admin on 2026-10-13)](https://gprec.ac.in/admissions/)
- [Fee Structure – GPREC > G.Pulla Reddy Engineering College – Kurnool, AP, INDIA](https://www.gprec.ac.in/admissions/fee-structure/)

---

### Question 11: information about library

- **Category:** `library`
- **Expected Behavior:** Library resources and timings. Filter out unrelated sources like Alumni or RTI.
- **Automated Check:** ✅ PASS - Passed library source relevance check.
- **Confidence:** High | **Latency:** 56.3s

**Output (after_step3_results):**
```text
**Central Library – G. Pulla Reddy Engineering College (GPREC), Kurnool**  

**Location & General Facilities**  
- The Central Library is situated on the GPREC campus and is described as spacious, well‑ventilated and furnished with adequate seating.  
- It serves all students and staff; about 150 persons can use the library simultaneously under an Open Access System.  

**Collection & Resources**  
- **Print collection:** ≈ 66,106 volumes and ≈ 14,153 titles covering core engineering subjects as well as general subjects.  
- **Reference & reading room:** A good number of titles are earmarked as reference books and a spacious reading room is attached.  
- **Classification:** Books are arranged and classified according to the Dewey Decimal Classification Scheme.  
- **Journals:** Subscription to 84 National and 979 International journals.  
- **Digital Library (Electronics Resources Wing):**  
  - 50 computer systems with 1 Gbps internet bandwidth.  
  - Access to national/international e‑journals and databases such as IEEE (≈250), Elsevier Science Direct (≈369), SpringerNature (≈503), DELNET, OLD QUESTION PAPERS – Kurnool, National Digital Library of India (NDLI), KNIBUS (off‑campus access) and British Council Library.  
- **Automation & Infrastructure:** Fully automated with SLIM 21 software; supported by 2 servers and 19 core‑i3 computers for library automation.  
- **Reprographic Services:** Cannon IR 4525 photocopier and laser printers are available.  
- **NPTEL Resources:** Materials for CSE, CE, ME, EEE, ECE, Basic Science and Humanities can be accessed through 12 core‑i3 computers.  

**Working Hours**  
- All working days: **9.00 AM – 7.00 PM**.  

**Library Membership & Cards**  
- **Eligibility:** All students and staff are automatic members.  
- **Number of cards issued:**  
  - Students (except final year): **3 cards each**  
  - Final‑year students: **4 cards each**  
  - Faculty members: **6 cards each**  
  - Research scholars: **4 cards each**  
- **Obtaining a card:** Must produce a valid college ID card.  
- **Card usage rules:**  
  - Cards are **non‑transferable**.  
  - **Only one book** may be borrowed per card.  
  - Members are responsible for the safety and security of borrowed books.  
  - ID card **and** library card must be shown to borrow books.  

**Borrowing & Renewal**  
- **Loan period:**  
  - General books (excluding reference copies & periodicals): **14 days** for students.  
  - Faculty: **one month**.  
- **Renewals:** Up to **two renewals** allowed if no reservations exist; renewal requires physical presentation of the book and ID card.  
- **Reservation:** Members may reserve a book already issued; reserved books are held at the counter for two days after return. If not collected within two days, the book goes to the waiting list and the reserving member loses seniority.  

**Overdue Charges**  
- First 7 days: **₹1 per day**.  
- From the 8th day onward: **₹2 per day**.  
- Holidays are counted in the overdue period.  
- If the due date falls on a holiday, the next working day becomes the due date.  
- If a book is not returned within **50 days** of the due date, the **full cost of the book plus overdue charges** is levied.  

**Loss & Damage of Books**  
- Loss must be reported to the librarian immediately in writing.  
- The borrower may replace the lost book with a good copy of a similar title **only after obtaining permission from the Head of the Institution**.  
- Failure to replace within the stipulated time results in **twice the book’s cost plus overdue charges**.  
- Borrowers are liable for any damage or loss and must ensure the book’s condition at borrowing.  

**Library Card Loss**  
- Report loss to the librarian immediately in writing.  
- Duplicate card issued on payment of **₹50 per card**.  
- The member bears sole responsibility for any misuse of a lost card.  

**Clearance / “No Dues” Certificate**  
- All members must return all borrowed books at the end of each academic year.  
- Faculty resigning or leaving the college must obtain a **“NO DUES”** certificate after returning books and surrendering all library cards.  
- Students completing their course must also obtain a **“NO DUES”** certificate after returning books and surrendering cards.  

**General Library Rules**  
- Entry permitted only with a valid ID card.  
- All members must sign the entrance register acknowledging the rules.  
- Personal books, files, or articles (except a small notebook or loose sheets) are **not allowed** inside.  
- **Strict silence** must be maintained.  
- **No marking, writing, tearing, or staining** of library books.  
- Misbehavior can lead to cancellation of membership and serious disciplinary action.  
- The college authorities’ decision is final in all library matters.  
- Before the final project viva‑voce, candidates must return all borrowed books and collect the “no dues” certificate.  

**Note:** All information above is drawn exclusively from the official GPREC Central Library sources provided. If any detail is not covered in those sources, it is not available in the official documentation.
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
- **Confidence:** High | **Latency:** 13.91s

**Output (after_step3_results):**
```text
Based on the verified official records, the EEE Department Library is maintained under the supervision of the Head of the Department, **Dr. G. Kishor**, along with a designated faculty library in-charge. The specific name of the designated faculty library in-charge is not mentioned in the available official sources.
```

**Retrieved Sources (Top 3):**
- [Verified Fact: EEE Head of Department (Verified by admin on 2026-10-12)](https://gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)
- [Verified Fact: EEE Department Library (Verified by admin on 2026-10-12)](https://gprec.ac.in/programs-offered/electrical-and-electronics-engineering/)
- [Official Directory: Librarian - Sri. P. Gopinath](https://gprec.ac.in/library/)

---

### Question 13: detail information about the exam time table

- **Category:** `exams_ambiguity`
- **Expected Behavior:** Ambiguity handling: query lacks branch/semester. Ask via CLARIFY or show 5 newest matching notices with links, never dump 30 bullet points.
- **Automated Check:** ✅ PASS - Passed bullet count check.
- **Confidence:** High | **Latency:** 0.0s

**Output (after_step3_results):**
```text
Which program and semester exam timetable are you looking for? (e.g., B.Tech IV Sem R20)
```

**Retrieved Sources (Top 3):**
- *None*

---

