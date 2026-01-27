from ui.session_store import SessionStore
import os

def test_mobaxterm_import():
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<MobaXtermSessions>
  <Bookmarks ImgNum="42">
    <Session name="10.176.133.19 (gateway)">
      <Protocol>SSH</Protocol>
      <Host>10.176.133.19</Host>
      <Port>22</Port>
      <Username>gateway</Username>
    </Session>
  </Bookmarks>
  <Bookmarks_1 SubRep="PuTTY sessions" ImgNum="208">
    <Session name="bunya">
      <Protocol>SSH</Protocol>
      <Host>bunya.rcc.uq.edu.au</Host>
      <Port>22</Port>
      <Username/>
    </Session>
  </Bookmarks_1>
</MobaXtermSessions>"""
    
    with open("test_moba.xml", "w") as f:
        f.write(xml_content)

    store = SessionStore("test_sessions_moba.json")
    store.sessions = []
    store.save()
    
    print("Importing...")
    count = store.import_from_xml("test_moba.xml")
    print(f"Import count: {count}")
    
    sessions = store.get_sessions()
    for s in sessions:
        print(s)

    # Clean up
    if os.path.exists("test_moba.xml"):
        os.remove("test_moba.xml")
    if os.path.exists("test_sessions_moba.json"):
        os.remove("test_sessions_moba.json")

if __name__ == "__main__":
    test_mobaxterm_import()
