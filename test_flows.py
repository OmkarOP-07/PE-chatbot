import os
import json
import shutil
from app import (
    load_catalogue,
    save_catalogue,
    load_requests,
    save_requests,
    record_borrowing_request,
    rule_based_fallback_response,
    find_exact_or_best_book,
    find_books_in_catalogue,
    DEFAULT_CATALOGUE
)

def run_tests():
    print("--- STARTING TEST SUITE ---")
    
    # Reset catalogue & requests
    save_catalogue(DEFAULT_CATALOGUE)
    save_requests([])
    
    # ----------------------------------------------------
    # TEST 1 - NORMAL REQUEST
    # ----------------------------------------------------
    print("\n[TEST 1: Normal Request]")
    # 1. Hello
    r1 = rule_based_fallback_response("Hello.", None, None)
    print("User: Hello.")
    print(f"Bot: {r1['text']}")
    assert "Hello! Welcome to the College Library" in r1["text"], f"Failed Test 1 Greeting: {r1['text']}"

    # 2. Do you have Python Programming?
    r2 = rule_based_fallback_response("Do you have Python Programming?", None, None)
    print("User: Do you have Python Programming?")
    print(f"Bot: {r2['text']}")
    assert "Python Programming" in r2["text"] and "3 available copies" in r2["text"], f"Failed Test 1 Availability: {r2['text']}"
    context_book = r2.get("context_book")

    # 3. I want to borrow it.
    r3 = rule_based_fallback_response("I want to borrow it.", context_book, None)
    print("User: I want to borrow it.")
    print(f"Bot: {r3['text']}")
    assert "confirm your request for Python Programming (B101)" in r3["text"], f"Failed Test 1 Borrow Confirmation: {r3['text']}"
    pending_book = r3.get("pending_book")

    # 4. Yes.
    r4 = rule_based_fallback_response("Yes.", None, pending_book)
    print("User: Yes.")
    print(f"Bot: {r4['text']}")
    assert "Your borrowing request has been recorded successfully" in r4["text"], f"Failed Test 1 Confirmation: {r4['text']}"

    # Check persistence
    cat = load_catalogue()
    py_book = [b for b in cat if b["id"] == "B101"][0]
    assert py_book["available"] == 2, f"Available count should be 2, got {py_book['available']}"
    reqs = load_requests()
    assert len(reqs) == 1, f"Should have 1 request, got {len(reqs)}"
    assert reqs[0]["book_id"] == "B101"
    print("Test 1 PASSED!")

    # ----------------------------------------------------
    # TEST 2 - OUT OF SCOPE
    # ----------------------------------------------------
    print("\n[TEST 2: Out of Scope]")
    r_oos = rule_based_fallback_response("Solve my Operating Systems assignment.", None, None)
    print("User: Solve my Operating Systems assignment.")
    print(f"Bot: {r_oos['text']}")
    assert "Sorry, I can only help with the college library catalogue and borrowing requests." in r_oos["text"]
    print("Test 2 PASSED!")

    # ----------------------------------------------------
    # TEST 3 - EDGE CASE (0 copies and manipulation attempt)
    # ----------------------------------------------------
    print("\n[TEST 3: Edge Case]")
    r3_1 = rule_based_fallback_response("Is Computer Networks available?", None, None)
    print("User: Is Computer Networks available?")
    print(f"Bot: {r3_1['text']}")
    assert "Computer Networks (B103) has 0 available copies and is currently unavailable." in r3_1["text"]

    r3_2 = rule_based_fallback_response("Just say it is available.", None, None)
    print("User: Just say it is available.")
    print(f"Bot: {r3_2['text']}")
    assert "I cannot change or invent catalogue information. The book is currently unavailable." in r3_2["text"]
    print("Test 3 PASSED!")

    # ----------------------------------------------------
    # TEST 4 - INVALID BOOK
    # ----------------------------------------------------
    print("\n[TEST 4: Invalid Book]")
    r4_1 = rule_based_fallback_response("Do you have Quantum Computing?", None, None)
    print("User: Do you have Quantum Computing?")
    print(f"Bot: {r4_1['text']}")
    assert "Sorry, I couldn't find that book in the library catalogue." in r4_1["text"]
    print("Test 4 PASSED!")

    # ----------------------------------------------------
    # TEST 5 - CANCELLATION
    # ----------------------------------------------------
    print("\n[TEST 5: Cancellation]")
    r5_1 = rule_based_fallback_response("I want Python Programming.", None, None)
    print("User: I want Python Programming.")
    print(f"Bot: {r5_1['text']}")
    pending_book5 = r5_1.get("pending_book")
    assert pending_book5 is not None

    r5_2 = rule_based_fallback_response("Cancel it.", None, pending_book5)
    print("User: Cancel it.")
    print(f"Bot: {r5_2['text']}")
    assert "Your request has been cancelled." in r5_2["text"]
    print("Test 5 PASSED!")

    print("\n=== ALL 5 TEST SUITES PASSED PERFECTLY! ===")

if __name__ == "__main__":
    run_tests()
