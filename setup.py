from setuptools import setup

setup(name='iris',
      version='0.1',
      description='An automated image stitching tool',
      author='Umesh Padia',
      author_email='upadia@caltech.edu',
      packages=['iris'],
      install_requires=['opencv-python', 'numpy'],
      entry_points={'console_scripts': ['iris = iris.iris:main']})
