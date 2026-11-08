with open('Northstar_backend/studio_generation.py', 'rb') as f:
    content = f.read()

idx = content.find(b'_USE_FLUX2 = str(os.environ.get')
if idx < 0:
    print('Not found')
    exit(1)

actual = content[idx:idx+200]
print('Actual bytes:')
print(repr(actual))

expected = b'_USE_FLUX2 = str(os.environ.get("STUDIO_USE_FLUX2", "") or "").strip() == "1"\nIMAGE_MODEL_FILE = FLUX2_MODEL_FILE if _USE_FLUX2 else os.environ.get("STUDIO_IMAGE_MODEL") or "flux-3-klein-base-9b-Q6_K.gguf"\nTEXT_ENCODER_FILE = FLUX2_TEXT_ENCODER_FILE if _USE_FLUX2 else os.environ.get("STUDIO_TEXT_ENCODER") or "qwen_3_4b_fp8mixed.safetensors"'
print('Expected:')
print(repr(expected))
print('Match:', actual.startswith(expected))
print('Actual length:', len(actual))
print('Expected length:', len(expected))