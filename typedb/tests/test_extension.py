import requests
from localstack.utils.strings import short_uid
from localstack_typedb.utils.h2_proxy import parse_http2_stream, get_headers_from_frames
from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType


def test_connect_to_db_via_http_api():
    host = "typedb.localhost.localstack.cloud:4566"

    # get auth token
    response = requests.post(
        f"http://{host}/v1/signin", json={"username": "admin", "password": "password"}
    )
    assert response.ok
    token = response.json()["token"]

    # create database
    db_name = f"db{short_uid()}"
    response = requests.post(
        f"http://{host}/v1/databases/{db_name}",
        json={},
        headers={"Authorization": f"bearer {token}"},
    )
    assert response.ok

    # list databases
    response = requests.get(
        f"http://{host}/v1/databases", headers={"Authorization": f"bearer {token}"}
    )
    assert response.ok
    databases = [db["name"] for db in response.json()["databases"]]
    assert db_name in databases

    # clean up
    response = requests.delete(
        f"http://{host}/v1/databases/{db_name}",
        headers={"Authorization": f"bearer {token}"},
    )
    assert response.ok


def test_connect_to_db_via_grpc_endpoint():
    db_name = "access-management-db"
    server_host = "typedb.localhost.localstack.cloud:4566"

    driver_cfg = TypeDB.driver(
        server_host,
        Credentials("admin", "password"),
        DriverOptions(is_tls_enabled=False),
    )
    with driver_cfg as driver:
        if driver.databases.contains(db_name):
            driver.databases.get(db_name).delete()
        driver.databases.create(db_name)

        with driver.transaction(db_name, TransactionType.SCHEMA) as tx:
            tx.query("define entity person;").resolve()
            tx.query("define attribute name, value string; person owns name;").resolve()
            tx.commit()

        with driver.transaction(db_name, TransactionType.WRITE) as tx:
            tx.query("insert $p isa person, has name 'Alice';").resolve()
            tx.query("insert $p isa person, has name 'Bob';").resolve()
            tx.commit()
        with driver.transaction(db_name, TransactionType.READ) as tx:
            results = tx.query(
                'match $p isa person; fetch {"name": $p.name};'
            ).resolve()
            for json in results:
                print(json)


def test_parse_http2_frames():
    # note: the data below is a dump taken from a browser request made against the emulator
    data = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n\x00\x00\x18\x04\x00\x00\x00\x00\x00\x00\x01\x00\x01\x00\x00\x00\x02\x00\x00\x00\x00\x00\x04\x00\x02\x00\x00\x00\x05\x00\x00@\x00\x00\x00\x04\x08\x00\x00\x00\x00\x00\x00\xbf\x00\x01"
    data += b"\x00\x01V\x01%\x00\x00\x00\x03\x00\x00\x00\x00\x15C\x87\xd5\xaf~MZw\x7f\x05\x8eb*\x0eA\xd0\x84\x8c\x9dX\x9c\xa3\xa13\xffA\x96\xa0\xe4\x1d\x13\x9d\t^\x83\x90t!#'U\xc9A\xed\x92\xe3M\xb8\xe7\x87z\xbe\xd0\x7ff\xa2\x81\xb0\xda\xe0S\xfa\xd02\x1a\xa4\x9d\x13\xfd\xa9\x92\xa4\x96\x854\x0c\x8aj\xdc\xa7\xe2\x81\x02\xe1o\xedK;\xdc\x0bM.\x0f\xedLE'S\xb0 \x04\x00\x08\x02\xa6\x13XYO\xe5\x80\xb4\xd2\xe0S\x83\xf9c\xe7Q\x8b-Kp\xdd\xf4Z\xbe\xfb@\x05\xdbP\x92\x9b\xd9\xab\xfaRB\xcb@\xd2_\xa5#\xb3\xe9OhL\x9f@\x94\x19\x08T!b\x1e\xa4\xd8z\x16\xb0\xbd\xad*\x12\xb5%L\xe7\x93\x83\xc5\x83\x7f@\x95\x19\x08T!b\x1e\xa4\xd8z\x16\xb0\xbd\xad*\x12\xb4\xe5\x1c\x85\xb1\x1f\x89\x1d\xa9\x9c\xf6\x1b\xd8\xd2c\xd5s\x95\x9d)\xad\x17\x18`u\xd6\xbd\x07 \xe8BFN\xab\x92\x83\xdb#\x1f@\x85=\x86\x98\xd5\x7f\x94\x9d)\xad\x17\x18`u\xd6\xbd\x07 \xe8BFN\xab\x92\x83\xdb'@\x8aAH\xb4\xa5I'ZB\xa1?\x84-5\xa7\xd7@\x8aAH\xb4\xa5I'Z\x93\xc8_\x83!\xecG@\x8aAH\xb4\xa5I'Y\x06I\x7f\x86@\xe9*\xc82K@\x86\xae\xc3\x1e\xc3'\xd7\x83\xb6\x06\xbf@\x82I\x7f\x86M\x835\x05\xb1\x1f\x00\x00\x04\x08\x00\x00\x00\x00\x03\x00\xbe\x00\x00"

    frames = parse_http2_stream(data)
    assert frames
    headers = get_headers_from_frames(frames)
    assert headers
    assert headers[":scheme"] == "https"
    assert headers[":method"] == "OPTIONS"
    assert headers[":path"] == "/_localstack/health"
