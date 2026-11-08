with open('Northstar_backend/studio_generation.py', 'rb') as f:
    content = f.read()

idx = content.find(b'_USE_FLUX2 = str(os.environ.get')
if idx < 0:
    print('Not found')
    exit(1)

actual = content[idx:idx+400]
print('Actual bytes (400):')
print(repr(actual))
print('Actual length:', len(actual))