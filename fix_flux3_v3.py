with open('Northstar_backend/studio_generation.py', 'rb') as f:
    content = f.read()

old = b'_USE_FLUX2 = str(os.environ.get("STUDIO_USE_FLUX2", "") or "").strip() == "1"\nIMAGE_MODEL_FILE = FLUX2_MODEL_FILE if _USE_FLUX2 else os.environ.get("STUDIO_IMAGE_MODEL") or "flux-3-klein-base-9b-Q6_K.gguf"\nTEXT_ENCODER_FILE = FLUX2_TEXT_ENCODER_FILE if _USE_FLUX2 else os.environ.get("STUDIO_TEXT_ENCODER") or "qwen_3_4b_fp8mixed.safetensors"'

new = b'''# Default image model: FLUX 3 (distilled). Set STUDIO_USE_FLUX2=1 to fall back to FLUX.2.
# Auto-fallback to FLUX.2 if FLUX 3 model file is not found.
def _model_file_exists(model_file: str) -> bool:
    import pathlib
    base = pathlib.Path(r"C:\\Users\\T2Hol\\ComfyUI\\models\\diffusion_models")
    return (base / model_file).exists()

_USE_FLUX2 = str(os.environ.get("STUDIO_USE_FLUX2", "") or "").strip() == "1"
if not _USE_FLUX2:
    _DEFAULT_FLUX3_MODEL = "flux-3-klein-base-9b-Q6_K.gguf"
    if not _model_file_exists(_DEFAULT_FLUX3_MODEL):
        _USE_FLUX2 = True  # Auto-fallback if FLUX 3 model not found

IMAGE_MODEL_FILE = FLUX2_MODEL_FILE if _USE_FLUX2 else os.environ.get("STUDIO_IMAGE_MODEL") or "flux-3-klein-base-9b-Q6_K.gguf"
TEXT_ENCODER_FILE = FLUX2_TEXT_ENCODER_FILE if _USE_FLUX2 else os.environ.get("STUDIO_TEXT_ENCODER") or "qwen_3_4b_fp8mixed.safetensors"'''

if old in content:
    content = content.replace(old, new)
    with open('Northstar_backend/studio_generation.py', 'wb') as f:
        f.write(content)
    print('Replaced successfully')
else:
    print('Old string not found')
    idx = content.find(b'_USE_FLUX2 = str(os.environ.get')
    if idx >= 0:
        print(f'Found at index {idx}:')
        print(content[idx:idx+300])
    else:
        print('Not found at all')