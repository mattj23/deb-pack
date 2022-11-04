import setuptools

with open("README.md", "r", encoding="utf-8") as handle:
    long_description = handle.read()

setuptools.setup(
    name="deb-pack",
    version="0.1.2",
    author="Matthew Jarvis",
    author_email="mattj23@gmail.com",
    description="Debian packaging tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mattj23/deb-pack",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
    install_requires=[
        "click>=8.1.3",
        "aptly-api-client>=0.2.4"
    ],
    entry_points={
        "console_scripts": [
            "pack=deb_pack.main:main",
        ]
    }
)