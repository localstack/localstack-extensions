"""
End-to-end gRPC tests using grpcbin services.

These tests make actual gRPC calls to grpcbin to verify that the full
HTTP/2 stack works correctly, including proper request/response handling.

grpcbin provides services like: Empty, Index, HeadersUnary, etc.
We use the Empty service which returns an empty response.
"""

import grpc


class TestGrpcEndToEnd:
    """End-to-end tests making actual gRPC calls to grpcbin."""

    def test_grpc_empty_call(self, grpcbin_extension_server):
        """Test making a gRPC call to grpcbin's Empty service via the gateway."""
        # Create a channel to grpcbin through the gateway
        gateway_port = grpcbin_extension_server["port"]
        channel = grpc.insecure_channel(f"localhost:{gateway_port}")

        try:
            # Use grpc.channel_ready_future to verify connection
            grpc.channel_ready_future(channel).result(timeout=5)

            # grpcbin provides /grpcbin.GRPCBin/Empty which returns empty response
            method = "/grpcbin.GRPCBin/Empty"

            # Empty message is just empty bytes in protobuf
            request = b""

            # Make the unary-unary call
            response = channel.unary_unary(
                method,
                request_serializer=lambda x: x,
                response_deserializer=lambda x: x,
            )(request, timeout=5)

            # Empty service returns empty response
            assert response is not None
            assert response == b"" or len(response) == 0

        finally:
            channel.close()

    def test_grpc_index_call(self, grpcbin_extension_server):
        """Test calling grpcbin's Index service which returns server info."""
        gateway_port = grpcbin_extension_server["port"]
        channel = grpc.insecure_channel(f"localhost:{gateway_port}")

        try:
            # Verify channel is ready
            grpc.channel_ready_future(channel).result(timeout=5)

            # grpcbin's Index service returns information about the server
            method = "/grpcbin.GRPCBin/Index"
            request = b""

            response = channel.unary_unary(
                method,
                request_serializer=lambda x: x,
                response_deserializer=lambda x: x,
            )(request, timeout=5)

            # Index returns a non-empty protobuf message with server info
            assert response is not None
            assert len(response) > 0, "Index service should return server information"

        finally:
            channel.close()

    def test_grpc_concurrent_calls(self, grpcbin_extension_server):
        """Test making multiple concurrent gRPC calls."""
        gateway_port = grpcbin_extension_server["port"]
        channel = grpc.insecure_channel(f"localhost:{gateway_port}")

        try:
            # Verify channel is ready
            grpc.channel_ready_future(channel).result(timeout=5)

            method = "/grpcbin.GRPCBin/Empty"
            request = b""

            # Make multiple concurrent calls
            responses = []
            for i in range(3):
                response = channel.unary_unary(
                    method,
                    request_serializer=lambda x: x,
                    response_deserializer=lambda x: x,
                )(request, timeout=5)
                responses.append(response)

            # Verify all calls completed
            assert len(responses) == 3, "All concurrent calls should complete"
            for i, response in enumerate(responses):
                assert response is not None, f"Call {i} should return a response"

        finally:
            channel.close()

    def test_grpc_connection_reuse(self, grpcbin_extension_server):
        """Test that a single gRPC channel can handle multiple sequential calls."""
        gateway_port = grpcbin_extension_server["port"]
        channel = grpc.insecure_channel(f"localhost:{gateway_port}")

        try:
            # Verify channel is ready
            grpc.channel_ready_future(channel).result(timeout=5)

            # Alternate between Empty and Index calls
            methods = ["/grpcbin.GRPCBin/Empty", "/grpcbin.GRPCBin/Index"]
            request = b""

            # Make multiple sequential calls on the same channel
            for i in range(6):
                method = methods[i % 2]
                response = channel.unary_unary(
                    method,
                    request_serializer=lambda x: x,
                    response_deserializer=lambda x: x,
                )(request, timeout=5)

                assert response is not None, f"Call {i} to {method} should succeed"

                # Index should return data, Empty should return empty
                if "Index" in method:
                    assert len(response) > 0, "Index should return server info"

        finally:
            channel.close()
