import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from google.protobuf import json_format
from grpc import RpcError

from jina.parsers import set_pea_parser
from jina.peapods.grpc import Grpclet
from jina.proto import jina_pb2
from jina.types.message.common import ControlMessage


@pytest.mark.slow
@pytest.mark.asyncio
async def test_send_receive():
    receive_cb = AsyncMock()
    args = set_pea_parser().parse_args([])
    grpclet = Grpclet(args=args, message_callback=receive_cb)
    asyncio.get_event_loop().create_task(grpclet.start())

    receive_cb.assert_not_called()

    await grpclet.send_message(_create_msg(args))
    await asyncio.sleep(0.1)
    receive_cb.assert_called()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_send_non_blocking():
    receive_cb = AsyncMock()

    def blocking_cb(msg):
        receive_cb()
        time.sleep(1.0)
        return msg

    args = set_pea_parser().parse_args([])
    grpclet = Grpclet(args=args, message_callback=blocking_cb)
    asyncio.get_event_loop().create_task(grpclet.start())

    receive_cb.assert_not_called()

    await grpclet.send_message(_create_msg(args))
    await asyncio.sleep(0.1)
    assert receive_cb.call_count == 1
    await grpclet.send_message(_create_msg(args))
    await asyncio.sleep(0.1)
    assert receive_cb.call_count == 2


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_send_static_ctrl_msg():
    receive_cb = AsyncMock()
    args = set_pea_parser().parse_args([])
    grpclet = Grpclet(args=args, message_callback=receive_cb)
    asyncio.get_event_loop().create_task(grpclet.start())

    receive_cb.assert_not_called()

    while True:
        try:

            def send_status():
                return Grpclet.send_ctrl_msg(
                    pod_address=f'{args.host}:{args.port_in}', command='STATUS'
                )

            await asyncio.get_event_loop().run_in_executor(None, send_status)
            break
        except RpcError:
            await asyncio.sleep(0.1)

    receive_cb.assert_called()


def _create_msg(args):
    msg = ControlMessage('STATUS')
    routing_pb = jina_pb2.RoutingTableProto()
    routing_table = {
        'active_pod': 'pod1',
        'pods': {
            'pod1': {
                'host': '0.0.0.0',
                'port': args.port_in,
                'expected_parts': 1,
                'out_edges': [{'pod': 'pod2'}],
            },
            'pod2': {
                'host': '0.0.0.0',
                'port': args.port_in,
                'expected_parts': 1,
                'out_edges': [],
            },
        },
    }
    json_format.ParseDict(routing_table, routing_pb)
    msg.envelope.routing_table.CopyFrom(routing_pb)
    return msg