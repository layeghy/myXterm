from ui.session_store import SessionStore
import os

def test_xml_import_case_insensitive():
    # Create a dummy XML file with mixed case
    xml_content = """<?xml version='1.0' encoding='utf-8'?>
<sessions>
    <session>
        <Name>Case Insensitive Session</Name>
        <HOST>case.com</HOST>
        <Port>2222</Port>
        <UserName>user</UserName>
        <Password>pass</Password>
    </session>
</sessions>"""
    
    with open("test_import_case.xml", "w") as f:
        f.write(xml_content)

    store = SessionStore("test_sessions_case.json")
    # Clear existing
    store.sessions = []
    store.save()
    
    print("Importing...")
    count = store.import_from_xml("test_import_case.xml")
    print(f"Import count: {count}")
    
    sessions = store.get_sessions()
    print(f"Sessions found: {len(sessions)}")
    for s in sessions:
        print(s)

    # Clean up
    if os.path.exists("test_import_case.xml"):
        os.remove("test_import_case.xml")
    if os.path.exists("test_sessions_case.json"):
        os.remove("test_sessions_case.json")

if __name__ == "__main__":
    test_xml_import_case_insensitive()
