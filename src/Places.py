import os

path = os.path.abspath(__file__)
SRC_FOLDER = os.path.dirname(path)
MAIN_FOLDER = os.path.dirname(SRC_FOLDER)
UI_FOLDER = os.path.join(MAIN_FOLDER, "ui")
ICONS_FOLDER = os.path.join(MAIN_FOLDER, "icons")
CSS_FOLDER = os.path.join(MAIN_FOLDER, "css")
