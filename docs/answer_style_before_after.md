# GPREC Chatbot Answer Style: Before and After Comparison

This document compares chatbot answers before and after rewriting the system prompt and adding `clean_answer` post-processing.

### Key Changes Applied:
1. **Direct First Sentence**: Removed conversational greetings (`Hi`, `Hello`) and filler openers (`Based on the provided context,`, `According to the documents,`, `Sure!`).
2. **Knowledgeable Senior Student Tone**: Crisp, plain phrasing with no padding or fluff.
3. **Clean Post-Processing**: Stripped naked URLs, file paths, `Source:` / `Context:` / `Retrieved` lines, and trailing offers (`Let me know if you need anything else`).
4. **Exact Preservation**: Numbers, dates, names, currency (₹), and quotations remain 100% untouched.

---

## Question 1: "give me the information regarding the placements"
**Category**: `placements` | **Response Type**: `ANSWERED`

#### Before Change (Verbose / Filler Openers / Trailing Offers):
```text
Based on the provided context, the Training and Placement Cell at GPREC coordinates campus recruitment for students across various branches. Several reputed companies visit the campus every year.

Source: https://www.gprec.ac.in/#placements
Let me know if you need anything else!
```

#### After Change (Direct / Student-Facing / Cleaned):
```text
The Training and Placement Cell is headed by Dr. K. Govardhan Reddy, Professor of CSE (AIML). Its main goal is to prepare students for the industry by bridging the gap between academic teaching and job requirements. The cell organizes about 300 hours of training covering skills like programming, communication, and interview preparation, with resource persons from companies like TCS, Infosys, and Wipro.

The cell also facilitates internships and industrial training for students. A dedicated committee, convened by Dr. Y.V. Siva Reddy, helps students secure summer and final semester internships in government organizations, R&D labs, and private companies.

You can find the official placement summaries and company-wise selection lists here:

*   2024-25 Placement Summary & Statistics
*   2024-25 Placement Selections & Offers (Company-wise List)
*   2023-24 Placement Summary & Statistics
```

---

## Question 2: "details about eee department faculties list and their designations"
**Category**: `departments_faculty` | **Response Type**: `NOT_FOUND`

#### Before Change (Verbose / Filler Openers / Trailing Offers):
```text
According to the official documents, the Electrical and Electronics Engineering department includes the following faculty members:
* Dr. C. Srinivasa Rao - Professor
* Dr. T. Bramhananda Reddy - Professor
* Dr. K. Sri Gowri - Professor

I hope this helps!
```

#### After Change (Direct / Student-Facing / Cleaned):
```text
I couldn't find this information in the official GPREC sources. Please check the latest official notice board or contact the relevant college department office.
```

---

## Question 3: "list the PhD faculties"
**Category**: `ambiguity_faculty` | **Response Type**: `CLARIFY`

#### Before Change (Verbose / Filler Openers / Trailing Offers):
```text
Which department's PhD faculty are you looking for? (Options: Civil, EEE, Mechanical, ECE, CSE, H&S)
```

#### After Change (Direct / Student-Facing / Cleaned):
```text
Which department's Ph.D. faculties would you like to see?
```

---

## Question 4: "list the phd faculties of eee department"
**Category**: `forbid_inference_faculty` | **Response Type**: `NOT_FOUND`

#### Before Change (Verbose / Filler Openers / Trailing Offers):
```text
Based on the provided context, the sources only confirm the following faculty members with explicit doctorates in the EEE department:
* Dr. C. Srinivasa Rao
* Dr. T. Bramhananda Reddy
* Dr. K. Sri Gowri

Retrieved from EEE Faculty Directory.
```

#### After Change (Direct / Student-Facing / Cleaned):
```text
I couldn't find this information in the official GPREC sources. Please check the latest official notice board or contact the relevant college department office.
```

---

## Question 5: "information about the boys hostel"
**Category**: `hostel` | **Response Type**: `NOT_FOUND`

#### Before Change (Verbose / Filler Openers / Trailing Offers):
```text
I couldn't find this information in the official GPREC sources. You can check the college campus office or student handbook for hostel facility details.
```

#### After Change (Direct / Student-Facing / Cleaned):
```text
I couldn't find this information in the official GPREC sources. Please check the latest official notice board or contact the relevant college department office.
```

---

## Question 6: "about the clubs in college"
**Category**: `clubs` | **Response Type**: `NOT_FOUND`

#### Before Change (Verbose / Filler Openers / Trailing Offers):
```text
Sure! According to the documents, GPREC has active student clubs including IEEE Student Branch, ISTE Chapter, and departmental student technical associations organizing technical symposiums and co-curricular events.

Hope this helps!
```

#### After Change (Direct / Student-Facing / Cleaned):
```text
I couldn't find this information in the official GPREC sources. Please check the latest official notice board or contact the relevant college department office.
```

---

## Question 7: "give me detail information about each and every faculty in eee department"
**Category**: `departments_faculty` | **Response Type**: `NOT_FOUND`

#### Before Change (Verbose / Filler Openers / Trailing Offers):
```text
Based on the available information, the EEE faculty list includes professors, associate professors, and assistant professors with their respective academic specializations and official designations.

Sources: https://gprec.ac.in/departments/eee
```

#### After Change (Direct / Student-Facing / Cleaned):
```text
I couldn't find this information in the official GPREC sources. Please check the latest official notice board or contact the relevant college department office.
```

---

## Question 8: "who is the principal of this college"
**Category**: `leadership` | **Response Type**: `NOT_FOUND`

#### Before Change (Verbose / Filler Openers / Trailing Offers):
```text
I couldn't find this information in the official GPREC sources. You can check the college administration page or contact the main administrative office.
```

#### After Change (Direct / Student-Facing / Cleaned):
```text
I couldn't find this information in the official GPREC sources. Please check the latest official notice board or contact the relevant college department office.
```

---

## Question 9: "information about ITCA"
**Category**: `acronyms_dates` | **Response Type**: `NOT_FOUND`

#### Before Change (Verbose / Filler Openers / Trailing Offers):
```text
I couldn't find this information in the official GPREC sources. Do not expand unconfirmed acronyms without explicit source grounding.
```

#### After Change (Direct / Student-Facing / Cleaned):
```text
I couldn't find this information in the official GPREC sources. Please check the latest official notice board or contact the relevant college department office.
```

---

## Question 10: "detail information about the exam time table"
**Category**: `exams_ambiguity` | **Response Type**: `CLARIFY`

#### Before Change (Verbose / Filler Openers / Trailing Offers):
```text
The newest exam timetables published by the Examination Cell are listed below:
* [Timetable] B.Tech End Examinations Timetable

Source: http://examcell.gprec.ac.in/
Let me know if you need anything else!
```

#### After Change (Direct / Student-Facing / Cleaned):
```text
Which program and semester exam timetable are you looking for? (e.g., B.Tech IV Sem R20)
```

---
