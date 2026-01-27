import pyte

def test_pyte():
    screen = pyte.Screen(80, 24)
    stream = pyte.Stream(screen)
    
    # Simulate some ANSI sequences
    data = "Hello \033[31mWorld\033[0m\r\nLine 2"
    stream.feed(data)
    
    print("Screen display:")
    for line in screen.display:
        print(f"'{line}'")

if __name__ == "__main__":
    try:
        test_pyte()
        print("\npyte is installed and working.")
    except ImportError:
        print("\npyte is NOT installed.")
