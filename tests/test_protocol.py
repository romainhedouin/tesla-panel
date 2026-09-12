import socket
import struct

import pytest

from protocol import (
    HEADER_FORMAT,
    STATUS_ERROR,
    STATUS_OK,
    handle_one_command,
    parse_ppm,
    recv_exact,
)


@pytest.fixture
def sockpair():
    a, b = socket.socketpair()
    yield a, b
    a.close()
    b.close()


def send_command(sock, command_type, payload=b""):
    sock.sendall(struct.pack(HEADER_FORMAT, command_type, len(payload)) + payload)


def test_recv_exact_reassembles_chunked_writes(sockpair):
    a, b = sockpair
    a.sendall(b"ab")
    a.sendall(b"cde")
    assert recv_exact(b, 5) == b"abcde"


def test_recv_exact_returns_none_on_early_close(sockpair):
    a, b = sockpair
    a.sendall(b"ab")
    a.close()
    assert recv_exact(b, 5) is None


def test_parse_ppm_basic():
    header = b"P6\n2 1\n255\n"
    pixels = bytes([255, 0, 0, 0, 255, 0])  # red pixel, green pixel
    width, height, data = parse_ppm(header + pixels)
    assert (width, height) == (2, 1)
    assert data == pixels


def test_parse_ppm_skips_comment_line():
    # GIMP-exported PPMs add a '#'-prefixed comment line in the header,
    # which must be skipped like whitespace rather than parsed as a number.
    header = b"P6\n# CREATOR: GIMP\n2 1\n255\n"
    pixels = bytes([1, 2, 3, 4, 5, 6])
    width, height, data = parse_ppm(header + pixels)
    assert (width, height) == (2, 1)
    assert data == pixels


def test_handle_one_command_dispatches_and_replies_ok(sockpair):
    a, b = sockpair
    received = []
    handlers = {7: lambda payload: received.append(payload)}
    send_command(a, 7, b"hello")

    assert handle_one_command(b, handlers, logger=lambda msg: None) is True
    assert received == [b"hello"]
    assert a.recv(1) == STATUS_OK


def test_handle_one_command_unknown_command_replies_error(sockpair):
    a, b = sockpair
    send_command(a, 99)

    assert handle_one_command(b, handlers={}, logger=lambda msg: None) is True
    assert a.recv(1) == STATUS_ERROR


def test_handle_one_command_handler_exception_replies_error(sockpair):
    a, b = sockpair

    def boom(payload):
        raise ValueError("nope")

    send_command(a, 1, b"x")

    assert handle_one_command(b, {1: boom}, logger=lambda msg: None) is True
    assert a.recv(1) == STATUS_ERROR


def test_handle_one_command_returns_false_on_disconnect(sockpair):
    a, b = sockpair
    a.close()
    assert handle_one_command(b, handlers={}, logger=lambda msg: None) is False
