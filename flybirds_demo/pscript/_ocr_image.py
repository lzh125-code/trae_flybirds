# -*- coding: utf-8 -*-
"""临时：对单张图片做 OCR，用于读取用户提供的截图内容。"""
import sys

import numpy as np
from PIL import Image

import easyocr

path = sys.argv[1]
image = np.array(Image.open(path).convert("RGB"))[:, :, ::-1]
reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
for box, text, score in reader.readtext(image, paragraph=False):
    if text and text.strip():
        y = int(sum(point[1] for point in box) / 4)
        print("%4d  %.2f  %s" % (y, score, text.strip()))
