import os
import yaml

ETC_DIR_PATH = os.path.dirname(os.path.abspath(__file__))
CONFIG_DICT = yaml.load(open(os.path.join(ETC_DIR_PATH, 'config.yaml'), 'r'))
