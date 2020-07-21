from google.cloud import speech
import base64
import os
import json
import io
import re
from urllib3 import request


from google.cloud.speech import types
from google.oauth2 import service_account
from main_app.transcript_data_extractor import data_extractor
# Instantiates a client

creds1 = json.loads(base64.b64decode(os.environ['G_AUTH']).decode())
SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

credentials = service_account.Credentials.from_service_account_info(creds1, scopes=SCOPES)
client = speech.SpeechClient(credentials=credentials)

# Loads the audio into memory

file_name = os.path.join(os.path.dirname(__file__), 'testAudioDir/data6.flac')

# TO READ FROM FILE
with io.open(file_name, 'rb') as audio_file:
    content = audio_file.read()


b642 = base64.encodebytes(content)

# CHOOSE DATA FROM audio_dataset
# encoded = audio_dataset.data2
decoded = base64.b64decode(b642)

# response = client.recognize(
#     config=speech.types.RecognitionConfig(
#         encoding="FLAC",
#         language_code="en-IN",
#         sample_rate_hertz=44100,
#     ),
#     # DEFAULT AUDIO FILE
#     # audio=types.RecognitionAudio(content=encoded)
#     # audio=audio
#     # audio={"content": enc.encode('UTF-8')}
#     # audio={"uri":"gs://cloud-samples-tests/speech/brooklyn.flac"}
# )

link = "https://host1ibn9yh.cloudconvert.com/download/~rpAM1je_eQceN5sDpLpVqgAElH8"
audio_content = request.urlopen(link)
b64 = base64.b64encode(audio_content)
decoded = base64.b64decode(b64)

# ASYNC SPEECH RECOG
audio=types.RecognitionAudio(content=decoded)
config=types.RecognitionConfig(
    encoding="FLAC",
    sample_rate_hertz=44100,
    language_code="en-IN",
)


operation = client.long_running_recognize(config=config, audio=audio)
print('Waiting for operation to complete...')
response = operation.result(timeout=90)
transcript = ""
for result in response.results:
    transcript = result.alternatives[0].transcript
    print('Transcript: {}'.format(transcript))
#     # print('Confidence: {}'.format(result.alternatives[0].confidence))


# data = data_extractor(textvalue, "For Warmline. You have a voicemail from 9971816121")

