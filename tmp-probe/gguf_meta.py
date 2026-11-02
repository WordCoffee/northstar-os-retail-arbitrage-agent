"""Read GGUF metadata without any dependency: architecture, experts, context, quant."""
import json
import struct
import sys
from pathlib import Path

GGUF_MAGIC = b"GGUF"

# GGUF value types
TYPES = {0: "u8", 1: "i8", 2: "u16", 3: "i16", 4: "u32", 5: "i32", 6: "f32",
         7: "bool", 8: "string", 9: "array", 10: "u64", 11: "i64", 12: "f64"}


class Reader:
    def __init__(self, fh):
        self.fh = fh

    def take(self, n):
        return self.fh.read(n)

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.take(8))[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def i64(self):
        return struct.unpack("<q", self.take(8))[0]

    def f32(self):
        return struct.unpack("<f", self.take(4))[0]

    def f64(self):
        return struct.unpack("<d", self.take(8))[0]

    def u16(self):
        return struct.unpack("<H", self.take(2))[0]

    def u8(self):
        return struct.unpack("<B", self.take(1))[0]

    def i8(self):
        return struct.unpack("<b", self.take(1))[0]

    def i16(self):
        return struct.unpack("<h", self.take(2))[0]

    def string(self):
        n = self.u64()
        if n > 1_000_000:
            raise ValueError(f"implausible string length {n} - metadata desync")
        return self.take(n).decode("utf-8", errors="replace")

    def value(self, kind):
        if kind == 0: return self.u8()
        if kind == 1: return self.i8()
        if kind == 2: return self.u16()
        if kind == 3: return self.i16()
        if kind == 4: return self.u32()
        if kind == 5: return self.i32()
        if kind == 6: return self.f32()
        if kind == 7: return bool(self.u8())
        if kind == 8: return self.string()
        if kind == 10: return self.u64()
        if kind == 11: return self.i64()
        if kind == 12: return self.f64()
        if kind == 9:
            inner = self.u32()
            n = self.u64()
            # Consume EVERY element (a short read desyncs the rest of the file),
            # but only keep the first few for display.
            kept = []
            for i in range(n):
                v = self.value(inner)
                if i < 8:
                    kept.append(v)
            if n > 8:
                kept.append("...")
            return kept
        raise ValueError(f"gguf type {kind} ({TYPES.get(kind)}) unsupported here")


def read_metadata(path: Path, limit: int = 0):
    with open(path, "rb") as fh:
        r = Reader(fh)
        magic = r.take(4)
        if magic != GGUF_MAGIC:
            raise ValueError(f"not a GGUF file: {magic!r}")
        version = r.u32()
        tensor_count = r.u64()
        kv_count = r.u64()
        meta = {}
        for _ in range(kv_count):
            key = r.string()
            kind = r.u32()
            try:
                meta[key] = r.value(kind)
            except Exception as exc:  # noqa: BLE001
                meta[key] = f"<parse error {exc}>"
                break
            if limit and len(meta) >= limit:
                break
        return {"version": version, "tensors": tensor_count, "kv": kv_count, "meta": meta}


if __name__ == "__main__":
    path = Path(sys.argv[1])
    info = read_metadata(path)
    keep = {k: v for k, v in info["meta"].items()
            if any(s in k for s in ("architecture", "expert", "block_count", "context",
                                    "embedding_length", "name", "file_type", "quant",
                                    "feed_forward", "attention.head", "tokenizer.ggml.model"))}
    out = {"file": str(path), "size_gb": round(path.stat().st_size / 1024 ** 3, 2),
           "gguf_version": info["version"], "tensor_count": info["tensors"],
           "kv_count": info["kv"], "metadata": keep}
    print(json.dumps(out, indent=2, default=str))
