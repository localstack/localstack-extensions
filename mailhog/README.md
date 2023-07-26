LocalStack Mailhog Extension
===============================

Web and API based STMP testing directly in LocalStack using [MailHog](https://github.com/mailhog/MailHog).

If the standard configuration is used, LocalStack will serve the UI through http://mailhog.localhost.localstack.cloud:4566 or http://localhost:4566/mailhog/.
It will also configure `SMTP_HOST` automatically, which points all services using SMTP, including [SES](https://docs.localstack.cloud/user-guide/aws/ses/), to MailHog.

## Install from GitHub repository

Install the extension directly from the GitHub repository by running:

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extensions/#egg=localstack-mailhog-extension&subdirectory=mailhog"
```

After starting LocalStack, you should see these lines in the log:

```
2023-07-26T10:00:08.072  INFO --- [  MainThread] mailhog.extension          : serving mailhog extension on host: http://mailhog.localhost.localstack.cloud:4566
2023-07-26T10:00:08.072  INFO --- [  MainThread] mailhog.extension          : serving mailhog extension on path: http://localhost:4566/mailhog/
```

## Integration with LocalStack

When using this extension, LocalStack is automatically configured to use the MailHog SMTP server when sending emails.
For example, if you run the following SES commands:

```console
$ awslocal ses verify-email-identity --email-address user1@yourdomain.com
```
```
$ awslocal ses send-email \                                              
    --from user1@yourdomain.com \
    --message 'Body={Text={Data="Hello from LocalStack to MailHog"}},Subject={Data=Test Email}' \
    --destination 'ToAddresses=recipient1@example.com'
{
    "MessageId": "ktrmpmhohorxfbjd-dzebwdgu-odnm-wyvz-pezg-mijejwlvaxtr-psfctr"
}
```

You should see the mail arriving in MailHog.
![Screenshot at 2023-07-26 12-08-54](https://github.com/localstack/localstack-extensions/assets/3996682/7b0bb4e5-2fc1-4f6b-a90e-0ed31663b411)


## Configure

You can use the [MailHog configuration environment variables](https://github.com/mailhog/MailHog/blob/master/docs/CONFIG.md) to configure the extension.
When using the CLI, you can add them by using `DOCKER_FLAGS='-e MH_<var>=<val> -e ...'`.
If you are using docker compose, simply add them as environment variables to the container.

## Development

### Install local development version

To install the extension into localstack in developer mode, you will need Python 3.10, and create a virtual environment in the extensions project.

In the newly generated project, simply run

```bash
make install
```

Then, to enable the extension for LocalStack, run

```bash
localstack extensions dev enable .
```

You can then start LocalStack with `EXTENSION_DEV_MODE=1` to load all enabled extensions:

```bash
EXTENSION_DEV_MODE=1 localstack start
```

## Known Limitations

The MailHog UI supports real-time updates through websockets, which is currently not supported through the default `:4566` port.
When you open the UI, you may see this error in the LocalStack logs, which is safe to ignore.
The UI won't update automatically though, so you need to click the refresh button.
```
2023-07-25T18:23:12.465 ERROR --- [-functhread3] hypercorn.error            : Error in ASGI Framework
Traceback (most recent call last):
File "/opt/code/localstack/.venv/lib/python3.10/site-packages/hypercorn/asyncio/task_group.py", line 23, in _handle
await app(scope, receive, send, sync_spawn, call_soon)
File "/opt/code/localstack/.venv/lib/python3.10/site-packages/hypercorn/app_wrappers.py", line 33, in __call__
await self.app(scope, receive, send)
File "/opt/code/localstack/.venv/lib/python3.10/site-packages/localstack/aws/serving/asgi.py", line 67, in __call__
return await self.wsgi(scope, receive, send)
File "/opt/code/localstack/.venv/lib/python3.10/site-packages/localstack/http/asgi.py", line 324, in __call__
raise NotImplementedError("Unhandled protocol %s" % scope["type"])
NotImplementedError: Unhandled protocol websocket
2023-07-25T18:23:12.465 ERROR --- [-functhread3] hypercorn.error            : Error in ASGI Framework
Traceback (most recent call last):
File "/opt/code/localstack/.venv/lib/python3.10/site-packages/hypercorn/asyncio/task_group.py", line 23, in _handle
await app(scope, receive, send, sync_spawn, call_soon)
File "/opt/code/localstack/.venv/lib/python3.10/site-packages/hypercorn/app_wrappers.py", line 33, in __call__
await self.app(scope, receive, send)
File "/opt/code/localstack/.venv/lib/python3.10/site-packages/localstack/aws/serving/asgi.py", line 67, in __call__
return await self.wsgi(scope, receive, send)
File "/opt/code/localstack/.venv/lib/python3.10/site-packages/localstack/http/asgi.py", line 324, in __call__
raise NotImplementedError("Unhandled protocol %s" % scope["type"])
```

## Licensing

* No modifications were made to MailHog, which is licensed under MIT license: https://github.com/mailhog/MailHog/blob/master/LICENSE.md
* The extension code is licensed under Apache License Version 2.0
