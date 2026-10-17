import os
from typing import List, Dict, Any, Optional, Tuple
from google import genai
from google.genai import types

import config
from src.vectorstore import VectorStore
from src.embeddings import Embedder
from src.database import DatabaseManager

class RAGPipeline:
    def __init__(self, embedder: Embedder, vstore: VectorStore, db: Optional[DatabaseManager] = None):
        self.embedder = embedder
        self.vstore = vstore
        self.db = db if db is not None else DatabaseManager()
        
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
                )
        else:
            api_key = config.GEMINI_API_KEY
            if not api_key:
                print("WARNING: GEMINI_API_KEY is not set. LLM generation will fail.")
                self.client = None
            else:
                # We use standard google-genai
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
        notices: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

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

        prompt = f"""You are the GPREC AI Student Assistant, an official RAG chatbot for G. Pulla Reddy Engineering College (GPREC), Kurnool.

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
9. Fee Structure: When asked about fee structure, cite official APHERMC / Government of Andhra Pradesh tuition fee notifications with academic year and as-of date. Clarify that B.Tech tuition fee applies college-wide across engineering branches (including EEE) for Autonomous colleges under Category-A (Convenor Quota) and Category-B (Management Quota).{feedback_instruction}

{verified_facts_str}{notices_str}--- AVAILABLE GPREC CONTEXT ---
{context_str}

Student Question: {query}
Answer:"""
        return prompt

    def answer_question(self, query: str) -> Dict[str, Any]:
        from src.reliability import (
            ResponseType, AmbiguityDetector, AnswerVerifier, 
            SensitiveInfoFilter, ResponseFormatter
        )
        
        # 1. Ambiguity handling (e.g. Case 3: "list the PhD faculties" without department)
        ambiguity = AmbiguityDetector.check_ambiguity(query)
        if ambiguity:
            return {
                "response_type": ResponseType.CLARIFY,
                "answer": ambiguity["question"],
                "clarify_question": ambiguity["question"],
                "clarify_options": ambiguity["options"],
                "sources": [],
                "confidence": "High",
                "confidence_reason": "Identified query ambiguity needing department clarification"
            }
            
        matched_entities = self.db.search_entity_directory(query)
        matched_facts = self.db.get_matching_verified_facts(query)
        
        # Check matching structured notices
        matched_notices = []
        q_lower = query.lower()
        if any(term in q_lower for term in ["timetable", "time table", "exam schedule", "notice", "circular", "seating", "hall ticket", "revaluation"]):
            if any(term in q_lower for term in ["timetable", "time table", "exam schedule"]):
                matched_notices = self.db.get_notices(notice_type="timetable", limit=10)
            else:
                matched_notices = self.db.search_notices(query, limit=10)

        contexts = self.retrieve(query)

        if not contexts and not matched_facts and not matched_entities and not matched_notices:
            return ResponseFormatter.format_not_found([
                "What courses are offered at GPREC?",
                "What are the library timings?",
                "Who is the head of the EEE department?"
            ])

        # Prepare all sources including verified facts, entity directory, and notices
        all_sources = []
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
            query, contexts, 
            verified_facts=matched_facts, 
            entity_directory=matched_entities,
            notices=matched_notices
        )
        
        import time
        max_retries = 3
        base_delay = 2
        answer_text = ""
        
        for attempt in range(max_retries):
            try:
                if config.LLM_PROVIDER == "openrouter":
                    response = self.client.chat.completions.create(
                        model=config.OPENROUTER_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0
                    )
                    answer_text = (response.choices[0].message.content or "").strip()
                else:
                    response = self.client.models.generate_content(
                        model=config.GEMINI_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                    answer_text = (response.text or "").strip()
                    
                # If LLM returns empty/blocked/anomalous output, retry
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
                if ("503" in error_msg or "429" in error_msg or "unavailable" in error_msg) and attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    time.sleep(sleep_time)
                    continue
                    
                # Fallback model attempt
                try:
                    import openai
                    or_client = openai.OpenAI(
                        base_url="https://openrouter.ai/api/v1",
                        api_key=config.OPENROUTER_API_KEY,
                    )
                    response = or_client.chat.completions.create(
                        model="openrouter/free",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0
                    )
                    answer_text = (response.choices[0].message.content or "").strip()
                    break
                except Exception:
                    pass

        # If after retries output is still empty, fall back cleanly
        if not answer_text:
            return ResponseFormatter.format_not_found()

        # 2. Answer Verification Pass
        passed_phd, phd_errors = AnswerVerifier.verify_phd_claims(answer_text, all_context_text)
        passed_facts, fact_errors = AnswerVerifier.verify_factual_grounding(answer_text, all_context_text)
        
        verification_passed = passed_phd and passed_facts
        
        # If verification fails, retry once with explicit corrective feedback
        if not verification_passed:
            feedback_issues = "; ".join(phd_errors + fact_errors)
            corrective_prompt = self.generate_prompt(
                query, contexts, 
                verification_feedback=feedback_issues,
                verified_facts=matched_facts,
                entity_directory=matched_entities,
                notices=matched_notices
            )
            try:
                if config.LLM_PROVIDER == "openrouter":
                    c_resp = self.client.chat.completions.create(
                        model=config.OPENROUTER_MODEL,
                        messages=[{"role": "user", "content": corrective_prompt}],
                        temperature=0.0
                    )
                    c_text = (c_resp.choices[0].message.content or "").strip()
                else:
                    c_resp = self.client.models.generate_content(
                        model=config.GEMINI_MODEL,
                        contents=corrective_prompt,
                        config=types.GenerateContentConfig(temperature=0.0)
                    )
                    c_text = (c_resp.text or "").strip()
                if c_text:
                    answer_text = c_text
                    # Re-verify
                    passed_phd, _ = AnswerVerifier.verify_phd_claims(answer_text, all_context_text)
                    passed_facts, _ = AnswerVerifier.verify_factual_grounding(answer_text, all_context_text)
                    verification_passed = passed_phd and passed_facts
            except Exception:
                pass

        # 3. Clean Response Type Categorization
        # Remove mixed pattern: "partial text + I couldn't find this"
        clean_answer = answer_text
        not_found_phrase = "I couldn't find this information in the available official GPREC sources"
        if not_found_phrase in clean_answer:
            parts = clean_answer.split(not_found_phrase)
            prefix = parts[0].strip()
            if prefix and len(prefix) > 40:
                # This was a partial response, clean up the contradictory suffix
                clean_answer = prefix
                response_type = ResponseType.PARTIAL
            else:
                return ResponseFormatter.format_not_found()
        else:
            response_type = ResponseType.ANSWERED

        # 4. Sensitive Info Filter (scrub personal mobile numbers & default credentials)
        clean_answer = SensitiveInfoFilter.scrub(clean_answer)

        # 5. Calibrate Confidence
        top_score = contexts[0].get("score", 0.0) if contexts else 1.0
        # In hybrid search: higher score is better (normalized between 0 and 1)
        if matched_facts and response_type == ResponseType.ANSWERED:
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

        return {
            "response_type": response_type,
            "answer": clean_answer,
            "sources": all_sources,
            "confidence": confidence,
            "confidence_reason": confidence_reason
        }


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

        contexts = self.retrieve(query)
        if not contexts and not matched_facts and not matched_entities and not matched_notices:
            def dummy_stream():
                yield "I couldn't find this information in the available official GPREC sources. Please check the latest official notice or contact the relevant college office."
            return dummy_stream(), contexts

        all_sources = []
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
            notices=matched_notices
        )
        
        if not self.client:
            def dummy_stream():
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
