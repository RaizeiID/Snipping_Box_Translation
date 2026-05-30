import ctranslate2
import sentencepiece as spm

model_dir = r"models\ct2_opus_mt_en_id"

src = spm.SentencePieceProcessor()
src.load(model_dir + r"\source.spm")

tgt = spm.SentencePieceProcessor()
tgt.load(model_dir + r"\target.spm")

translator = ctranslate2.Translator(model_dir, device="cuda", compute_type="int8_float16")

tokens = src.encode("Hello world!", out_type=str)
tokens.append("</s>")

result = translator.translate_batch([tokens], beam_size=1, max_decoding_length=64)
output_tokens = result[0].hypotheses[0]

print("TOKENS:", output_tokens)
print("TEXT:", tgt.decode(output_tokens))
print("Fast CT2 test OK")
