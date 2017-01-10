import sys, os
sys.path.append("..")
sys.path.append("../scripts")

import make_rooms
make_rooms.convert("_preview.tga", "../rooms.py")

import bpalace
bpalace.main()
