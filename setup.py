from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="bookshelf",
    version="0.0.5",
    author="trez",
    author_email="tobias.vehkajarvi@gmail.com",
    description="Collection tracker",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/trez/bookshelf",
    project_urls={
        "Bug Tracker": "https://github.com/trez/bookshelf/issues",
    },
    classifiers=["Programming Language :: Python :: 3"],
    install_requires=[
        "pyclicommander @ git+https://github.com/trez/pyclicommander",
        "pycolors",
        "GitPython"
    ],
    entry_points={
        "console_scripts": [
            "bookshelf=src.__main__:main",
        ]
    },
    packages=["src"],
    python_requires=">=3.8.5",
)
