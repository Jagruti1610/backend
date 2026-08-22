import json
import re
import time
import random
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from ..core.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

MODEL_NAMES = {
    "flash": "gemini-3.6-flash",
    "pro": "gemini-3.1-pro-preview",  # "gemini-3-pro" is retired -> 404. Use the current preview id.
}

# ~4 characters per token is a safe rough estimate for English/legal text.
# Keep single-call prompts well under typical free-tier TPM limits.
SAFE_CHUNK_CHARS = 60000       # per-chunk text size sent to the model
MAX_RETRIES = 5                 # retries specifically for 429 rate-limit errors
BASE_BACKOFF_SECONDS = 3        # base for exponential backoff


def get_gemini_model(model_name: str = "flash"):
    resolved = MODEL_NAMES.get(model_name, MODEL_NAMES["flash"])
    return genai.GenerativeModel(resolved)


def call_gemini(prompt: str, model_choice: str = "flash", retry_count: int = 0) -> str:
    """
    Calls Gemini via the SDK with exponential backoff + jitter on rate-limit
    (429 / ResourceExhausted) errors, so a single throttle doesn't crash the request.
    """
    if not settings.GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY is not set. Check your .env file.")

    model = get_gemini_model(model_choice)

    try:
        response = model.generate_content(prompt)

        if not response.candidates:
            reason = getattr(response.prompt_feedback, "block_reason", "unknown")
            raise Exception(f"Gemini returned no candidates (reason: {reason}).")

        return response.text

    except google_exceptions.ResourceExhausted as e:
        # This is Gemini's 429 rate-limit error surfaced through the SDK.
        if retry_count < MAX_RETRIES:
            wait_time = (BASE_BACKOFF_SECONDS * (2 ** retry_count)) + random.uniform(0, 1)
            print(f"[Gemini] Rate limited (attempt {retry_count + 1}/{MAX_RETRIES}). "
                  f"Waiting {wait_time:.1f}s before retry...")
            time.sleep(wait_time)
            return call_gemini(prompt, model_choice, retry_count + 1)
        else:
            raise Exception(
                "Gemini API rate limit exceeded after multiple retries. "
                "Your API key's free-tier quota (requests/tokens per minute) may be too low "
                "for this request size, or too many requests were sent in a short time. "
                "Try again in a minute, use a shorter document, or switch to the 'flash' model."
            ) from e

    except google_exceptions.NotFound as e:
        raise Exception(f"Gemini model not found ('{model_choice}'). Check the model ID. {e}") from e

    except google_exceptions.GoogleAPIError as e:
        raise Exception(f"Gemini API Error: {e}") from e


def chunk_text(text: str, chunk_size: int = SAFE_CHUNK_CHARS) -> list[str]:
    """Splits text into chunks on paragraph boundaries, each under chunk_size chars."""
    if len(text) <= chunk_size:
        return [text]

    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size):
                    chunks.append(para[i:i + chunk_size])
                current = ""
            else:
                current = para + "\n\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks


def generate_summary(text: str, model_choice: str = "flash", language: str = "English") -> str:
    """
    Short documents: single call.
    Long documents: map-reduce — summarize each chunk, then combine those
    partial summaries into one final structured summary. Keeps each individual
    call small enough to avoid tripping token-per-minute rate limits, instead
    of sending the whole document (up to 100k chars) at once.
    """
    chunks = chunk_text(text)

    if len(chunks) == 1:
        prompt = f"""
        You are a highly skilled legal assistant. Analyze the following legal document text and provide a structured summary.
        Format your response with these exact headings:

        **Facts:** (Briefly list the key facts)
        **Issues:** (What legal questions are being raised?)
        **Judgment:** (What was the final decision?)
        **Ratio Decidendi:** (The legal principle/reasoning behind the decision)
        **Conclusion:** (Final summary in 2-3 sentences)

        Respond in {language} language.

        Document Text:
        {chunks[0]}
        """
        return call_gemini(prompt, model_choice)

    # Step 1: summarize each chunk (small delay between calls to stay under RPM limits)
    partial_summaries = []
    for i, chunk in enumerate(chunks):
        chunk_prompt = f"""
        You are a legal assistant. Briefly summarize the key facts, issues, and any decisions
        mentioned in this excerpt (part {i + 1} of {len(chunks)}) of a larger legal document.
        Be concise — this is an intermediate summary that will be combined with others later.

        Excerpt:
        {chunk}
        """
        partial_summaries.append(call_gemini(chunk_prompt, model_choice))
        if i < len(chunks) - 1:
            time.sleep(1.5)  # small gap between calls to respect requests-per-minute limits

    # Step 2: combine partial summaries into the final structured summary
    combined = "\n\n---\n\n".join(partial_summaries)
    final_prompt = f"""
    You are a highly skilled legal assistant. Below are sequential partial summaries of different
    sections of one legal document. Combine them into a single coherent structured summary.
    Format your response with these exact headings:

    **Facts:** (Briefly list the key facts)
    **Issues:** (What legal questions are being raised?)
    **Judgment:** (What was the final decision?)
    **Ratio Decidendi:** (The legal principle/reasoning behind the decision)
    **Conclusion:** (Final summary in 2-3 sentences)

    Respond in {language} language.

    Partial Summaries:
    {combined}
    """
    return call_gemini(final_prompt, model_choice)


def chat_with_document(question: str, context_text: str, model_choice: str = "flash") -> str:
    # Keep the context within a safe single-call token budget.
    safe_context = context_text[:SAFE_CHUNK_CHARS * 2]  # ~60k chars, single call

    prompt = f"""
    You are a professional AI legal assistant helping the user understand a document they uploaded.
    Maintain a polished, professional tone throughout — like a knowledgeable assistant, not a
    casual chatbot.

    Document Context:
    {safe_context}

    User Message: {question}

    Instructions for your reply:
    1. If the message is a greeting or simple pleasantry (e.g. "hello", "hi", "how are you",
       "thank you"), respond briefly and professionally, and naturally invite the user to ask
       about the document (e.g. "Hello! I'm ready to help with your document — feel free to ask
       me anything about it.").
    2. For substantive questions, your primary focus is the document. If the document contains
       the answer, explain it clearly and professionally in a few sentences.
    3. If the question is about the document but the document doesn't cover it, say so plainly
       and professionally, and briefly offer relevant general knowledge if it would genuinely help.
    4. Do not go off on unrelated tangents. Keep the conversation centered on the document and
       the user's practical needs regarding it.
    5. Keep replies clear, concise, and professional. Do not repeat yourself.

    Answer:
    """
    return call_gemini(prompt, model_choice)


def translate_summary(summary_text: str, target_language: str, model_choice: str = "flash") -> str:
    prompt = f"""
    Translate the following legal document summary into {target_language}.
    Keep the same structure and headings (like **Facts:**, **Issues:**, etc.) — only translate
    the actual content text, not the formatting/markdown symbols. Keep it natural and clear,
    not a robotic word-by-word translation.

    Summary to translate:
    {summary_text}

    Translated summary (in {target_language}):
    """
    return call_gemini(prompt, model_choice)


def analyze_document(text: str, model_choice: str = "flash") -> dict:
    """
    Asks Gemini to identify the document type and return relevant clauses/risk/PII
    analysis for THAT type — not a fixed generic contract checklist.
    """
    safe_text = text[:SAFE_CHUNK_CHARS * 2]

    prompt = f"""
    You are a legal AI analyst. Read the following document and first identify what TYPE of
    legal document it is (e.g. contract/agreement, court notice, court order, affidavit,
    police notice, employment letter, etc.). Then, based ONLY on what is actually relevant
    to THAT specific document type, provide an analysis.

    Do NOT apply a generic "contract clauses" checklist to every document — a court notice,
    for example, should be judged on notice-appropriate elements (issuing authority, recipient,
    date, allegations, response deadline, signature/seal), not on things like "confidentiality
    clause" or "termination clause" which only apply to contracts.

    Return STRICTLY VALID JSON, with no markdown formatting, no code fences, and no extra text
    outside the JSON object. Use exactly these keys:

    {{
      "document_type": "short label for the document type",
      "risk_score": <integer 0-100, overall risk/attention level for this document>,
      "risk_level": "Low" | "Medium" | "High",
      "important_clauses": ["relevant elements/clauses that ARE present in this document"],
      "missing_clauses": ["relevant elements/clauses that SHOULD be present for this document type but are missing or unclear"],
      "pii_findings": {{
        "names": [...], "phone_numbers": [...], "emails": [...], "addresses": [...], "id_numbers": [...]
      }},
      "recommendations": ["short, practical recommendations for the reader"],
      "suggested_questions": ["a few natural questions a user might want to ask about this document"]
    }}

    Document Text:
    {safe_text}
    """

    raw = call_gemini(prompt, model_choice)

    # Gemini kabhi extra text/preamble bhi likh deta hai — isliye sirf pehli { se lekar aakhri } tak ka
    # hissa nikaal ke parse karte hain, poore raw text ko strict parse karne ki koshish nahi karte.
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        print(f"[analyze_document] Could not find JSON in Gemini response:\n{raw[:500]}")
        return {}

    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[analyze_document] JSON parse failed: {e}\nRaw match:\n{match.group(0)[:500]}")
        return {}

    pii = data.get("pii_findings") or {}
    pii_count = sum(len(v) for v in pii.values() if isinstance(v, list))

    return {
        "risk_score": data.get("risk_score"),
        "risk_level": data.get("risk_level"),
        "important_clauses": data.get("important_clauses") or [],
        "missing_clauses": data.get("missing_clauses") or [],
        "pii_findings": pii,
        "pii_found_count": pii_count,
        "recommendations": data.get("recommendations") or [],
        "suggested_questions": data.get("suggested_questions") or [],
    }