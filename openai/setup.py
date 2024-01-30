#!/usr/bin/env python
from setuptools import setup

entry_points = {
    "localstack.extensions": [
        "localstack_openai=localstack_openai.extension:LocalstackOpenAIExtension"
    ],
}

setup(entry_points=entry_points)