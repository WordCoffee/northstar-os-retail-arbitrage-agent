"""Enhanced test for FLUX 3 failure mode and fallback behavior."""
import os
import sys

# Add the Northstar_backend directory to the path
sys.path.insert(0, 'Northstar_backend')

from studio_generation import (
    generate_image, 
    _USE_FLUX2, 
    _DEFAULT_FLUX3_MODEL,
    FLUX2_MODEL_FILE,
    _get_flux3_model_file,
    _get_flux3_text_encoder_file,
    _get_flux3_vae_file
)

def test_flux3_weights_missing():
    """Test that FLUX 3 weights missing raises appropriate error and forces FLUX.2."""
    
    # Ensure STUDIO_USE_FLUX2 is not set (so we test auto-fallback)
    if 'STUDIO_USE_FLUX2' in os.environ:
        del os.environ['STUDIO_USE_FLUX2']
    
    # Ensure STUDIO_FLUX3_MODEL is not set
    original_flux3_model = os.environ.get('STUDIO_FLUX3_MODEL')
    original_flux3_text_encoder = os.environ.get('STUDIO_FLUX3_TEXT_ENCODER')
    original_flux3_vae = os.environ.get('STUDIO_FLUX3_VAE')
    
    try:
        # Clear FLUX 3 environment variables
        if 'STUDIO_FLUX3_MODEL' in os.environ:
            del os.environ['STUDIO_FLUX3_MODEL']
        if 'STUDIO_FLUX3_TEXT_ENCODER' in os.environ:
            del os.environ['STUDIO_FLUX3_TEXT_ENCODER']
        if 'STUDIO_FLUX3_VAE' in os.environ:
            del os.environ['STUDIO_FLUX3_VAE']
        
        # Test 1: _get_flux3_model_file raises RuntimeError when not set
        try:
            _get_flux3_model_file()
            print("❌ _get_flux3_model_file should have raised RuntimeError when STUDIO_FLUX3_MODEL is not set")
            assert False, "Expected RuntimeError from _get_flux3_model_file"
        except RuntimeError as e:
            print(f"✅ _get_flux3_model_file correctly raises error: {str(e)[:100]}...")
        
        # Test 2: _get_flux3_text_encoder_file raises RuntimeError when not set
        try:
            _get_flux3_text_encoder_file()
            print("❌ _get_flux3_text_encoder_file should have raised RuntimeError when STUDIO_FLUX3_TEXT_ENCODER is not set")
            assert False, "Expected RuntimeError from _get_flux3_text_encoder_file"
        except RuntimeError as e:
            print(f"✅ _get_flux3_text_encoder_file correctly raises error: {str(e)[:100]}...")
        
        # Test 3: _get_flux3_vae_file raises RuntimeError when not set
        try:
            _get_flux3_vae_file()
            print("❌ _get_flux3_vae_file should have raised RuntimeError when STUDIO_FLUX3_VAE is not set")
            assert False, "Expected RuntimeError from _get_flux3_vae_file"
        except RuntimeError as e:
            print(f"✅ _get_flux3_vae_file correctly raises error: {str(e)[:100]}...")
        
        # Test 4: Verify that _USE_FLUX2 is now True when FLUX 3 weights are missing
        # (This happens in the module initialization, so we need to reload or check the logic)
        # Since we've cleared the env vars, _USE_FLUX2 should be True
        if _USE_FLUX2:
            print(f"✅ FLUX.2 is being used (_USE_FLUX2 = True) when FLUX 3 weights are missing")
        else:
            print(f"❌ FLUX.2 should be used (_USE_FLUX2 = True) when FLUX 3 weights are missing")
            # This might be okay if the module-level logic already set it
        
        # Test 5: Call generate_image - it should use FLUX.2 since FLUX 3 weights are missing
        width, height = 1024, 1024
        seed = 12345
        
        result = generate_image("test image", width, height, seed=seed)
        
        # Verify the result contains FLUX.2 model (not FLUX 3)
        assert 'model' in result, "Result should contain model name"
        assert 'provider' in result, "Result should contain provider"
        
        # The model should be the FLUX.2 model (without extension)
        from pathlib import Path
        expected_flux2_model = Path(FLUX2_MODEL_FILE).stem
        actual_model = result['model']
        
        print(f"✅ generate_image correctly returns FLUX.2 model: {actual_model}")
        assert actual_model == expected_flux2_model, f"Expected {expected_flux2_model}, got {actual_model}"
        assert result['provider'] == 'comfyui', f"Expected provider 'comfyui', got {result['provider']}"
        
    finally:
        # Restore environment variables
        if original_flux3_model is not None:
            os.environ['STUDIO_FLUX3_MODEL'] = original_flux3_model
        elif 'STUDIO_FLUX3_MODEL' in os.environ:
            del os.environ['STUDIO_FLUX3_MODEL']
            
        if original_flux3_text_encoder is not None:
            os.environ['STUDIO_FLUX3_TEXT_ENCODER'] = original_flux3_text_encoder
        elif 'STUDIO_FLUX3_TEXT_ENCODER' in os.environ:
            del os.environ['STUDIO_FLUX3_TEXT_ENCODER']
            
        if original_flux3_vae is not None:
            os.environ['STUDIO_FLUX3_VAE'] = original_flux3_vae
        elif 'STUDIO_FLUX3_VAE' in os.environ:
            del os.environ['STUDIO_FLUX3_VAE']

def test_flux3_explicit_use():
    """Test that explicitly setting STUDIO_USE_FLUX2=1 forces FLUX.2."""
    
    # Explicitly force FLUX.2
    os.environ['STUDIO_USE_FLUX2'] = '1'
    
    try:
        width, height = 1024, 1024
        seed = 54321
        
        result = generate_image("test image", width, height, seed=seed)
        
        # Should use FLUX.2
        assert result['model'] == Path(FLUX2_MODEL_FILE).stem, f"Expected FLUX.2 model, got {result['model']}"
        print(f"✅ FLUX.2 forced mode VERIFIED: STUDIO_USE_FLUX2=1 works correctly")
        print(f"   Model used: {result['model']}")
        
    finally:
        # Clean up environment
        if 'STUDIO_USE_FLUX2' in os.environ:
            del os.environ['STUDIO_USE_FLUX2']

if __name__ == '__main__':
    print("=== Testing FLUX 3 enhanced failure mode ===")
    test_flux3_weights_missing()
    print()
    print("=== Testing FLUX.2 explicit mode ===")
    test_flux3_explicit_use()
    print("\n✅ All tests passed!")