import json
import time
from faker import Faker
from flask import Flask, request, Response


faker = Faker()
app = Flask(__name__)

res_len = 20

class ChunkReader:
    def __init__(self, chunks, delay):
        self.ID = ""
        self.Created = 0
        self.Chunks = chunks
        self.SentFinished = False
        self.SentDone = False
        self.Delay = delay

def new_chunk_reader(cs, d):
    return ChunkReader(cs, d)

def done(r):
    return r.SentFinished and r.SentDone

def next_chunk(r):
    if r.SentDone:
        return None, None

    if r.SentFinished:
        b = b"data: [DONE]\n\n"
        r.SentDone = True
        return b, None

    if len(r.Chunks) == 0:
        d = {
            "id": r.ID,
            "object": "chat.completion.chunk",
            "created": r.Created,
            "model": "gpt-3.5-turbo",
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }

        b = json.dumps(d).encode()
        r.SentFinished = True
        b = b"data: " + b + b"\n\n"
        return b, None

    c = r.Chunks[0] + " "
    d = {
        "id": r.ID,
        "object": "chat.completion.chunk",
        "created": r.Created,
        "model": "gpt-3.5-turbo",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "content": c,
                },
                "finish_reason": None,
            }
        ],
    }
    b = json.dumps(d).encode()
    r.Chunks = r.Chunks[1:]
    b = b"data: " + b + b"\n\n"
    return b, None

def read(r, p):
    if done(r):
        return 0, None

    if r.SentFinished:
        b = b"data: [DONE]\n\n"
        n = min(len(b), len(p))
        p[:n] = b[:n]
        r.SentDone = True
        return n, None

    if len(r.Chunks) == 0:
        d = {
            "id": r.ID,
            "object": "chat.completion.chunk",
            "created": r.Created,
            "model": "gpt-3.5-turbo",
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
        b = json.dumps(d).encode()
        b = b"data: " + b + b"\n\n"
        n = min(len(b), len(p))
        p[:n] = b[:n]
        r.SentFinished = True
        return n, None

    c = r.Chunks[0] + " "
    d = {
        "id": r.ID,
        "object": "chat.completion.chunk",
        "created": r.Created,
        "model": "gpt-3.5-turbo",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "content": c,
                },
                "finish_reason": None,
            }
        ],
    }
    b = json.dumps(d).encode()
    b = b"data: " + b + b"\n\n"
    n = min(len(b), len(p))
    p[:n] = b[:n]
    r.Chunks = r.Chunks[1:]
    time.sleep(r.Delay)
    return n, None

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    data = request.get_data()
    req = json.loads(data)

    ws = [faker.word() for _ in range(res_len)]
    ws = [" " + w if i > 0 else w for i, w in enumerate(ws)]

    if not req.get("stream"):
        m = "".join(ws)
        return {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": m,
                    },
                }
            ]
        }

    id = faker.uuid4()
    ct = int(time.time())
    sd = 0.5

    def generate():
        for w in ws:
            b, _ = next_chunk(chunk_reader)
            if b is not None:
                yield b
            time.sleep(sd)

        b, _ = next_chunk(chunk_reader)
        if b is not None:
            yield b

        yield b"[done]\n"

    chunk_reader = new_chunk_reader(ws, sd)
    return Response(generate(), content_type='text/event-stream')


@app.route('/v1/audio/transcriptions', methods=['POST'])
def transcribe():
    return {
        "text": faker.sentence(),
    }


@app.route('/v1/audio/translations', methods=['POST'])
def translate():
    return {
        "text": faker.sentence(),
    }


@app.route('/v1/images/generations', methods=['POST'])
def generate_image():
    return {
        "created": int(time.time()),
        "data": [
            {"url": faker.image_url()}
        ]
    }

@app.route('/v1/engines', methods=['GET'])
def list_engines():
    return {
        "object": "list",
        "data": [
            {
                "id": "model-id-0",
                "object": "model",
                "created": 1686935002,
                "owned_by": "organization-owner"
            },
            {
                "id": "model-id-1",
                "object": "model",
                "created": 1686935002,
                "owned_by": "organization-owner",
            },
            {
                "id": "model-id-2",
                "object": "model",
                "created": 1686935002,
                "owned_by": "openai"
            },
        ],
        "object": "list"
    }


def run(port=1323):
    app.run(host="0.0.0.0",port=port, debug=True)


def stop():
    app.stop()


if __name__ == "__main__":
    run()
