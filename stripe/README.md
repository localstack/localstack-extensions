Stripe LocalStack extensions
============================

A LocalStack extension that provides a mocked version of [Stripe](https://stripe.com) as a service.

## Installing


```bash
localstack extensions install localstack-extension-stripe
```

## Using

Once installed, you can query stripe either through `localhost:4566/stripe` or
`stripe.localhost.localstack.cloud:4566`.

```bash
curl stripe.localhost.localstack.cloud:4566/v1/customers \
	-u sk_test_12345: \
	-d description="Customer data for Alice"
````

## Licensing

* [localstripe](https://github.com/adrienverge/localstripe) is licensed under
  the GNU General Public License version 3.
* localstack-extension-stripe (this project) does not modify localstripe in
  any way
