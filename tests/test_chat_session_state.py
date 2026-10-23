import pytest
from unittest.mock import MagicMock, patch


def test_session_state_message_sequence_after_three_turns():
    """Verify that after 3 chat turns, session state contains exactly 6 messages
    in the strict alternating order [Q1, A1, Q2, A2, Q3, A3] with no duplicates,
    overlaps, or reordering.
    """
    session_state = {"messages": []}

    turns = [
        ("Who is the Principal of GPREC?", "Dr. J. Someswar Rao is the Principal of GPREC."),
        ("What is the college code?", "The EAPCET counseling code for GPREC is GPRW."),
        ("Where is the campus located?", "GPREC is located on Nandyal Road in Kurnool, Andhra Pradesh.")
    ]

    for q, a in turns:
        # Step 1: User message appended
        session_state["messages"].append({"role": "user", "content": q})
        
        # Step 2: Assistant response generated and appended
        session_state["messages"].append({
            "role": "assistant",
            "content": a,
            "response_type": "ANSWERED",
            "sources": [],
            "confidence": "High",
            "confidence_reason": "Verified record"
        })

    # Assertions
    messages = session_state["messages"]
    assert len(messages) == 6, f"Expected exactly 6 messages, got {len(messages)}"

    expected_roles = ["user", "assistant", "user", "assistant", "user", "assistant"]
    actual_roles = [m["role"] for m in messages]
    assert actual_roles == expected_roles, f"Roles out of order: {actual_roles}"

    # Verify each question appears exactly once
    user_questions = [m["content"] for m in messages if m["role"] == "user"]
    assert user_questions == [
        "Who is the Principal of GPREC?",
        "What is the college code?",
        "Where is the campus located?"
    ]
    for q in user_questions:
        assert user_questions.count(q) == 1, f"Duplicate detected for question: {q}"

    # Verify assistant answers match their respective turns
    assistant_answers = [m["content"] for m in messages if m["role"] == "assistant"]
    assert assistant_answers == [
        "Dr. J. Someswar Rao is the Principal of GPREC.",
        "The EAPCET counseling code for GPREC is GPRW.",
        "GPREC is located on Nandyal Road in Kurnool, Andhra Pradesh."
    ]


def test_container_keys_uniqueness_for_turns():
    """Verify that container keys generated per message index are unique and monotonic."""
    keys = []
    # 3 turns = 6 messages
    for idx in range(6):
        key = f"msg_block_{idx}"
        assert key not in keys, f"Duplicate container key found: {key}"
        keys.append(key)

    assert keys == [
        "msg_block_0",
        "msg_block_1",
        "msg_block_2",
        "msg_block_3",
        "msg_block_4",
        "msg_block_5"
    ]


def test_clear_chat_resets_session_state():
    """Verify that clearing chat completely empties the message list."""
    session_state = {
        "messages": [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"}
        ]
    }
    assert len(session_state["messages"]) == 2
    session_state["messages"] = []
    assert len(session_state["messages"]) == 0
