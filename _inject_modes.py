
import re, sys

# Write the replacement text to a separate file to avoid encoding issues in this script
REPLACE_WITH = (
    "    try:\n"
    "        # Language detection used by all modes\n"
    "        original_query = request.query\n"
    "        lang_detected  = detect_language(original_query)\n"
    "        english_query  = translate_to_english(original_query, lang_detected)\n"
    "\n"
    "        # Resolve pipeline mode\n"
    '        req_mode = (request.mode or "auto").lower().strip()\n'
    '        if req_mode == "auto":\n'
    "            resolved_mode = await auto_detect_mode(english_query)\n"
    '        elif req_mode in ("chat", "fast", "study", "research"):\n'
    "            resolved_mode = req_mode\n"
    "        else:\n"
    "            resolved_mode = await auto_detect_mode(english_query)\n"
    "\n"
    '        print(f"[MODE] requested={req_mode}  resolved={resolved_mode}  lang={lang_detected}")\n'
    "\n"
    "        # CHAT MODE ---------------------------------------------------\n"
    '        if resolved_mode == "chat":\n'
    "            gen = await run_chat_pipeline(english_query, request.conversation_history)\n"
    '            answer = gen["answer"]\n'
    '            if lang_detected != "en":\n'
    "                answer = translate_from_english(answer, lang_detected)\n"
    "            total_time = (time.time() - total_start) * 1000\n"
    "            return QueryResponse(\n"
    "                answer=answer, citations=[], confidence=0.95,\n"
    "                metadata=QueryMetadata(\n"
    '                    query_type="chat", retrieval_strategy="none", pipeline_mode="chat",\n'
    '                    generation_time_ms=gen["generation_time_ms"],\n'
    '                    tokens_used=gen["tokens_used"], total_time_ms=total_time,\n'
    "                    language_detected=lang_detected, original_query=original_query,\n"
    "                    rewritten_query=english_query,\n"
    "                ),\n"
    "            )\n"
    "\n"
    "        # FAST MODE ---------------------------------------------------\n"
    '        if resolved_mode == "fast":\n'
    "            if not documents_store:\n"
    "                return QueryResponse(\n"
    '                    answer="Upload a PDF first to use Fast mode!",\n'
    "                    citations=[], confidence=0.0,\n"
    '                    metadata=QueryMetadata(pipeline_mode="fast", total_time_ms=0),\n'
    "                )\n"
    "            answer_text, citations, confidence, timing = await run_fast_pipeline(\n"
    "                english_query, request.conversation_history\n"
    "            )\n"
    '            if lang_detected != "en":\n'
    "                answer_text = translate_from_english(answer_text, lang_detected)\n"
    "            total_time = (time.time() - total_start) * 1000\n"
    "            await db.save_query(\n"
    '                query_text=original_query, query_type="fast", strategy="semantic_only",\n'
    "                answer=answer_text, citations=[c.dict() for c in citations],\n"
    "                confidence=confidence, chunks_retrieved=len(citations), chunks_used=len(citations),\n"
    '                tokens_used=timing.get("tokens_used", 0), retrieval_time_ms=0,\n'
    '                generation_time_ms=timing.get("generation_time_ms", 0), total_time_ms=total_time,\n'
    "                mmr_diversity_score=0.0, avg_retrieval_score=confidence, reflection_validated=False,\n"
    "                language_detected=lang_detected, original_query=original_query, rewritten_query=english_query,\n"
    "            )\n"
    "            return QueryResponse(\n"
    "                answer=answer_text, citations=citations, confidence=confidence,\n"
    "                metadata=QueryMetadata(\n"
    '                    query_type="fast", retrieval_strategy="semantic_only", pipeline_mode="fast",\n'
    "                    chunks_retrieved=len(citations), chunks_used=len(citations),\n"
    '                    tokens_used=timing.get("tokens_used", 0),\n'
    '                    generation_time_ms=timing.get("generation_time_ms", 0),\n'
    "                    total_time_ms=total_time, language_detected=lang_detected,\n"
    "                    original_query=original_query, rewritten_query=english_query,\n"
    "                ),\n"
    "            )\n"
    "\n"
    "        # STUDY MODE --------------------------------------------------\n"
    '        if resolved_mode == "study":\n'
    "            if not documents_store:\n"
    "                return QueryResponse(\n"
    '                    answer="Upload a PDF first to use Study mode!",\n'
    "                    citations=[], confidence=0.0,\n"
    '                    metadata=QueryMetadata(pipeline_mode="study", total_time_ms=0),\n'
    "                )\n"
    "            ret_start = time.time()\n"
    "            all_chunks, filenames = get_all_chunks_for_study()\n"
    "            ret_ms    = (time.time() - ret_start) * 1000\n"
    "            gen       = await generate_study_guide_with_gemini(english_query, all_chunks, filenames)\n"
    '            answer    = gen["answer"]\n'
    '            if lang_detected != "en":\n'
    "                answer = translate_from_english(answer, lang_detected)\n"
    "            seen_pgs: set = set()\n"
    "            cit_list: List[Citation] = []\n"
    "            for c in all_chunks:\n"
    '                pk = (c.get("source", ""), c.get("page_num"))\n'
    "                if pk not in seen_pgs:\n"
    "                    seen_pgs.add(pk)\n"
    "                    cit_list.append(Citation(\n"
    '                        text=c["text"][:150] + "..." if len(c["text"]) > 150 else c["text"],\n'
    '                        source=c.get("source", "Unknown"), page=c.get("page_num"),\n'
    '                        section=c.get("section"), confidence=1.0,\n'
    "                    ))\n"
    "            total_time = (time.time() - total_start) * 1000\n"
    "            await db.save_query(\n"
    '                query_text=original_query, query_type="document_study", strategy="full_document",\n'
    '                answer=answer, citations=[c.dict() for c in cit_list[:20]], confidence=0.92,\n'
    "                chunks_retrieved=len(all_chunks), chunks_used=len(all_chunks),\n"
    '                tokens_used=gen["tokens_used"], retrieval_time_ms=ret_ms,\n'
    '                generation_time_ms=gen["generation_time_ms"], total_time_ms=total_time,\n'
    "                mmr_diversity_score=1.0, avg_retrieval_score=1.0, reflection_validated=True,\n"
    "                language_detected=lang_detected, original_query=original_query, rewritten_query=english_query,\n"
    "            )\n"
    "            return QueryResponse(\n"
    "                answer=answer, citations=cit_list[:20], confidence=0.92,\n"
    "                metadata=QueryMetadata(\n"
    '                    query_type="document_study", retrieval_strategy="full_document_synthesis",\n'
    '                    pipeline_mode="study", chunks_retrieved=len(all_chunks), chunks_used=len(all_chunks),\n'
    '                    tokens_used=gen["tokens_used"], retrieval_time_ms=ret_ms,\n'
    '                    generation_time_ms=gen["generation_time_ms"], total_time_ms=total_time,\n'
    "                    avg_retrieval_score=1.0, mmr_diversity_score=1.0, reflection_validated=True,\n"
    "                    language_detected=lang_detected, original_query=original_query, rewritten_query=english_query,\n"
    "                ),\n"
    "            )\n"
    "\n"
    "        # RESEARCH MODE (v4 full pipeline) -- default fallback ---------\n"
    "        if not documents_store:\n"
    "            return QueryResponse(\n"
    '                answer="Please upload a PDF first to enable the research pipeline.",\n'
    "                citations=[], confidence=0.0,\n"
    '                metadata=QueryMetadata(pipeline_mode="research", total_time_ms=0),\n'
    "            )\n"
    "\n"
    '        print("[1/8] CLASSIFICATION...")\n'
    "        classification = classify_query(english_query)\n"
    '        query_type  = classification["type"]\n'
    '        strategy    = classification["strategy"]\n'
    '        print(f"       -> Type: {query_type.upper()}, Strategy: {strategy}")\n'
    "\n"
)

with open("production_agentic.py", "r", encoding="utf-8") as f:
    content = f.read()

# Locate "    try:" inside ask_question by finding the function definition
func_pos = content.find("async def ask_question(request: QueryRequest):")
if func_pos == -1:
    print("ERROR: ask_question not found")
    sys.exit(1)

# Find the try: that follows the function definition
try_pos = content.find("    try:", func_pos)
if try_pos == -1:
    print("ERROR: try block not found after ask_question")
    sys.exit(1)

# Find where STEP 2 starts (we preserve everything from STEP 2 onward)
# STEP 2 is now: "# -- STEP 2: Skip rewriting for study mode"
step2_marker = "        # -- STEP 2: Skip rewriting for study mode"
step2_pos = content.find(step2_marker, func_pos)
if step2_pos == -1:
    print("STEP 2 marker not found, trying fallback")
    step2_marker = "        if query_type == \"document_study\":"
    step2_pos = content.find(step2_marker, func_pos)

if step2_pos == -1:
    print("ERROR: Could not find STEP 2 / document_study marker")
    # Show what's around try_pos
    print("Content around try:", repr(content[try_pos:try_pos+400]))
    sys.exit(1)

print(f"  try: at char {try_pos}")
print(f"  step2 at char {step2_pos}")
print(f"  Replacing chars {try_pos} - {step2_pos}")

new_content = content[:try_pos] + REPLACE_WITH + content[step2_pos:]

with open("production_agentic.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("SUCCESS: ask_question routing replaced")
