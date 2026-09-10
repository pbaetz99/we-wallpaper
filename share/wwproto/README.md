# waywallen control protocol

`control.proto` and `filter.proto` are copied from
[waywallen/waywallen](https://github.com/waywallen/waywallen) (MIT license,
`proto/`), version 0.3.9. `*_pb2.py` are generated from them with
`python -m grpc_tools.protoc -I . --python_out=. control.proto filter.proto`.

The daemon exposes the WebSocket port on the session bus
(`org.waywallen.waywallen.Daemon1`, property `WsPort`). Requests are sent as
raw `Request` messages; the server answers with `ServerFrame { response | event }`.
