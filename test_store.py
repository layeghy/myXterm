from ui.session_store import SessionStore
import os

def test_session_store():
    # Clean up
    if os.path.exists("sessions.json"):
        os.remove("sessions.json")

    store = SessionStore()
    assert len(store.get_sessions()) == 0

    data = {
        "host": "localhost",
        "port": 22,
        "username": "test",
        "password": "password"
    }
    store.add_session(data)

    # Reload
    store2 = SessionStore()
    sessions = store2.get_sessions()
    assert len(sessions) == 1
    assert sessions[0]["host"] == "localhost"
    
    print("SessionStore tests passed!")

if __name__ == "__main__":
    test_session_store()
