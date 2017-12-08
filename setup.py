from setuptools import setup

setup(
    name="peregrine",
    description="The PEREGRINE API.",
    license="Apache",
    packages=[
        "peregrine",
        "peregrine.utils",
        "peregrine.services",
        "peregrine.repositories",
        "peregrine.models",
        "peregrine.esutils",
        "peregrine.download",
    ],
    entry_points={
        'console_scripts': ['peregrine=peregrine.api:main']
    },
)
