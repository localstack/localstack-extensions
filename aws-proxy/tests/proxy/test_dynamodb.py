import boto3
import pytest
from botocore.exceptions import ClientError
from localstack.aws.connect import connect_to
from localstack.utils.aws.resources import create_dynamodb_table
from localstack.utils.strings import short_uid

from aws_proxy.shared.models import ProxyConfig


class TestDynamoDBRequests:
    region_name = "us-east-1"

    @pytest.fixture(scope="class")
    def dynamodb_client_aws(self):
        return boto3.client("dynamodb", region_name=self.region_name)

    @pytest.fixture
    def create_dynamodb_table_aws(self, dynamodb_client_aws):
        tables = []

        def factory(**kwargs):
            kwargs["client"] = dynamodb_client_aws
            if "table_name" not in kwargs:
                kwargs["table_name"] = f"test-table-{short_uid()}"
            if "partition_key" not in kwargs:
                kwargs["partition_key"] = "id"

            tables.append(kwargs["table_name"])

            return create_dynamodb_table(**kwargs)

        yield factory

        # cleanup
        for table in tables:
            try:
                dynamodb_client_aws.delete_table(TableName=table)
            except Exception as e:
                print(f"error cleaning up table {table}: {e}", table, e)

    def test_dynamodb_requests_read_only(
        self, start_aws_proxy, create_dynamodb_table_aws, dynamodb_client_aws
    ):
        # create clients
        dynamodb_client = connect_to(region_name=self.region_name).dynamodb

        # start proxy - only forwarding requests for read operations
        config = ProxyConfig(
            services={"dynamodb": {"resources": ".*", "read_only": True}}
        )
        start_aws_proxy(config)

        # create table in AWS
        table_name = f"test-table-{short_uid()}"
        create_dynamodb_table_aws(table_name=table_name)
        tables_aws = dynamodb_client_aws.list_tables()["TableNames"]
        assert table_name in tables_aws

        # assert that local call for this table is proxied
        tables_local = dynamodb_client.list_tables()["TableNames"]
        assert table_name in tables_local

        item = {"id": {"S": "123"}, "value": {"S": "foobar"}}
        # put item via AWS client
        dynamodb_client_aws.put_item(TableName=table_name, Item=item)

        # get item via AWS client
        result = dynamodb_client_aws.get_item(
            TableName=table_name, Key={"id": {"S": "123"}}
        )
        assert result["Item"] == item

        # get item via local client
        result = dynamodb_client.get_item(
            TableName=table_name, Key={"id": {"S": "123"}}
        )
        assert result["Item"] == item

        # assert that scan operation is working
        result = dynamodb_client.scan(TableName=table_name)
        assert len(result["Items"]) == 1

        # assert that write operation is NOT working - it's sent to localstack, which cannot find the table
        item3 = {"id": {"S": "789"}, "value": {"S": "foobar3"}}
        with pytest.raises(ClientError) as exc:
            dynamodb_client.put_item(TableName=table_name, Item=item3)

        assert exc.match("ResourceNotFoundException")
