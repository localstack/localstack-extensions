# LocalStack OpenAI Extension

![GitHub license](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![Python version](https://img.shields.io/badge/python-3.11%2B-blue)
[![Build Status](https://travis-ci.com/yourusername/localstack-openai-mock.svg?branch=master)](https://travis-ci.com/yourusername/localstack-openai-mock)

This is a LocalStack extension that allows you to mock the OpenAI API for testing and development purposes. It provides a convenient way to interact with a mock OpenAI service locally using LocalStack.

## Installation

You can install this extension directly using the LocalStack extension manager:

```bash
localstack extensions install localstack-extension-openai
```

## Using

Once installed, you can access the OpenAI Mock API through `localhost:4510/v1`.

### Example

```python

import openai
openai.organization = "org-test"
openai.api_key = "test"
openai.api_base = "http://localhost:4510/v1"

completion = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
print(completion.choices)
```

## Coverage
- [x] Chat completion
- [x] Engines Listing
- [x] Transcribe
- [x] Translate
- [x] Generate Image URL
- [ ] Generate Image Base64
- [ ] Embeddings
- [ ] Fine Tuning
- [ ] Files
- [ ] Moderations



## Authors
**Cristopher Pinzon** cristopher.pinzon@localstack.cloud

### Thank you for using the LocalStack OpenAI Extension!