#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.api_stack import KeycloakSampleApiStack

app = cdk.App()

KeycloakSampleApiStack(
    app,
    "KeycloakSampleApiStack",
    env=cdk.Environment(account="000000000000", region="us-east-1"),
)

app.synth()
