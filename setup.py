#!/usr/bin/env python3

from setuptools import setup

setup(
  name='allrgb',
  version='1.0.0',
  description="Generates an image with every RGB color exactly once",
  author="Dan Kaplun",
  author_email='min@dvir.us',
  url='http://github.com/dbkaplun/allrgb',
  scripts=['allrgb.py'],
  install_requires=['numpy', 'scikit-image', 'imageio']
)
