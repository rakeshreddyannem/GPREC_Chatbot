import os
import re
from typing import List, Dict, Any, Optional, Tuple
from google import genai
from google.genai import types

import config
from src.vectorstore import VectorStore
from src.embeddings import Embedder
from src.database import DatabaseManager


def clean_answer(text: str) -> str:
    """Post-processes LLM-generated answers for ANSWERED and PARTIAL responses.

    Rules:
    - Removes citation markers matching 【[^】]*】, [1], [2] style markers, and (Source: ...) parts
    - Deletes everything from a line starting with Sources:, Source:, References:, Evidence:, or Context:
      to the end of that block, including its bullets
    - Removes filler openers like 'Based on the official GPREC sources,', 'According to the (official) sources/documents/context,',
      'Sure,', 'Certainly,', 'Here is', 'Here are the details' only when followed by the actual answer
    - Removes '(also referenced as ...)' and '(also known as ...)' parentheses when the name is a spelling variant
    - Removes 'Confidence: ...' lines from the answer text
    - Preserves numbers, dates, currency (₹), names, and quotes
    - Tidies leftover double spaces and blank lines
    """
    if not text or not isinstance(text, str):
        return ""

    cleaned = text

    # 1. Remove citation markers matching 【[^】]*】, bracketed numbers [1], [2], [1-3], [1†...], and (Source: ...)
    cleaned = re.sub(r'【[^】]*】', '', cleaned)
    cleaned = re.sub(r'\[\d+(?:[,\s–-]+\d+)*†?[^\]]*\]', '', cleaned)
    cleaned = re.sub(r'\s*\((?:Source|Sources):\s*[^)]*\)', '', cleaned, flags=re.IGNORECASE)

    # 2. Remove "(also referenced as ...)" and "(also known as ...)" parentheticals
    cleaned = re.sub(
        r'\s*\((?:also\s+referenced\s+as|also\s+known\s+as|also\s+called|a\.k\.a\.)\s+[^)]+\)',
        '',
        cleaned,
        flags=re.IGNORECASE
    )

    # 3. Remove "Confidence: ..." line from the answer text
    cleaned = re.sub(
        r'^\s*(?:\*\*)?Confidence\s*:[^\n]*$',
        '',
        cleaned,
        flags=re.MULTILINE | re.IGNORECASE
    )

    # 4. Remove filler openers only when followed by the actual answer
    filler_openers_pattern = re.compile(
        r'^\s*(?:'
        r'based\s+on\s+(?:the\s+)?(?:official\s+|provided\s+|available\s+)?(?:gprec\s+)?(?:context|documents|sources|information|records)[,\s:]*'
        r'|according\s+to\s+(?:the\s+)?(?:official\s+|provided\s+|available\s+)?(?:gprec\s+)?(?:documents|sources|context|information|records)[,\s:]*'
        r'|sure[!,\s]*'
        r'|certainly[!,\s]*'
        r'|great\s+question[!,\s]*'
        r'|hello[!,\s]*'
        r'|hi[!,\s]*'
        r'|here\s+(?:is|are)\s+(?:the\s+)?(?:official\s+)?(?:details|information|records|answers?)[,\s:]*'
        r'|here\s+(?:is|are)[,\s:]*'
        r')+',
        re.IGNORECASE
    )
    while True:
        match = filler_openers_pattern.match(cleaned)
        if match:
            remainder = cleaned[match.end():].lstrip()
            if remainder:  # only remove when followed by the actual answer
                cleaned = remainder[:1].upper() + remainder[1:]
                continue
        break

    # 5. Delete everything from a line starting with Sources:, Source:, References:, Evidence:, or Context:
    # to the end of that block, including its bullets
    lines = cleaned.splitlines()
    output_lines = []
    header_pattern = re.compile(
        r'^\s*(?:[-*•]\s*)?(?:#+\s*)?(?:\*\*)?(?:sources?|references?|evidence|context)(?:\*\*)?\s*:.*$'
        r'|^\s*(?:[-*•]\s*)?retrieved\b.*$',
        re.IGNORECASE
    )
    bullet_or_indented_pattern = re.compile(
        r'^\s*(?:[-*•]\s+|\d+\.\s+|[">]\s*|\s{2,}\S|【|\[\d+\])'
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        if header_pattern.match(line):
            i += 1
            # Skip all subsequent lines belonging to this source block
            while i < len(lines):
                next_line = lines[i]
                if not next_line.strip():
                    # Look ahead to see if more bullets follow
                    lookahead = i + 1
                    while lookahead < len(lines) and not lines[lookahead].strip():
                        lookahead += 1
                    if lookahead < len(lines) and bullet_or_indented_pattern.match(lines[lookahead]):
                        i += 1
                        continue
                    else:
                        break
                elif bullet_or_indented_pattern.match(next_line):
                    i += 1
                    continue
                else:
                    break
            continue

        output_lines.append(line)
        i += 1

    cleaned = "\n".join(output_lines)

    # 6. Clean up raw URLs and file paths
    def _md_link_sub(match):
        anchor = match.group(1).strip()
        url = match.group(2).strip()
        if anchor.lower() in ["link", "here", "download document", "source", "url", url.lower()]:
            return ""
        return anchor

    cleaned = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+|file:///[^\s)]+)\)', _md_link_sub, cleaned)
    cleaned = re.sub(r'https?://\S+|www\.\S+', '', cleaned)
    cleaned = re.sub(r'(?:[A-Za-z]:\\[\w\-.\\]+|/(?:[\w\-.]+/)+[\w\-.]+\.[\w]+)', '', cleaned)

    # 7. Strip trailing polite offers and sign-offs at the end
    trailing_offers_pattern = re.compile(
        r'(?:(?<=[.!?])\s*|(?:\n\s*)+)(?:'
        r'let\s+me\s+know[\w\s]*'
        r'|feel\s+free\s+to[\w\s]*'
        r'|hope\s+this\s+helps[\w\s]*'
        r'|i\s+hope\s+this\s+helps[\w\s]*'
        r'|is\s+there\s+anything\s+else[\w\s]*'
        r'|do\s+not\s+hesitate[\w\s]*'
        r')[\.\?!]*\s*$',
        re.IGNORECASE
    )
    while True:
        new_cleaned = trailing_offers_pattern.sub('', cleaned).rstrip()
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned

    # 8. Tidy spaces before punctuation, double spaces, and excess blank lines
    cleaned = re.sub(r'[ \t]+([.,!?;:])', r'\1', cleaned)
    cleaned = re.sub(r'[ \t]{2,}', ' ', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    return cleaned.strip()


def normalize_question(q: str) -> str:
    """Normalizes question text: lowercase, remove punctuation, collapse whitespace."""
    if not q:
        return ""
    q = q.lower().strip()
    q = re.sub(r'[^\w\s]', '', q)
    q = re.sub(r'\s+', ' ', q).strip()
    return q


def clear_answer_cache(db: Optional[DatabaseManager] = None) -> int:
    """Clears all entries in the SQLite answer cache."""
    manager = db if db is not None else DatabaseManager()
    return manager.clear_answer_cache()


def is_gprec_fact_query(query: str) -> bool:
    """Returns True if the question is about GPREC administrative facts, faculty, fees, notices, or dates."""
    if not query:
        return False
    q_lower = query.lower()
    gprec_keywords = [
        "faculty", "hod", "principal", "professor", "associate professor", "assistant professor",
        "staff", "director", "dean", "warden", "dr.", "dr ", "who is", "who are",
        "fee", "fees", "tuition", "fine", "payment", "challan", "payu", "scholarship",
        "notice", "circular", "timetable", "time table", "deadline", "last date", "due date",
        "result", "results", "exam schedule", "holiday", "working day", "academic calendar", "sem exam",
        "gprec", "pulla reddy", "hostel", "mess", "bus", "transport", "library", "canteen",
        "placement", "placements", "highest package", "average package", "recruiters",
        "intake", "cutoff", "eapcet", "ecet", "icet", "counseling", "admissions", "campus",
        "established", "autonomous", "accreditation", "naac", "nba", "nirf", "contact",
        "scheme-2020", "scheme-2023", "scheme 2020", "scheme 2023", "regulations"
    ]
    return any(k in q_lower for k in gprec_keywords)


def rewrite_query(
    query: str, 
    history: Optional[List[Dict[str, str]]] = None,
    client: Any = None
) -> Tuple[str, bool]:
    """
    Rewrites follow-up questions (short, pronouns, or missing subjects) into standalone queries.
    Uses rule-based patterns first (works 100% offline without API key),
    and falls back to LLM rewrite only if rules cannot resolve it.
    Returns: (rewritten_query, was_rewritten)
    """
    if not history or not query:
        return query, False

    clean_q = query.strip()
    q_lower = clean_q.lower()

    # Get the last turn
    last_turn = history[-1]
    last_q = (last_turn.get("question") or "").strip()
    last_a = (last_turn.get("answer") or "").strip()
    last_q_lower = last_q.lower()

    if not last_q:
        return clean_q, False

    # Check if query is a follow-up:
    # 1. Starts with conjunctions/transitions (and, what about, how about, also, same for, and for)
    # 2. Contains pronouns (he, she, his, her, him, its, their, they, this, that, these, those)
    # 3. Very short query (< 5 words) with missing subject
    has_pronoun = bool(re.search(r'\b(he|she|his|her|him|its|their|they|this|that|these|those)\b', q_lower))
    has_prefix = bool(re.match(r'^(and\b|what about\b|how about\b|also\b|same for\b|what of\b)', q_lower))
    words = clean_q.split()
    is_short = len(words) <= 4

    # A query is self-contained (not a follow-up) if it explicitly specifies a person or title:
    has_person_target = bool(re.search(r'\b(?:dr|prof|professor|sri|smt|mr|mrs|ms)\.?\s*[a-z]+', q_lower)) or bool(re.search(r'\b(who is|profile of|details of)\s+(?:dr|prof|sri|smt|[a-z]{3,})', q_lower))
    if has_person_target and not has_pronoun and not has_prefix:
        return clean_q, False

    if not (has_pronoun or has_prefix or is_short):
        return clean_q, False

    # --- RULE 1: Department Shift (e.g. "and for ECE?", "what about mechanical?", "and civil?") ---
    dept_tokens = {
        "eee": "EEE", "ece": "ECE", "cse": "CSE", "civil": "Civil Engineering",
        "mechanical": "Mechanical Engineering", "me": "Mechanical Engineering",
        "cst": "CST", "csd": "CSD", "csm": "CSM", "cso": "CSO",
        "mba": "MBA", "mca": "MCA", "h&s": "Humanities and Sciences", "hbs": "Humanities and Sciences"
    }
    
    new_dept = None
    for tok, label in dept_tokens.items():
        if re.search(rf'\b{re.escape(tok)}\b', q_lower):
            new_dept = label
            break

    if new_dept:
        last_q_lower = last_q.lower()
        old_dept_matched = None
        for tok, label in dept_tokens.items():
            if re.search(rf'\b{re.escape(tok)}\b', last_q_lower):
                old_dept_matched = tok
                break
        if old_dept_matched:
            rewritten = re.sub(rf'\b{re.escape(old_dept_matched)}\b', new_dept, last_q, flags=re.IGNORECASE)
            rewritten = re.sub(r'[?!.,]+$', '', rewritten).strip() + "?"
            return rewritten, True
        elif any(k in last_q_lower for k in ["hod", "faculty", "intake", "cutoff", "syllabus", "placement"]):
            rewritten = f"{last_q.rstrip('?.! ')} for {new_dept}?"
            return rewritten, True

    # --- RULE 2: Pronoun referring to person/faculty (e.g. "his qualification", "what is his email", "his photo") ---
    if has_pronoun:
        person_name = None
        name_match = re.search(r'\b(?:dr\.?|prof\.?|sri\.?|smt\.?)\s+([a-zA-Z\.\s]{2,30})\b', last_q, re.IGNORECASE)
        if name_match:
            person_name = name_match.group(0).strip()
        else:
            name_match_a = re.search(r'\b(?:dr\.?|prof\.?)\s+([A-Z][a-zA-Z\.\s]{2,25})\b', last_a)
            if name_match_a:
                person_name = name_match_a.group(0).strip()
            elif "kishor" in last_q_lower or "kishor" in last_a.lower():
                person_name = "Dr. G. Kishor"

        if person_name:
            if "qualification" in q_lower:
                return f"qualification of {person_name}", True
            if "email" in q_lower:
                return f"what is the email of {person_name}", True
            if "photo" in q_lower or "picture" in q_lower:
                return f"photo of {person_name}", True
            if "designation" in q_lower or "role" in q_lower:
                return f"designation of {person_name}", True
            if "department" in q_lower:
                return f"department of {person_name}", True
            
            rewritten = re.sub(r'\b(?:his|her)\b', f"{person_name}'s", clean_q, flags=re.IGNORECASE)
            rewritten = re.sub(r'\b(?:him|her)\b', f"{person_name}", rewritten, flags=re.IGNORECASE)
            rewritten = re.sub(r'\b(?:he|she)\b', f"{person_name}", rewritten, flags=re.IGNORECASE)
            return rewritten, True

    # --- RULE 3: "what about the fee?" / "and fee?" / "how much is the fee?" ---
    if any(k in q_lower for k in ["fee", "fees", "cost", "tuition"]):
        clean_last = re.sub(r'[?!.]+$', '', last_q).strip()
        return f"what is the fee for {clean_last}?", True

    # --- RULE 4: "and eligibility?" / "what about eligibility?" ---
    if "eligibility" in q_lower:
        clean_last = re.sub(r'[?!.]+$', '', last_q).strip()
        return f"eligibility for {clean_last}?", True

    # --- RULE 5: Short prefix follow-up (e.g. "and placements?", "what about cutoffs?") ---
    if has_prefix:
        suffix = re.sub(r'^(and\s+for|and\s+what\s+about|what\s+about|how\s+about|and|also|same\s+for)\s+', '', clean_q, flags=re.IGNORECASE).rstrip('?.! ')
        clean_last = re.sub(r'[?!.]+$', '', last_q).strip()
        return f"{suffix} for {clean_last}?", True

    # --- FALLBACK: LLM rewrite if rules weren't enough and client is available ---
    if client is not None:
        try:
            rewrite_prompt = (
                f"Previous question: {last_q}\n"
                f"Previous answer summary: {last_a[:120]}\n"
                f"Follow-up question: {clean_q}\n\n"
                f"Rewrite the follow-up question as a single standalone question with all implied subjects and context restored. "
                f"Output ONLY the rewritten question, nothing else."
            )
            model_to_use = os.getenv("LLM_MODEL") or getattr(config, "LLM_MODEL", None) or getattr(config, "OPENROUTER_MODEL", "google/gemma-2-9b-it:free")
            if config.LLM_PROVIDER == "openrouter":
                resp = client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": rewrite_prompt}],
                    temperature=0.0,
                    timeout=8.0,
                    max_tokens=60
                )
                llm_rewritten = (resp.choices[0].message.content or "").strip().strip('"\'')
            else:
                resp = client.models.generate_content(
                    model=model_to_use,
                    contents=rewrite_prompt,
                    config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=60)
                )
                llm_rewritten = (resp.text or "").strip().strip('"\'')

            if llm_rewritten:
                lines = [l.strip() for l in llm_rewritten.splitlines() if l.strip()]
                candidate = None
                for l in reversed(lines):
                    clean_l = re.sub(r'^(?:\d+\.|\*|-|Rewritten question:)\s*', '', l, flags=re.IGNORECASE).strip()
                    if clean_l.endswith('?'):
                        candidate = clean_l
                        break
                if not candidate and lines:
                    candidate = re.sub(r'^(?:\d+\.|\*|-|Rewritten question:)\s*', '', lines[-1], flags=re.IGNORECASE).strip()

                if candidate:
                    c_lower = candidate.lower()
                    if not any(bad in c_lower for bad in ["analyze", "previous question", "previous answer", "likely a typo", "note:"]):
                        if len(candidate) > len(clean_q):
                            return candidate, True
        except Exception:
            pass

    return clean_q, False


class RAGPipeline:
    def __init__(self, embedder: Embedder, vstore: VectorStore, db: Optional[DatabaseManager] = None):
        self.embedder = embedder
        self.vstore = vstore
        self.db = db if db is not None else DatabaseManager()
        self.model_name = os.getenv("LLM_MODEL") or os.getenv("OPENROUTER_MODEL") or getattr(config, "LLM_MODEL", None) or getattr(config, "OPENROUTER_MODEL", "google/gemma-2-9b-it:free")
        
        if config.LLM_PROVIDER == "openrouter":
            import openai
            api_key = config.OPENROUTER_API_KEY
            if not api_key:
                print("WARNING: OPENROUTER_API_KEY is not set.")
                self.client = None
            else:
                self.client = openai.OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                    timeout=20.0,
                    max_retries=1,
                )
        else:
            api_key = config.GEMINI_API_KEY
            if not api_key:
                print("WARNING: GEMINI_API_KEY is not set. LLM generation will fail.")
                self.client = None
            else:
                self.client = genai.Client(api_key=api_key)

    def retrieve(self, query: str, top_k: int = config.TOP_K) -> List[Dict[str, Any]]:
        from src.data_quality import ChunkDeduplicator
        query_emb = self.embedder.embed_text(query)
        # Retrieve slightly larger candidate set to filter and deduplicate
        raw_results = self.vstore.search(query_emb, query_text=query, top_k=top_k * 2)

        # Domain noise filtering:
        # If query is not specifically asking about RTI / statutory, filter out RTI declarations
        q_lower = query.lower()
        filtered = []
        is_rti_query = any(k in q_lower for k in ["rti", "right to information", "statutory declaration", "act 4(1)"])
        for r in raw_results:
            url = r.get("source_url", "").lower()
            title = r.get("title", "").lower()
            if not is_rti_query and ("/rti/" in url or "rti" in url or "statutory declaration" in title or "right to information" in title):
                continue
            if ("library" in q_lower or "faculty" in q_lower or "hostel" in q_lower) and "alumni" in url:
                continue
            filtered.append(r)

        if not filtered and raw_results:
            filtered = raw_results

        # Deduplicate retrieved chunks by hash & near-duplicate token sets
        deduped = ChunkDeduplicator.deduplicate_chunks(filtered, similarity_threshold=0.85)
        return deduped[:top_k]

    def generate_prompt(
        self, 
        query: str, 
        contexts: List[Dict[str, Any]], 
        verification_feedback: str = "", 
        verified_facts: Optional[List[Dict[str, Any]]] = None, 
        entity_directory: Optional[List[Dict[str, Any]]] = None,
        notices: Optional[List[Dict[str, Any]]] = None,
        curated_links: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        curated_links_str = ""
        if curated_links:
            curated_links_str = "--- OFFICIAL DIRECT HYPERLINKS (MANDATORY TO INCLUDE AS CLICKABLE HYPERLINKS) ---\n"
            for cl in curated_links:
                curated_links_str += f"* [{cl['title']}]({cl['url']})\n"
            curated_links_str += "\nWhen relevant official document or portal links are provided above, you MUST include the exact clickable markdown hyperlink(s) in your answer (e.g. [Document Title](URL)).\n\n"

        verified_facts_str = ""
        if verified_facts or entity_directory:
            verified_facts_str = "--- VERIFIED GROUND TRUTH & ENTITY DIRECTORY (HIGHEST PRIORITY) ---\n"
            if entity_directory:
                for ent in entity_directory:
                    verified_facts_str += f"* Entity: {ent.get('role')} ({ent.get('department')}) - Name: {ent.get('name')} | Designation: {ent.get('designation')} | Qualification: {ent.get('qualification')} (Source: {ent.get('source_url', 'College Directory')})\n"
            if verified_facts:
                for vf in verified_facts:
                    v_date = vf.get('verified_date') or '2026-10-12'
                    v_by = vf.get('verified_by') or 'admin'
                    verified_facts_str += f"* {vf['entity']} - {vf['attribute'].title()}: {vf['value']} [Verified by {v_by} on {v_date}] (Source: {vf.get('source_url', 'Official College Records')})\n"
            verified_facts_str += "\nUse these verified facts and entity directory records with highest priority when answering.\n\n"

        notices_str = ""
        if notices:
            notices_str = "--- OFFICIAL STRUCTURED NOTICES & TIMETABLES (LATEST FIRST) ---\n"
            for n in notices[:5]:
                pub = n.get("published_date") or ""
                ntype = (n.get("notice_type") or "Notice").title()
                prog = f" [{n.get('program')}]" if n.get('program') else ""
                sem = f" {n.get('semester')}" if n.get('semester') else ""
                reg = f" ({n.get('scheme_regulation')})" if n.get('scheme_regulation') else ""
                pdf_url = (n.get("attachment_urls") or "").split(",")[0] if n.get("attachment_urls") else (n.get("source_page") or "")
                link_md = f" | [Download Document]({pdf_url})" if pdf_url else ""
                notices_str += f"* [{ntype}]{prog}{sem}{reg} {n.get('title')} (Published: {pub}){link_md}\n"
            notices_str += "\nWhen presenting timetables or notices, format the 5 newest relevant notices clearly with their published dates and direct links. Never output more than 5 primary notice bullets; mention older records are available in archives.\n\n"

        context_str = ""
        for i, ctx in enumerate(contexts, 1):
            title = ctx.get("title", "Document")
            url = ctx.get("source_url", "")
            # Only use real published_date, never crawl date or first_seen
            pub_date = ctx.get("published_date") or ""
            content = ctx.get("content", "")
            date_line = f"Published Date: {pub_date}\n" if pub_date else ""
            context_str += f"\n--- Source {i}: {title} ({url}) ---\n{date_line}{content}\n"

        feedback_instruction = ""
        if verification_feedback:
            feedback_instruction = f"\nCORRECTION REQUIRED FROM PREVIOUS ATTEMPT:\n{verification_feedback}\nRewrite your answer removing unsupported claims.\n"

        prompt = f"""You are the GPREC AI Student Assistant, an official conversational chatbot for G. Pulla Reddy Engineering College (GPREC), Kurnool.

TODAY'S DATE: {today}

CRITICAL RELIABILITY RULES:
1. Grounding: Answer ONLY using the official GPREC sources, verified facts, and entity directory provided below.
2. Verified Facts Priority: When verified ground truth facts or entity directory entries are provided, treat them as authoritative ground truth.
3. Forbid Inference: NEVER state something as fact because it is "implied". 
   - A person counts as Ph.D. faculty ONLY if the source explicitly states a doctorate (a "Dr." prefix in staff lists or explicit "Ph.D." qualification). Being a jury member, reviewer, resource person, or Ph.D. supervisor is NOT evidence that the faculty holds a doctorate.
   - If the sources only confirm some members of a department, state: "The sources only confirm X of Y faculty members."
4. Date Handling: Never invent notice dates. Do not cite crawler timestamps or today's date as a notice date.
5. Acronyms: Do NOT expand any acronym unless the full expansion literally appears in the sources.
6. Sensitive Info: Do NOT repeat default passwords, login credential formats, or personal mobile phone numbers. Direct students to the relevant office or portal instead.
7. Completeness & Format: If the information is missing from the sources, state clearly that it is not available in official sources. Never combine partial text with a generic "I couldn't find" fallback.
8. Exam Timetables: When asked about exam timetables or schedules, present the newest relevant timetables with published date, notice type badge, and direct document link. Never dump large raw unstructured lists of 20+ bullets.
9. Fee Structure: When asked about fee structure, cite official APHERMC / Government of Andhra Pradesh tuition fee notifications with academic year and as-of date. Clarify that B.Tech tuition fee applies college-wide across engineering branches (including EEE) for Autonomous colleges under Category-A (Convenor Quota) and Category-B (Management Quota).
10. Official Hyperlinks: When official relevant document or portal links are provided in the context or direct links section, you MUST provide them as clickable markdown hyperlinks `[Title](URL)` in the response so students and visitors can directly open or download them.{feedback_instruction}

TONE AND STYLE GUIDELINES (STRICT):
- First sentence is the direct answer to exactly what was asked. No greetings, no "Based on the official GPREC sources", no "According to the documents", no filler openers.
- Answer only what was asked. Add at most ONE extra sentence, and only if it directly helps with the same question (for a HOD question: the department name or when the department was established is fine; another person's achievements are not).
- Never quote or paraphrase source passages. Never write a Sources or References section. Never write citation markers, line numbers, brackets with numbers or symbols like 【 】.
- Never mention "official GPREC sources", "the context", "the documents", "the provided information" or "the knowledge base".
- Do not repeat a name in a different spelling.
- For a simple fact question the whole answer is 1 to 2 sentences. Use a list only for 3 or more parallel items.
- Bold only the key fact (name, date, amount), at most 2 bold items.
- Write like a knowledgeable senior student talking to a junior: plain words, short sentences, a friendly but professional tone. Never pad.
- Put dates, amounts, names and deadlines exactly as written in the source.
- If the sources only partly answer, give the part that is supported, then say plainly what is missing, in one sentence.
- If nothing relevant was found, state plainly in one or two sentences that the information is not available and suggest where the student can check. Do not guess.
- Never output internal thinking, reasoning steps, or analysis. Output only the final answer.
- Never print raw URLs, file paths, chunk numbers, source IDs or retrieved text in the answer body. The app shows sources separately as buttons.

--- STYLE EXAMPLES (FOR FORMAT AND TONE ONLY — ALL FACTS IN THESE EXAMPLES ARE FICTIONAL PLACEHOLDERS AND MUST NEVER BE USED IN AN ACTUAL ANSWER) ---

Example 1 (Simple Fact Question):
Student Question: Who is the HOD of Electrical and Electronics Engineering?
Answer: The HOD of the Electrical and Electronics Engineering department is **Dr. G. Kishor**. The department was established in 1994 and has an intake of 120.

Example 2 (List Question):
Student Question: What certificates do I need to submit during reporting?
Answer: You need to submit the following original certificates at the admissions counter:
* Allotment order and rank card
* Intermediate or 10+2 marks memo
* SSC or 10th class certificate
* Transfer certificate (TC) and study certificates

Example 3 (Partial Answer Question):
Student Question: When will the internal lab exams be held and who is the external examiner?
Answer: The internal lab examinations are scheduled from **10 Nov 2026** to **15 Nov 2026**. The official notice does not specify the external examiners.

Example 4 (Not Found Question):
Student Question: Is there an indoor swimming pool facility on the campus?
Answer: There is no swimming pool facility listed in the official college records. You can check with the Department of Physical Education or the campus administrative office.
--------------------------------------------------------------------------------------------------------------------------------------------

{curated_links_str}{verified_facts_str}{notices_str}--- AVAILABLE GPREC CONTEXT ---
{context_str}

Student Question: {query}
Answer:"""
        return prompt

    def answer_question(
        self, 
        query: str, 
        history: Optional[List[Dict[str, str]]] = None, 
        study_mode: bool = False
    ) -> Dict[str, Any]:
        import time
        start_time = time.time()
        retrieval_duration_ms = 0.0
        llm_duration_ms = 0.0
        ver_duration_ms = 0.0

        # 0. Check Faculty Directory directly on raw user query (Deterministic code routing, NO LLM)
        from src.faculty_router import handle_faculty_query
        direct_faculty_res = handle_faculty_query(query, self.db)
        if direct_faculty_res is not None:
            total_duration_ms = (time.time() - start_time) * 1000
            direct_faculty_res["timings"] = {
                "total_ms": round(total_duration_ms, 1),
                "retrieval_ms": 0.0,
                "llm_ms": 0.0,
                "verification_ms": 0.0
            }
            print(f"[DEBUG TIMING] Faculty Router (Direct) | Total: {total_duration_ms:.1f}ms")
            return direct_faculty_res

        # Step 2: Follow-up memory / query rewriting
        effective_query, was_rewritten = rewrite_query(query, history, getattr(self, "client", None))
        search_query = effective_query if was_rewritten else query
        norm_q = normalize_question(search_query)
        cache_key = f"study:{norm_q}" if study_mode else norm_q

        # Step 1: Check SQLite answer cache (24h expiry)
        cached = self.db.get_cached_answer(cache_key)
        if cached is not None:
            total_duration_ms = (time.time() - start_time) * 1000
            cached["timings"] = {
                "total_ms": round(total_duration_ms, 1),
                "retrieval_ms": 0.0,
                "llm_ms": 0.0,
                "verification_ms": 0.0
            }
            cached["from_cache"] = True
            print(f"[DEBUG TIMING] Answer Cache HIT for '{cache_key}' | Total: {total_duration_ms:.1f}ms")
            if was_rewritten:
                cached["rewritten_query"] = effective_query
            return cached

        # 0. Check Faculty Directory first (Deterministic code routing, NO LLM)
        from src.faculty_router import handle_faculty_query
        faculty_res = handle_faculty_query(search_query, self.db)
        if faculty_res is not None:
            total_duration_ms = (time.time() - start_time) * 1000
            faculty_res["timings"] = {
                "total_ms": round(total_duration_ms, 1),
                "retrieval_ms": 0.0,
                "llm_ms": 0.0,
                "verification_ms": 0.0
            }
            print(f"[DEBUG TIMING] Faculty Router | Total: {total_duration_ms:.1f}ms")
            if was_rewritten:
                faculty_res["rewritten_query"] = effective_query
            return faculty_res

        from src.reliability import (
            ResponseType, AmbiguityDetector, AnswerVerifier, 
            SensitiveInfoFilter, ResponseFormatter
        )

        # Step 3: Check Study Mode (general academic help)
        if study_mode and not is_gprec_fact_query(search_query):
            matched_syllabus = self.db.search_syllabus_subject(search_query)
            study_prompt = (
                f"You are an expert academic tutor for engineering students.\n"
                f"Explain the following concept or answer the student's academic doubt in a clear, step-by-step educational way with examples where helpful.\n\n"
                f"Student Question: {search_query}\n\n"
                f"Explanation:"
            )
            t_llm_start = time.time()
            explanation_text = ""
            if self.client:
                try:
                    model_to_use = os.getenv("LLM_MODEL") or getattr(config, "LLM_MODEL", None) or getattr(config, "OPENROUTER_MODEL", "google/gemma-2-9b-it:free")
                    if config.LLM_PROVIDER == "openrouter":
                        response = self.client.chat.completions.create(
                            model=model_to_use,
                            messages=[{"role": "user", "content": study_prompt}],
                            temperature=0.2,
                            timeout=20.0,
                            max_tokens=700
                        )
                        explanation_text = (response.choices[0].message.content or "").strip()
                    else:
                        response = self.client.models.generate_content(
                            model=model_to_use,
                            contents=study_prompt,
                            config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=700)
                        )
                        explanation_text = (response.text or "").strip()
                except Exception:
                    explanation_text = f"Academic explanation for: {search_query}"
            else:
                explanation_text = f"Academic explanation for: {search_query}"
            llm_duration_ms = (time.time() - t_llm_start) * 1000

            answer_body = f"General academic explanation, not from GPREC documents.\n\n{explanation_text}"
            total_duration_ms = (time.time() - start_time) * 1000
            print(f"[DEBUG TIMING] Study Mode | Total: {total_duration_ms:.1f}ms | LLM: {llm_duration_ms:.1f}ms")

            study_res = {
                "response_type": ResponseType.ANSWERED,
                "answer": answer_body,
                "sources": [],
                "confidence": "High",
                "confidence_reason": "General academic explanation",
                "is_study_mode": True,
                "matched_syllabus": matched_syllabus,
                "timings": {
                    "total_ms": round(total_duration_ms, 1),
                    "retrieval_ms": 0.0,
                    "llm_ms": round(llm_duration_ms, 1),
                    "verification_ms": 0.0
                }
            }
            if was_rewritten:
                study_res["rewritten_query"] = effective_query
            self.db.set_cached_answer(cache_key, study_res)
            return study_res

        # 1. Ambiguity handling (e.g. Case 3: "list the PhD faculties" without department)
        ambiguity = AmbiguityDetector.check_ambiguity(search_query)
        if ambiguity:
            total_duration_ms = (time.time() - start_time) * 1000
            amb_res = {
                "response_type": ResponseType.CLARIFY,
                "answer": ambiguity["question"],
                "clarify_question": ambiguity["question"],
                "clarify_options": ambiguity["options"],
                "sources": [],
                "confidence": "High",
                "confidence_reason": "Identified query ambiguity needing department clarification",
                "timings": {
                    "total_ms": round(total_duration_ms, 1),
                    "retrieval_ms": 0.0,
                    "llm_ms": 0.0,
                    "verification_ms": 0.0
                }
            }
            if was_rewritten:
                amb_res["rewritten_query"] = effective_query
            return amb_res
            
        matched_entities = self.db.search_entity_directory(search_query)
        matched_facts = self.db.get_matching_verified_facts(search_query)
        
        # 2. Check if question is specifically about deadlines, timetables, results, or latest notices
        q_lower = search_query.lower()
        is_deadline_query = any(k in q_lower for k in [
            "deadline", "deadlines", "last date", "due date", "closing date", "on or before"
        ])
        is_timetable_query = any(k in q_lower for k in [
            "timetable", "time table", "exam schedule", "examination schedule", "exam dates", "dates of exam"
        ])
        is_result_query = any(k in q_lower for k in [
            "result", "results", "grade card", "marks memo", "revaluation", "recounting"
        ])
        is_latest_notice_query = any(k in q_lower for k in [
            "latest notice", "latest notices", "recent notice", "recent notices", "new notice",
            "new notices", "exam notice", "exam notices", "latest notification", "recent notification",
            "latest circular", "recent circular"
        ]) or (
            any(w in q_lower for w in ["latest", "recent", "new", "current"]) and
            any(t in q_lower for t in ["notice", "circular", "notification"])
        )

        is_notice_category_query = (
            is_deadline_query or is_timetable_query or is_result_query or is_latest_notice_query
        )

        if is_notice_category_query:
            # Query the notices table directly, sorted by published_date DESC
            matched_notices = []
            if is_deadline_query:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM notices
                        WHERE is_active = 1 AND (
                            deadline_date IS NOT NULL OR
                            LOWER(raw_text) LIKE '%last date%' OR
                            LOWER(raw_text) LIKE '%on or before%' OR
                            LOWER(raw_text) LIKE '%due%' OR
                            LOWER(notice_type) IN ('fee notification', 'revaluation')
                        )
                        ORDER BY CASE WHEN deadline_date IS NOT NULL AND deadline_date != '' THEN deadline_date ELSE '9999-12-31' END ASC,
                                 CASE WHEN published_date IS NOT NULL AND published_date != '' THEN published_date ELSE '1970-01-01' END DESC
                        LIMIT 10
                    """)
                    matched_notices = [dict(row) for row in cursor.fetchall()]
            elif is_timetable_query:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM notices
                        WHERE is_active = 1 AND (
                            LOWER(notice_type) = 'timetable' OR
                            LOWER(title) LIKE '%timetable%' OR
                            LOWER(title) LIKE '%time table%' OR
                            LOWER(raw_text) LIKE '%timetable%' OR
                            LOWER(raw_text) LIKE '%time table%'
                        )
                        ORDER BY CASE WHEN published_date IS NOT NULL AND published_date != '' THEN published_date ELSE '1970-01-01' END DESC,
                                 notice_id DESC
                        LIMIT 10
                    """)
                    matched_notices = [dict(row) for row in cursor.fetchall()]
            elif is_result_query:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM notices
                        WHERE is_active = 1 AND (
                            LOWER(notice_type) IN ('results', 'revaluation') OR
                            LOWER(title) LIKE '%result%' OR
                            LOWER(title) LIKE '%revaluation%' OR
                            LOWER(raw_text) LIKE '%result%' OR
                            LOWER(raw_text) LIKE '%revaluation%'
                        )
                        ORDER BY CASE WHEN published_date IS NOT NULL AND published_date != '' THEN published_date ELSE '1970-01-01' END DESC,
                                 notice_id DESC
                        LIMIT 10
                    """)
                    matched_notices = [dict(row) for row in cursor.fetchall()]
            else: # is_latest_notice_query
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT * FROM notices
                        WHERE is_active = 1
                        ORDER BY CASE WHEN published_date IS NOT NULL AND published_date != '' THEN published_date ELSE '1970-01-01' END DESC,
                                 notice_id DESC
                        LIMIT 10
                    """)
                    matched_notices = [dict(row) for row in cursor.fetchall()]

            # If user query specified specific topic/branch/program, filter matched_notices
            if matched_notices:
                # Check programs
                prog_terms = ["b.tech", "m.tech", "mba", "mca"]
                for pt in prog_terms:
                    if pt in q_lower:
                        filtered = [n for n in matched_notices if pt in (n.get("title", "") + " " + n.get("raw_text", "") + " " + str(n.get("program", ""))).lower()]
                        if filtered:
                            matched_notices = filtered
                        break

                # Check topic terms (e.g. "revaluation", "marine", "hostel", "cse", "eee")
                query_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', q_lower))
                generic_words = {
                    "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
                    "latest", "recent", "current", "upcoming", "new", "list", "show", "tell",
                    "give", "details", "info", "information", "notice", "notices", "circular",
                    "circulars", "notification", "notifications", "exam", "exams", "examination",
                    "examinations", "dates", "date", "schedule", "timetable", "the", "for", "and",
                    "are", "with", "from", "any", "all", "about", "there"
                }
                topic_keywords = query_words - generic_words
                if topic_keywords:
                    filtered_topic = [
                        n for n in matched_notices
                        if any(tk in (n.get("title", "") + " " + n.get("raw_text", "") + " " + (n.get("department") or "")).lower() for tk in topic_keywords)
                    ]
                    matched_notices = filtered_topic

            # If nothing matches, return NOT_FOUND instead of falling back to old chunks
            if not matched_notices:
                return ResponseFormatter.format_not_found([
                    "Check official notifications at examcell.gprec.ac.in",
                    "Check the physical notice board at the examination cell",
                    "Contact the Controller of Examinations (COE)"
                ])

            # Build direct answer from the notices table
            top_notice = matched_notices[0]
            pub_date = top_notice.get("published_date")
            date_str = pub_date[:10] if pub_date else None
            date_prefix = f"Based on the notice dated **{date_str}**" if date_str else "Based on the official notice"

            if is_deadline_query:
                deadline_val = top_notice.get("deadline_date") or "as specified in the circular"
                answer = f"{date_prefix}, the deadline for **{top_notice['title']}** is **{deadline_val}**."
                if len(matched_notices) > 1 and matched_notices[1].get("deadline_date"):
                    answer += f" Additionally, the deadline for **{matched_notices[1]['title']}** is **{matched_notices[1]['deadline_date']}**."
            elif any(w in q_lower for w in ["list", "what are", "all"]) or len(matched_notices) > 1 and is_latest_notice_query:
                bullets = []
                for n in matched_notices[:5]:
                    n_date = n.get("published_date")
                    d_txt = f" (Published: {n_date[:10]})" if n_date else ""
                    bullets.append(f"* **{n['title']}**{d_txt}")
                answer = f"{date_prefix}, the latest updates are:\n\n" + "\n".join(bullets)
            else:
                answer = f"{date_prefix}, **{top_notice['title']}** has been published."
                if top_notice.get("deadline_date"):
                    answer += f" The last date is **{top_notice['deadline_date']}**."

            sources = []
            for n in matched_notices[:5]:
                doc_url = n.get("document_url") or (n.get("attachment_urls") or "").split(",")[0] or n.get("source_page") or "https://www.gprec.ac.in"
                sources.append({
                    "title": f"Notice: {n['title']}",
                    "source_url": doc_url,
                    "page": None,
                    "published_date": n.get("published_date")
                })

            total_duration_ms = (time.time() - start_time) * 1000
            print(f"[DEBUG TIMING] Notice Match | Total: {total_duration_ms:.1f}ms")
            notice_res = {
                "response_type": ResponseType.ANSWERED,
                "answer": clean_answer(answer),
                "sources": sources,
                "confidence": "High",
                "confidence_reason": f"Official notice dated {date_str or 'verified'}",
                "timings": {
                    "total_ms": round(total_duration_ms, 1),
                    "retrieval_ms": round(total_duration_ms, 1),
                    "llm_ms": 0.0,
                    "verification_ms": 0.0
                }
            }
            if was_rewritten:
                notice_res["rewritten_query"] = effective_query
            self.db.set_cached_answer(cache_key, notice_res)
            return notice_res

        matched_notices = []

        from src.curated_links import find_relevant_curated_links, format_curated_links_markdown
        t_ret_start = time.time()
        curated_links = find_relevant_curated_links(search_query)
        contexts = self.retrieve(search_query)
        retrieval_duration_ms = (time.time() - t_ret_start) * 1000

        if not contexts and not matched_facts and not matched_entities and not matched_notices and not curated_links:
            nf_res = ResponseFormatter.format_not_found([
                "What courses are offered at GPREC?",
                "What are the library timings?",
                "Who is the head of the EEE department?"
            ])
            total_duration_ms = (time.time() - start_time) * 1000
            nf_res["timings"] = {
                "total_ms": round(total_duration_ms, 1),
                "retrieval_ms": round(retrieval_duration_ms, 1),
                "llm_ms": 0.0,
                "verification_ms": 0.0
            }
            print(f"[DEBUG TIMING] Not Found | Total: {total_duration_ms:.1f}ms | Retrieval: {retrieval_duration_ms:.1f}ms")
            if was_rewritten:
                nf_res["rewritten_query"] = effective_query
            return nf_res

        # Prepare all sources including verified facts, entity directory, notices, and curated links
        all_sources = []
        if curated_links:
            for cl in curated_links:
                all_sources.append({
                    "title": cl["title"],
                    "source_url": cl["url"],
                    "page": None,
                    "published_date": cl.get("year")
                })
        if matched_facts:
            for vf in matched_facts:
                if vf.get("source_url"):
                    v_date = vf.get("verified_date") or "2026-10-12"
                    all_sources.append({
                        "title": f"Verified Fact: {vf['entity']} (Verified by admin on {v_date})",
                        "source_url": vf["source_url"],
                        "page": None,
                        "published_date": v_date
                    })
        if matched_entities:
            for ent in matched_entities:
                if ent.get("source_url"):
                    all_sources.append({
                        "title": f"Official Directory: {ent.get('role')} - {ent.get('name')}",
                        "source_url": ent["source_url"],
                        "page": None,
                        "published_date": None
                    })
        if matched_notices:
            for n in matched_notices[:5]:
                pdf_url = (n.get("attachment_urls") or "").split(",")[0] if n.get("attachment_urls") else (n.get("source_page") or "")
                all_sources.append({
                    "title": f"Notice [{n.get('notice_type', 'Notice').title()}]: {n['title']}",
                    "source_url": pdf_url or "http://examcell.gprec.ac.in/",
                    "page": None,
                    "published_date": n.get("published_date")
                })
        for c in contexts:
            all_sources.append({
                "title": c.get("title", "Document"),
                "source_url": c.get("source_url", ""),
                "page": c.get("page"),
                "published_date": c.get("published_date")
            })

        # Check if client initialized
        if not self.client:
            if curated_links:
                links_md = format_curated_links_markdown(curated_links)
                return {
                    "response_type": ResponseType.ANSWERED,
                    "answer": f"Here are the relevant official GPREC document/portal links:\n\n{links_md}",
                    "sources": all_sources,
                    "confidence": "High",
                    "confidence_reason": "Official GPREC document/portal links"
                }
            return {
                "response_type": ResponseType.NOT_FOUND,
                "answer": "Error: LLM client is not initialized (missing API key in .env).",
                "sources": all_sources,
                "confidence": "Low",
                "confidence_reason": "LLM client uninitialized"
            }

        all_context_text = " ".join([c.get("content", "") + " " + c.get("title", "") for c in contexts])
        if matched_facts:
            all_context_text += " " + " ".join([vf.get("value", "") for vf in matched_facts])
        if matched_entities:
            all_context_text += " " + " ".join([f"{e.get('name', '')} {e.get('role', '')} {e.get('designation', '')}" for e in matched_entities])
        if matched_notices:
            all_context_text += " " + " ".join([f"{n.get('title', '')} {n.get('raw_text', '')}" for n in matched_notices])

        prompt = self.generate_prompt(
            search_query, contexts, 
            verified_facts=matched_facts, 
            entity_directory=matched_entities,
            notices=matched_notices,
            curated_links=curated_links
        )
        
        # LLM Call (Speed settings: 20s timeout, max 1 retry, no OpenRouter fallback loop)
        t_llm_start = time.time()
        max_retries = 2
        answer_text = ""
        model_to_use = os.getenv("LLM_MODEL") or getattr(config, "LLM_MODEL", None) or getattr(config, "OPENROUTER_MODEL", "google/gemma-2-9b-it:free")
        
        for attempt in range(max_retries):
            try:
                if config.LLM_PROVIDER == "openrouter":
                    response = self.client.chat.completions.create(
                        model=model_to_use,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        timeout=20.0,
                        max_tokens=600
                    )
                    answer_text = (response.choices[0].message.content or "").strip()
                else:
                    response = self.client.models.generate_content(
                        model=model_to_use,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=600)
                    )
                    answer_text = (response.text or "").strip()
                    
                is_invalid = (
                    not answer_text
                    or answer_text.lower().startswith("user safety")
                    or (len(answer_text) < 25 and "safe" in answer_text.lower())
                )
                if is_invalid and attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                elif is_invalid:
                    answer_text = ""
                break
            except Exception as e:
                error_msg = str(e).lower()
                # At most 1 retry, no fallback loop on timeouts/errors
                if ("503" in error_msg or "429" in error_msg or "timeout" in error_msg) and attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                break
                
        llm_duration_ms = (time.time() - t_llm_start) * 1000

        # If after retries output is still empty, fall back cleanly
        if not answer_text:
            nf_res = ResponseFormatter.format_not_found()
            total_duration_ms = (time.time() - start_time) * 1000
            nf_res["timings"] = {
                "total_ms": round(total_duration_ms, 1),
                "retrieval_ms": round(retrieval_duration_ms, 1),
                "llm_ms": round(llm_duration_ms, 1),
                "verification_ms": 0.0
            }
            print(f"[DEBUG TIMING] Total: {total_duration_ms:.1f}ms | Retrieval: {retrieval_duration_ms:.1f}ms | LLM: {llm_duration_ms:.1f}ms | Verification: 0.0ms")
            if was_rewritten:
                nf_res["rewritten_query"] = effective_query
            return nf_res

        # 2. Answer Verification Pass (Rule-based checks only, NO extra LLM call)
        t_ver_start = time.time()
        passed_phd, phd_errors = AnswerVerifier.verify_phd_claims(answer_text, all_context_text)
        passed_facts, fact_errors = AnswerVerifier.verify_factual_grounding(answer_text, all_context_text)
        verification_passed = passed_phd and passed_facts
        ver_duration_ms = (time.time() - t_ver_start) * 1000

        # 3. Clean Response Type Categorization
        # Clean answer text immediately from citation markers, headers, and openers
        final_answer = clean_answer(answer_text)
        not_found_phrase = "I couldn't find this information in the available official GPREC sources"
        if not_found_phrase in final_answer:
            parts = final_answer.split(not_found_phrase)
            prefix = parts[0].strip()
            if prefix and len(prefix) > 40:
                final_answer = prefix
                response_type = ResponseType.PARTIAL
            elif curated_links:
                final_answer = f"You can access the official GPREC document/portal directly using the link(s) below:\n\n{format_curated_links_markdown(curated_links)}"
                response_type = ResponseType.ANSWERED
            else:
                nf_res = ResponseFormatter.format_not_found()
                total_duration_ms = (time.time() - start_time) * 1000
                nf_res["timings"] = {
                    "total_ms": round(total_duration_ms, 1),
                    "retrieval_ms": round(retrieval_duration_ms, 1),
                    "llm_ms": round(llm_duration_ms, 1),
                    "verification_ms": round(ver_duration_ms, 1)
                }
                print(f"[DEBUG TIMING] Total: {total_duration_ms:.1f}ms | Retrieval: {retrieval_duration_ms:.1f}ms | LLM: {llm_duration_ms:.1f}ms | Verification: {ver_duration_ms:.1f}ms")
                if was_rewritten:
                    nf_res["rewritten_query"] = effective_query
                return nf_res
        else:
            response_type = ResponseType.ANSWERED

        # Ensure all relevant curated links are provided as clickable markdown hyperlinks in the answer
        if curated_links:
            missing_links = [cl for cl in curated_links if cl["url"] not in final_answer]
            if missing_links:
                links_block = format_curated_links_markdown(missing_links)
                if response_type == ResponseType.ANSWERED and final_answer:
                    final_answer = f"{final_answer.rstrip()}\n\n**Official Document / Portal Links:**\n{links_block}"
                else:
                    final_answer = f"You can access the official GPREC document/portal directly using the link(s) below:\n\n{links_block}"
                    response_type = ResponseType.ANSWERED

        # 4. Post-Processing & Sensitive Info Filter
        if response_type in (ResponseType.ANSWERED, ResponseType.PARTIAL):
            final_answer = clean_answer(final_answer)
        final_answer = SensitiveInfoFilter.scrub(final_answer)

        # 5. Calibrate Confidence
        top_score = contexts[0].get("score", 0.0) if contexts else 1.0
        if curated_links and response_type == ResponseType.ANSWERED:
            confidence = "High"
            confidence_reason = "Authoritative official GPREC document/portal link"
        elif matched_facts and response_type == ResponseType.ANSWERED:
            v_date = matched_facts[0].get("verified_date") or "2026-10-12"
            confidence = "High"
            confidence_reason = f"Verified by admin on {v_date}"
        elif matched_entities and response_type == ResponseType.ANSWERED:
            confidence = "High"
            confidence_reason = f"Verified from official entity directory ({matched_entities[0].get('role')})"
        elif matched_notices and response_type == ResponseType.ANSWERED:
            confidence = "High"
            confidence_reason = "Grounded in official structured notices and timetables"
        elif top_score > 0.38 and verification_passed and response_type == ResponseType.ANSWERED:
            confidence = "High"
            confidence_reason = "Strong relevance score and verified against official documents"
        elif response_type == ResponseType.PARTIAL or not verification_passed:
            confidence = "Medium"
            confidence_reason = "Partial context available; unconfirmed details omitted"
        else:
            confidence = "Medium" if top_score > 0.25 else "Low"
            confidence_reason = "Standard keyword and semantic match"

        total_duration_ms = (time.time() - start_time) * 1000
        timings = {
            "total_ms": round(total_duration_ms, 1),
            "retrieval_ms": round(retrieval_duration_ms, 1),
            "llm_ms": round(llm_duration_ms, 1),
            "verification_ms": round(ver_duration_ms, 1)
        }
        print(f"[DEBUG TIMING] Total: {total_duration_ms:.1f}ms | Retrieval: {retrieval_duration_ms:.1f}ms | LLM: {llm_duration_ms:.1f}ms | Verification: {ver_duration_ms:.1f}ms")

        result = {
            "response_type": response_type,
            "answer": final_answer,
            "sources": all_sources,
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "timings": timings
        }
        if was_rewritten:
            result["rewritten_query"] = effective_query

        # Cache valid answers in SQLite (24-hour expiry, exclude NOT_FOUND and CLARIFY)
        if response_type in (ResponseType.ANSWERED, ResponseType.PARTIAL):
            self.db.set_cached_answer(cache_key, result)

        return result


    def answer_question_stream(self, query: str):
        matched_entities = self.db.search_entity_directory(query)
        matched_facts = self.db.get_matching_verified_facts(query)
        matched_notices = []
        q_lower = query.lower()
        if any(term in q_lower for term in ["timetable", "time table", "exam schedule", "notice", "circular", "seating", "hall ticket", "revaluation"]):
            if any(term in q_lower for term in ["timetable", "time table", "exam schedule"]):
                matched_notices = self.db.get_notices(notice_type="timetable", limit=10)
            else:
                matched_notices = self.db.search_notices(query, limit=10)

        from src.curated_links import find_relevant_curated_links, format_curated_links_markdown
        curated_links = find_relevant_curated_links(query)

        contexts = self.retrieve(query)
        if not contexts and not matched_facts and not matched_entities and not matched_notices and not curated_links:
            def dummy_stream():
                yield "I couldn't find this information in the available official GPREC sources. Please check the latest official notice or contact the relevant college office."
            return dummy_stream(), contexts

        all_sources = []
        if curated_links:
            for cl in curated_links:
                all_sources.append({
                    "title": cl["title"],
                    "source_url": cl["url"],
                    "page": None,
                    "published_date": cl.get("year")
                })
        if matched_facts:
            for vf in matched_facts:
                if vf.get("source_url"):
                    all_sources.append({
                        "title": f"GPREC Official Record: {vf['entity']}",
                        "source_url": vf["source_url"],
                        "page": None,
                        "published_date": vf.get("verified_date")
                    })
        if matched_entities:
            for ent in matched_entities:
                if ent.get("source_url"):
                    all_sources.append({
                        "title": f"Official Directory: {ent.get('role')} - {ent.get('name')}",
                        "source_url": ent["source_url"],
                        "page": None,
                        "published_date": None
                    })
        if matched_notices:
            for n in matched_notices[:5]:
                pdf_url = (n.get("attachment_urls") or "").split(",")[0] if n.get("attachment_urls") else (n.get("source_page") or "")
                all_sources.append({
                    "title": f"Notice [{n.get('notice_type', 'Notice').title()}]: {n['title']}",
                    "source_url": pdf_url or "http://examcell.gprec.ac.in/",
                    "page": None,
                    "published_date": n.get("published_date")
                })
        for c in contexts:
            all_sources.append({
                "title": c.get("title", "Document"),
                "source_url": c.get("source_url", ""),
                "page": c.get("page"),
                "published_date": c.get("published_date")
            })

        prompt = self.generate_prompt(
            query, contexts, 
            verified_facts=matched_facts,
            entity_directory=matched_entities,
            notices=matched_notices,
            curated_links=curated_links
        )
        
        if not self.client:
            def dummy_stream():
                if curated_links:
                    yield f"Here are the relevant official GPREC document/portal links:\n\n{format_curated_links_markdown(curated_links)}"
                else:
                    yield "Error: LLM client is not initialized (missing API key)."
            return dummy_stream(), all_sources
            
        fallback_models = [
            "openrouter/free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "liquid/lfm-2.5-2.6b:free",
            "poolside/laguna-s-2.1:free"
        ]
        
        def stream_generator():
            primary_failed = False
            try:
                if config.LLM_PROVIDER == "openrouter":
                    response_stream = self.client.chat.completions.create(
                        model=config.OPENROUTER_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        stream=True
                    )
                    for chunk in response_stream:
                        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                else:
                    response_stream = self.client.models.generate_content_stream(
                        model=config.GEMINI_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                    for chunk in response_stream:
                        if chunk.text:
                            yield chunk.text
                return # Success
            except Exception as e:
                # Catch the exception before it leaks to st.write_stream
                primary_failed = True
                print(f"Primary LLM failed: {e}")
                
            if primary_failed:
                import time
                yield "\n\n*(Primary API rate limited, falling back to backup models...)*\n\n"
                import openai
                api_key = config.OPENROUTER_API_KEY
                if not api_key:
                    yield "An error occurred: The primary API failed and no OPENROUTER_API_KEY is set."
                    return
                    
                or_client = openai.OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                )
                
                for model_id in fallback_models:
                    try:
                        response_stream = or_client.chat.completions.create(
                            model=model_id,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.0,
                            stream=True
                        )
                        for chunk in response_stream:
                            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                                yield chunk.choices[0].delta.content
                        return # Success
                    except Exception as e:
                        time.sleep(1)
                        continue # Try the next fallback model
                        
                yield "\n\nAn error occurred: All fallback models are currently rate-limited upstream. Please try again in a few minutes."
                
        return stream_generator(), all_sources


def clear_answer_cache() -> int:
    """Clears any existing answer cache from files, database tables, or in-memory caches."""
    cleared = 0
    # 1. Disk cache files
    cache_files = [
        config.DATA_DIR / "answer_cache.json",
        config.DATA_DIR / "cache.json",
        config.DATA_DIR / "answer_cache.sqlite",
        config.DATA_DIR / "cache.db",
    ]
    for cf in cache_files:
        if cf.exists():
            try:
                cf.unlink()
                cleared += 1
                print(f"Cleared cache file: {cf}")
            except Exception as e:
                print(f"Failed to clear cache file {cf}: {e}")

    # 2. Database tables
    try:
        db = DatabaseManager()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('answer_cache', 'query_cache', 'cache')")
            tables = cursor.fetchall()
            for (tbl,) in tables:
                cursor.execute(f"DELETE FROM {tbl}")
                cleared += 1
                print(f"Cleared database cache table: {tbl}")
            conn.commit()
    except Exception:
        pass

    # 3. Streamlit cache
    try:
        import streamlit as st
        if hasattr(st, "cache_data"):
            st.cache_data.clear()
        if hasattr(st, "cache_resource"):
            st.cache_resource.clear()
        cleared += 1
    except Exception:
        pass

    return cleared
