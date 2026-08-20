import os
from typing import Optional

class SpeechTranscriber:
    """
    Dual-Pathway Speech Recognition (Chapter 3.4)
    Primary: Offline Vosk API (vosk-model-small-en-us-0.15)
    Secondary / Fallback: SpeechRecognition (Google Web Speech / CMU Sphinx)
    """

    @classmethod
    def transcribe_audio_file(cls, wav_path: str) -> str:
        # Try Vosk first (Offline)
        try:
            from vosk import Model, KaldiRecognizer
            import wave
            import json
            
            model_path = os.path.expanduser("~/.esim/vosk_model")
            if os.path.exists(model_path):
                wf = wave.open(wav_path, "rb")
                model = Model(model_path)
                rec = KaldiRecognizer(model, wf.getframerate())
                
                results = []
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    if rec.AcceptWaveform(data):
                        res = json.loads(rec.Result())
                        results.append(res.get("text", ""))
                res_final = json.loads(rec.FinalResult())
                results.append(res_final.get("text", ""))
                return " ".join([r for r in results if r]).strip()
        except Exception:
            pass

        # Fallback to SpeechRecognition
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio = r.record(source)
            try:
                return r.recognize_google(audio)
            except Exception:
                return r.recognize_sphinx(audio)
        except Exception as e:
            return ""
