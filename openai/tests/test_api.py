import openai

openai.organization = "org-test"
openai.api_key = "test"
# openai.api_base = "http://localhost:1323/v1"
openai.api_base = "http://localhost:4566/_extension/openai/v1"


def test_list_models():
    models = openai.Engine.list()
    assert len(models.data) > 0


def test_chat_completion():
    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ],
    )
    assert len(completion.choices) > 0


def test_transcribe():
    transcript = openai.Audio.transcribe("whisper-1", open("sample.wav", "rb"))
    assert len(transcript.text) > 0


def test_translate():
    translate = openai.Audio.translate("whisper-1", open("sample.wav", "rb"))
    assert len(translate.text) > 0


def test_generate_image():
    response = openai.Image.create(prompt="a white siamese cat", n=1, size="1024x1024")
    assert response["data"][0]["url"]
