Use Terraform files in LocalStack init hooks
============================================

LocalStack Extension for using Terraform files in [init hooks](https://docs.localstack.cloud/references/init-hooks/).

> [!WARNING]
> This extension is experimental and subject to change.

> [!NOTE]
> The extension is designed for simple self-contained terraform files, not complex projects or modules.
> If you have larger projects, then we recommend running them from the host.

## Usage

* Start localstack with `EXTENSION_AUTO_INSTALL="localstack-extension-terraform-init"`
* Optionally specify `TERRAFORM_VERSION=1.13.2` (currently defaults to 1.5.7)
* Mount a `main.tf` file into `/etc/localstack/init/ready.d`

When LocalStack starts up, it will install the extension, which in turn install `terraform` and `tflocal` into the container.
If one of the init stage directories contain a `main.tf`, the extension will run `tflocal init` and `tflocal apply` on that directory.

> [!NOTE]
> Terraform state files will be created in your host directory if you mounted an entire folder into `/etc/localstack/init/ready.d`.
> These files are created from within the container using the container user, so you may need `sudo` to remove the files from your host.
> If you only mount the `main.tf` file, not an entire directory, localstack will have to download the AWS terraform provider every time during `tflocal init`.
> 
### Example

Example `main.tf`:
```hcl
resource "aws_s3_bucket" "example" {
  bucket = "my-tf-test-bucket"

  tags = {
    Name        = "My bucket"
    Environment = "Dev"
  }
}
```

Start LocalStack Pro with mounted `main.tf`:

```console
localstack start \
  -e EXTENSION_AUTO_INSTALL="localstack-extension-terraform-init" \
  -v ./main.tf:/etc/localstack/init/ready.d/main.tf
```

Or, if you use a docker-compose file:

```yaml
services:
  localstack:
    container_name: "localstack-main"
    image: localstack/localstack-pro  # required for Pro
    ports:
      - "127.0.0.1:4566:4566"            # LocalStack Gateway
    environment:
      # Activate LocalStack Pro: https://docs.localstack.cloud/getting-started/auth-token/
      - LOCALSTACK_AUTH_TOKEN=${LOCALSTACK_AUTH_TOKEN:?}
      - EXTENSION_AUTO_LOAD=localstack-extension-terraform-init"
    volumes:
      # you could also place your main.tf in `./ready.d` and set "./ready.d:/etc/localstack/init/ready.d"
      - "./main.tf:/etc/localstack/init/ready.d/main.tf"
      - "./volume:/var/lib/localstack"
      - "/var/run/docker.sock:/var/run/docker.sock"
```

In a new terminal window, you can wait for localstack to complete and then print the created s3 buckets.

```console
localstack wait && awslocal s3 ls
```

The logs should show something like:

```
2024-06-26T20:36:19.946  INFO --- [ady_monitor)] l.extension                : Applying terraform project from file /etc/localstack/init/ready.d/main.tf
2024-06-26T20:36:19.946 DEBUG --- [ady_monitor)] localstack.utils.run       : Executing command: ['tflocal', '-chdir=/etc/localstack/init/ready.d', 'init', '-input=false']
2024-06-26T20:36:26.864 DEBUG --- [ady_monitor)] localstack.utils.run       : Executing command: ['tflocal', '-chdir=/etc/localstack/init/ready.d', 'apply', '-auto-approve']
```

## Install local development version

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

## Install from GitHub repository

To distribute your extension, simply upload it to your github account. Your extension can then be installed via:

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extensions/#egg=localstack-extension-terraform-init&subdirectory=terraform-init"
```
