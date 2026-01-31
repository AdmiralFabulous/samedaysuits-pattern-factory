from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="samedaysuits",
    version="6.4.3",
    author="SameDaySuits",
    author_email="support@samedaysuits.com",
    description="Automated garment manufacturing pipeline",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/samedaysuits/samedaysuits-pattern-factory",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Manufacturing",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "scanning": [
            "opencv-python>=4.8.0",
            "mediapipe>=0.10.0",
            "opencv-contrib-python>=4.8.0",  # For ArUco markers
        ],
        "patterns": [
            "ezdxf>=1.0.0",  # For DXF generation
        ],
        "ai": [
            "transformers>=4.30.0",  # For SAM 3D Body
            "torch>=2.0.0",
            "smplx>=0.1.0",  # For SMPL body model
        ],
        "all": [
            # Combined scanning + patterns + ai
            "opencv-python>=4.8.0",
            "mediapipe>=0.10.0",
            "opencv-contrib-python>=4.8.0",
            "ezdxf>=1.0.0",
            "transformers>=4.30.0",
            "torch>=2.0.0",
            "smplx>=0.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "sds=samedaysuits.cli:main",
            "samedaysuits=samedaysuits.cli:main",
        ],
    },
)
