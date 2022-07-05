#!/usr/bin/env python
from setuptools import setup

entry_points = {
    "localstack.extensions": [
        "localstripe=localstack_stripe.extension:LocalstripeExtension"
    ],
}

setup(entry_points=entry_points)
