from PyInstaller.utils.hooks import collect_all
import pprint

print("Collecting 'winpty'...")
try:
    ret = collect_all('winpty')
    print("Datas:")
    pprint.pprint(ret[0])
    print("\nBinaries:")
    pprint.pprint(ret[1])
    print("\nHidden Imports:")
    pprint.pprint(ret[2])
except Exception as e:
    print(f"Error: {e}")

print("\nCollecting 'pywinpty' (just in case)...")
try:
    ret = collect_all('pywinpty')
    print("Datas:")
    pprint.pprint(ret[0])
    print("\nBinaries:")
    pprint.pprint(ret[1])
    print("\nHidden Imports:")
    pprint.pprint(ret[2])
except Exception as e:
    print(f"Error: {e}")
