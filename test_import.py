from ui.session_store import SessionStore
import os

def test_xml_import():
    # Create a dummy XML file
    xml_content = """<?xml version='1.0' encoding='utf-8'?>
<Sessions>
    <Session>
        <name>Imported Session</name>
        <host>imported.com</host>
        <port>2222</port>
        <username>user</username>
        <password>pass</password>
    </Session>
</Sessions>"""
    
    with open("test_import.xml", "w") as f:
        f.write(xml_content)

    store = SessionStore("test_sessions.json")
    # Clear existing
    store.sessions = []
    store.save()
    
    print("Importing...")
    success = store.import_from_xml("test_import.xml")
    print(f"Import success: {success}")
    
    sessions = store.get_sessions()
    print(f"Sessions found: {len(sessions)}")
    for s in sessions:
        print(s)

    # Clean up
    if os.path.exists("test_import.xml"):
        os.remove("test_import.xml")
    if os.path.exists("test_sessions.json"):
        os.remove("test_sessions.json")

if __name__ == "__main__":
    test_xml_import()
