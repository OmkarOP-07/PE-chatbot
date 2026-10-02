import os
import json
import uuid
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Anthropic client import with graceful error handling
try:
    import anthropic
    HAS_ANTHROPIC_PKG = True
except ImportError:
    HAS_ANTHROPIC_PKG = False

# Paths to data files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CATALOGUE_FILE = os.path.join(BASE_DIR, "catalogue.json")
REQUESTS_FILE = os.path.join(BASE_DIR, "requests.json")

# Default catalogue in case catalogue.json is missing or corrupted
DEFAULT_CATALOGUE = [
    {"id": "B101", "title": "Python Programming", "category": "Programming", "available": 3},
    {"id": "B102", "title": "Database Management Systems", "category": "Database", "available": 2},
    {"id": "B103", "title": "Computer Networks", "category": "Networking", "available": 0},
    {"id": "B104", "title": "Operating Systems", "category": "Systems", "available": 4},
    {"id": "B105", "title": "Artificial Intelligence", "category": "AI", "available": 1},
    {"id": "B106", "title": "Web Technology", "category": "Web Development", "available": 2}
]

# ---------------------------------------------------------
# DATA STORAGE HELPERS
# ---------------------------------------------------------
def load_catalogue():
    """Load catalogue data from JSON file."""
    if not os.path.exists(CATALOGUE_FILE):
        save_catalogue(DEFAULT_CATALOGUE)
        return DEFAULT_CATALOGUE
    try:
        with open(CATALOGUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading catalogue: {e}")
        return DEFAULT_CATALOGUE

def save_catalogue(catalogue):
    """Save catalogue data to JSON file."""
    try:
        with open(CATALOGUE_FILE, "w", encoding="utf-8") as f:
            json.dump(catalogue, f, indent=2)
    except Exception as e:
        st.error(f"Error saving catalogue: {e}")

def load_requests():
    """Load borrowing requests from JSON file."""
    if not os.path.exists(REQUESTS_FILE):
        save_requests([])
        return []
    try:
        with open(REQUESTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading requests: {e}")
        return []

def save_requests(requests_list):
    """Save borrowing requests to JSON file."""
    try:
        with open(REQUESTS_FILE, "w", encoding="utf-8") as f:
            json.dump(requests_list, f, indent=2)
    except Exception as e:
        st.error(f"Error saving requests: {e}")

def record_borrowing_request(book_id):
    """Record a borrowing request and decrement available count."""
    catalogue = load_catalogue()
    target_book = None
    for book in catalogue:
        if book["id"].upper() == book_id.upper():
            target_book = book
            break

    if not target_book:
        return False, "Book not found in catalogue."

    if target_book["available"] <= 0:
        return False, f"Sorry, {target_book['title']} ({target_book['id']}) is currently unavailable."

    # Decrement available copy
    target_book["available"] -= 1
    save_catalogue(catalogue)

    # Append to requests.json
    req_id = f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    new_request = {
        "request_id": req_id,
        "book_id": target_book["id"],
        "book_title": target_book["title"],
        "category": target_book["category"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Confirmed"
    }

    requests_list = load_requests()
    requests_list.append(new_request)
    save_requests(requests_list)

    return True, new_request

def find_books_in_catalogue(query):
    """Search books by title, ID, or category."""
    catalogue = load_catalogue()
    q = query.strip().lower()
    if not q:
        return []
    matches = []
    for b in catalogue:
        if (q in b["title"].lower() or 
            q in b["id"].lower() or 
            q in b["category"].lower()):
            matches.append(b)
    return matches

def find_exact_or_best_book(query):
    """Find the single most relevant book from a user query."""
    catalogue = load_catalogue()
    q = query.lower()
    
    # Check exact ID first
    for b in catalogue:
        if b["id"].lower() in q:
            return b

    # Check title match
    for b in catalogue:
        if b["title"].lower() in q:
            return b

    # Check individual significant keywords in title
    for b in catalogue:
        words = [w.lower() for w in b["title"].split() if len(w) > 3]
        if any(w in q for w in words):
            return b

    # Check category match
    for b in catalogue:
        if b["category"].lower() in q:
            return b

    return None

# ---------------------------------------------------------
# SYSTEM PROMPT FOR CLAUDE
# ---------------------------------------------------------
SYSTEM_PROMPT = """You are a friendly College Library Assistant chatbot.

You can ONLY help students with:
* Searching books.
* Checking book availability.
* Showing available copies.
* Creating borrowing requests.
* Confirming or cancelling requests.

Rules:
1. Use only the supplied library catalogue.
2. Never invent book titles or availability.
3. Never claim a book is available when its available count is zero.
4. Never record a request without explicit confirmation.
5. Do not answer academic, programming, personal, or unrelated questions.
6. Keep responses short and friendly.

Fallback:
Sorry, I can only help with the college library catalogue and borrowing requests."""

# ---------------------------------------------------------
# CLAUDE AND RULE-BASED BACKEND ENGINE
# ---------------------------------------------------------
def call_claude_api(messages_history, current_catalogue, api_key):
    """Call Anthropic Claude API with context and strict guardrails."""
    if not HAS_ANTHROPIC_PKG:
        raise RuntimeError("anthropic package is not installed.")

    client = anthropic.Anthropic(api_key=api_key)

    catalogue_summary = json.dumps(current_catalogue, indent=2)
    extended_system = f"{SYSTEM_PROMPT}\n\nCURRENT OFFICIAL LIBRARY CATALOGUE (GROUND TRUTH):\n{catalogue_summary}"

    # Prepare message format for Anthropic
    anthropic_messages = []
    for msg in messages_history:
        if msg["role"] in ["user", "assistant"]:
            anthropic_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

    # Ensure last message is from user
    if not anthropic_messages or anthropic_messages[-1]["role"] != "user":
        return "How can I help you with our library catalogue today?"

    response = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=350,
        system=extended_system,
        messages=anthropic_messages,
        temperature=0.0
    )
    return response.content[0].text

def rule_based_fallback_response(user_text, last_book_context, pending_request):
    """
    Deterministic rule-based engine implementing all required flows and test cases.
    Ensures 100% functionality even without an API key.
    """
    import re
    # Remove leading/trailing whitespace and normalize
    raw_lower = user_text.strip().lower()
    # Strip common punctuation for clean matching
    text_clean = re.sub(r"[^\w\s]", "", raw_lower).strip()
    catalogue = load_catalogue()

    # Out-of-scope trigger phrases (Assignments, general queries, programming questions)
    out_of_scope_keywords = [
        "assignment", "solve", "homework", "exam", "weather",
        "recipe", "poem", "joke", "who are you", "what is your name",
        "calculate", "essay", "write a", "teach me"
    ]
    
    # Check for direct out of scope questions (unless referring to the book title itself)
    if any(k in text_clean for k in out_of_scope_keywords):
        return {
            "text": "Sorry, I can only help with the college library catalogue and borrowing requests.",
            "books": [],
            "action": None
        }

    # Edge case: Prompt injection / hallucination pressure (Test 3)
    if "just say it is available" in text_clean or "pretend it is available" in text_clean or "make it available" in text_clean:
        return {
            "text": "I cannot change or invent catalogue information. The book is currently unavailable.",
            "books": [],
            "action": None
        }

    # Confirmation / Cancellation flow when a request is pending (Test 1 & Test 5)
    if pending_request:
        confirm_words = ["yes", "yeah", "yep", "confirm", "confirm request", "please confirm", "yes please", "sure", "ok", "okay"]
        cancel_words = ["no", "cancel", "cancel it", "cancel request", "stop", "nevermind", "no thanks", "abort"]
        
        if text_clean in confirm_words or any(text_clean.startswith(w) for w in confirm_words):
            success, result = record_borrowing_request(pending_request["id"])
            if success:
                return {
                    "text": "Your borrowing request has been recorded successfully.",
                    "books": [],
                    "action": "clear_pending"
                }
            else:
                return {
                    "text": f"Unable to process request: {result}",
                    "books": [],
                    "action": "clear_pending"
                }
        elif text_clean in cancel_words or any(w in text_clean for w in cancel_words):
            return {
                "text": "Your request has been cancelled.",
                "books": [],
                "action": "clear_pending"
            }
        else:
            return {
                "text": f"Would you like to confirm your request for {pending_request['title']} ({pending_request['id']})? Please reply 'Yes' or 'Cancel'.",
                "books": [pending_request],
                "action": "keep_pending"
            }

    # Greeting (Test 1)
    greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "greetings"]
    if text_clean in greetings or any(text_clean.startswith(f"{g} ") for g in greetings):
        return {
            "text": "Hello! Welcome to the College Library. How can I help?",
            "books": [],
            "action": None
        }

    # Show all books
    if "all books" in text_clean or "show catalogue" in text_clean or "list books" in text_clean or "all the books" in text_clean:
        return {
            "text": "Here are all the books currently registered in the college library catalogue:",
            "books": catalogue,
            "action": None
        }

    # Borrow intent triggers
    borrow_triggers = ["borrow", "issue", "take", "checkout", "i want", "reserve", "get"]
    is_borrow_intent = any(trigger in text_clean for trigger in borrow_triggers)

    matched_book = find_exact_or_best_book(text_clean)
    
    # If student refers to context book (e.g. "I want to borrow it" or "borrow it")
    if not matched_book and last_book_context and ("it" in text_clean.split() or "that" in text_clean.split() or text_clean in ["borrow", "i want to borrow", "borrow it"]):
        # Refresh from current catalogue
        for b in catalogue:
            if b["id"] == last_book_context["id"]:
                matched_book = b
                break

    # If user wants to borrow a book but hasn't specified which one
    if is_borrow_intent and not matched_book:
        # Check if they asked an invalid book
        # e.g., "I want Quantum Computing"
        cleaned_without_triggers = text_clean
        for tr in borrow_triggers:
            cleaned_without_triggers = cleaned_without_triggers.replace(tr, "").strip()
        if len(cleaned_without_triggers) > 2 and cleaned_without_triggers not in ["a book", "the book", "book"]:
            return {
                "text": "Sorry, I couldn't find that book in the library catalogue.",
                "books": [],
                "action": None
            }
        return {
            "text": "Which book would you like to borrow? Please provide the title or book ID (e.g., Python Programming or B101).",
            "books": [],
            "action": None
        }

    # If borrow intent and book found
    if is_borrow_intent and matched_book:
        if matched_book["available"] > 0:
            return {
                "text": f"Would you like to confirm your request for {matched_book['title']} ({matched_book['id']})?",
                "books": [matched_book],
                "action": "set_pending",
                "pending_book": matched_book
            }
        else:
            return {
                "text": f"{matched_book['title']} ({matched_book['id']}) has 0 available copies and is currently unavailable.",
                "books": [matched_book],
                "action": None
            }

    # Check availability or search
    if matched_book:
        if matched_book["available"] > 0:
            return {
                "text": f"{matched_book['title']} ({matched_book['id']}) has {matched_book['available']} available copies.",
                "books": [matched_book],
                "action": "set_context",
                "context_book": matched_book
            }
        else:
            return {
                "text": f"{matched_book['title']} ({matched_book['id']}) has 0 available copies and is currently unavailable.",
                "books": [matched_book],
                "action": "set_context",
                "context_book": matched_book
            }

    # If asking for a book not in catalogue (Test 4: "Do you have Quantum Computing?")
    search_indicators = ["do you have", "have you got", "is there", "search", "find", "book about", "can i get", "is"]
    if any(ind in text_clean for ind in search_indicators) or (len(text_clean.split()) <= 4 and not any(g in text_clean for g in greetings)):
        return {
            "text": "Sorry, I couldn't find that book in the library catalogue.",
            "books": [],
            "action": None
        }

    # Default fallback
    return {
        "text": "Sorry, I can only help with the college library catalogue and borrowing requests.",
        "books": [],
        "action": None
    }

# ---------------------------------------------------------
# UI RENDERING FUNCTIONS
# ---------------------------------------------------------
def render_book_card(book):
    """Render a clean, modern book card with availability status."""
    is_available = book["available"] > 0
    status_label = "Available" if is_available else "Unavailable"
    badge_bg = "#dcfce7" if is_available else "#fee2e2"
    badge_color = "#166534" if is_available else "#991b1b"
    border_color = "#22c55e" if is_available else "#ef4444"

    card_html = f"""
    <div style="
        border: 1px solid {border_color};
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
        background-color: #fafafa;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-weight: 700; font-size: 1.05rem; color: #1e293b;">{book['title']}</span>
            <span style="
                background-color: {badge_bg};
                color: {badge_color};
                padding: 3px 8px;
                border-radius: 9999px;
                font-size: 0.8rem;
                font-weight: 600;
            ">{status_label}</span>
        </div>
        <div style="font-size: 0.88rem; color: #475569; display: flex; gap: 16px; flex-wrap: wrap;">
            <span><strong>ID:</strong> {book['id']}</span>
            <span><strong>Category:</strong> {book['category']}</span>
            <span><strong>Available Copies:</strong> <strong style="color: {'#166534' if is_available else '#991b1b'};">{book['available']}</strong></span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

# ---------------------------------------------------------
# STREAMLIT APPLICATION
# ---------------------------------------------------------
def main():
    st.set_page_config(
        page_title="College Library Assistant",
        page_icon="📚",
        layout="wide"
    )

    # Custom styling
    st.markdown("""
        <style>
        .stChatMessage {
            padding: 0.5rem 1rem;
        }
        .main-header {
            margin-bottom: 0.5rem;
        }
        .quick-btn-container {
            margin-top: 1rem;
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: #f8fafc;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }
        </style>
    """, unsafe_allow_html=True)

    # Initialize Session State
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hello! Welcome to the College Library. How can I help you today?",
                "books": []
            }
        ]

    if "pending_request" not in st.session_state:
        st.session_state.pending_request = None

    if "last_book_context" not in st.session_state:
        st.session_state.last_book_context = None

    if "quick_prompt_input" not in st.session_state:
        st.session_state.quick_prompt_input = None

    # Load API key directly from environment (.env)
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    # ---------------------------------------------------------
    # SIDEBAR
    # ---------------------------------------------------------
    with st.sidebar:
        st.title("📚 College Library Assistant")
        st.caption("Prompt Engineering Practical 5.2 – Task-Specific Chatbot")
        st.divider()

        # Engine status
        if api_key:
            st.success("Claude AI Mode Active", icon="🤖")
        else:
            st.info("Rule-Based Mode Active", icon="⚡")

        st.divider()

        # Actions
        if st.button("🔄 New Chat", use_container_width=True):
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": "Hello! Welcome to the College Library. How can I help you today?",
                    "books": []
                }
            ]
            st.session_state.pending_request = None
            st.session_state.last_book_context = None
            st.session_state.quick_prompt_input = None
            st.rerun()

        # View Catalogue Expander
        with st.expander("📖 View Library Catalogue", expanded=False):
            catalogue = load_catalogue()
            for book in catalogue:
                render_book_card(book)

        # View Borrowing Requests Expander
        with st.expander("📋 View Borrowing Requests", expanded=False):
            requests_list = load_requests()
            if requests_list:
                for req in reversed(requests_list):
                    st.markdown(f"""
                    **{req['book_title']}** ({req['book_id']})  
                    *Request ID:* `{req['request_id']}`  
                    *Status:* `{req['status']}` | *Date:* {req['timestamp']}
                    ---
                    """)
            else:
                st.caption("No borrowing requests recorded yet.")

        st.divider()
        st.markdown("""
        **About this Assistant:**
        * Search catalogue by title or category
        * Real-time availability checks
        * Guided 2-step borrowing confirmations
        * Persistent JSON catalogue & requests
        """)

    # ---------------------------------------------------------
    # MAIN HEADER & WELCOME QUICK ACTIONS
    # ---------------------------------------------------------
    st.title("📚 College Library Assistant Chatbot")
    st.write("Welcome to the college library! Ask about books, check availability, or request a book to borrow.")

    # Suggested Prompts (shown especially when conversation is short)
    if len(st.session_state.messages) <= 1:
        st.markdown("##### 💡 Suggested Prompts:")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("Find Python Programming", key="sp1", use_container_width=True):
                st.session_state.quick_prompt_input = "Find Python Programming"
                st.rerun()
        with col2:
            if st.button("Show all books", key="sp2", use_container_width=True):
                st.session_state.quick_prompt_input = "Show all books"
                st.rerun()
        with col3:
            if st.button("Is Computer Networks available?", key="sp3", use_container_width=True):
                st.session_state.quick_prompt_input = "Is Computer Networks available?"
                st.rerun()
        with col4:
            if st.button("I want to borrow a book", key="sp4", use_container_width=True):
                st.session_state.quick_prompt_input = "I want to borrow a book"
                st.rerun()

    # ---------------------------------------------------------
    # DISPLAY CHAT HISTORY
    # ---------------------------------------------------------
    chat_container = st.container()
    with chat_container:
        for idx, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if "books" in message and message["books"]:
                    for b in message["books"]:
                        render_book_card(b)

    # ---------------------------------------------------------
    # PENDING REQUEST CONFIRMATION WIDGET
    # ---------------------------------------------------------
    if st.session_state.pending_request:
        st.warning(
            f"**Pending Confirmation:** Do you want to borrow **{st.session_state.pending_request['title']} ({st.session_state.pending_request['id']})**?",
            icon="⚠️"
        )
        conf_col1, conf_col2, _ = st.columns([1, 1, 3])
        with conf_col1:
            if st.button("✅ Confirm Request", type="primary", use_container_width=True):
                success, result = record_borrowing_request(st.session_state.pending_request["id"])
                if success:
                    st.session_state.messages.append({
                        "role": "user",
                        "content": "Yes, confirm my borrowing request."
                    })
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Your borrowing request has been recorded successfully. Request ID: **{result['request_id']}** for **{result['book_title']} ({result['book_id']})**.",
                        "books": []
                    })
                else:
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Unable to process request: {result}",
                        "books": []
                    })
                st.session_state.pending_request = None
                st.rerun()

        with conf_col2:
            if st.button("❌ Cancel Request", use_container_width=True):
                st.session_state.messages.append({
                    "role": "user",
                    "content": "Cancel it."
                })
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Your request has been cancelled.",
                    "books": []
                })
                st.session_state.pending_request = None
                st.rerun()

    # ---------------------------------------------------------
    # PROCESS INPUT (CHAT INPUT OR QUICK PROMPT)
    # ---------------------------------------------------------
    user_prompt = st.chat_input("Ask about books, check availability, or request a book...")

    if st.session_state.quick_prompt_input:
        user_prompt = st.session_state.quick_prompt_input
        st.session_state.quick_prompt_input = None

    if user_prompt:
        clean_prompt = user_prompt.strip()
        if not clean_prompt:
            return

        # Add user message to state
        st.session_state.messages.append({
            "role": "user",
            "content": clean_prompt
        })

        # Process message with spinner
        with st.spinner("Processing your request..."):
            catalogue = load_catalogue()
            
            # Step 1: Execute rule-based backend logic to verify catalogue operations & guardrails
            rb_result = rule_based_fallback_response(
                clean_prompt,
                st.session_state.last_book_context,
                st.session_state.pending_request
            )

            # Update state actions based on Python backend verification
            if rb_result.get("action") == "clear_pending":
                st.session_state.pending_request = None
            elif rb_result.get("action") == "set_pending":
                st.session_state.pending_request = rb_result.get("pending_book")
            elif rb_result.get("action") == "set_context":
                st.session_state.last_book_context = rb_result.get("context_book")

            final_text = rb_result["text"]
            books_to_show = rb_result.get("books", [])

            # Step 2: If Claude API key is provided and message is not an explicit confirmed/cancelled backend operation
            if api_key and HAS_ANTHROPIC_PKG and rb_result.get("action") not in ["clear_pending", "set_pending"]:
                try:
                    claude_reply = call_claude_api(
                        st.session_state.messages,
                        catalogue,
                        api_key
                    )
                    if claude_reply and len(claude_reply.strip()) > 0:
                        final_text = claude_reply
                except Exception as api_err:
                    st.warning(f"Claude API notification: Using reliable fallback response ({api_err})")

            # Append assistant message
            st.session_state.messages.append({
                "role": "assistant",
                "content": final_text,
                "books": books_to_show
            })

        st.rerun()

if __name__ == "__main__":
    main()
