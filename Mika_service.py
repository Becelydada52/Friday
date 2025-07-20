import sys
import os
from Friday import FridayAssistant

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--install":
        pass
    else:
        assistant = FridayAssistant()
        assistant.speak("Пятница активирована")
        assistant.listen_background()
    
if __name__ == '__main__':
    main()