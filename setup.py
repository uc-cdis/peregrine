from setuptools import setup

setup(
    name="peregrine",
    description="The PEREGRINE API.",
    license="Apache",
    packages=[
        "peregrine",
        "peregrine.auth",
        "peregrine.blueprints",
        "peregrine.utils",
        "peregrine.resources",
        "peregrine.resources.submission",
        "peregrine.resources.submission.graphql",
    ],
    entry_points={
        'console_scripts': ['peregrine=peregrine.api:main']
    },
)
