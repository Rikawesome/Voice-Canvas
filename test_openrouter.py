# test_whisper.py
import whisper

print("Loading model...")
model = whisper.load_model("tiny")
print("Model loaded! Testing transcription...")

# Create a test audio file or use an existing one
# result = model.transcribe("your_test_audio.wav")
# print(result["text"])
print("If you didn't crash, Whisper works!")