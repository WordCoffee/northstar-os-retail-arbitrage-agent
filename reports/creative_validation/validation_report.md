# Shared Creative — End-to-End Job Validation

Run: 2026-10-07T23:47:08

## routing
```json
{
  "check": "routing",
  "routing": {
    "draft": "z-image-draft",
    "standard": "sdxl-standard",
    "high": "sdxl-high",
    "explicit_lanes": [
      "qwen-t2i"
    ],
    "inpaint": "sdxl-inpaint"
  }
}
```

## product_ad
```json
{
  "check": "product_ad",
  "status": "done",
  "elapsed_s": 4.02,
  "output": {
    "exists": true,
    "size": [
      896,
      1152
    ],
    "mode": "RGB",
    "provenance": true,
    "provenance_lane": "shared_pipeline",
    "commercial_use": "allowed",
    "output_sha256": "ededd741b9137b6b"
  },
  "error": null
}
```

## packaging_concept
```json
{
  "check": "packaging_concept",
  "status": "done",
  "elapsed_s": 16.09,
  "concept": true,
  "disclaimer": true,
  "composited": {
    "exists": true,
    "size": [
      1024,
      1024
    ],
    "mode": "RGB",
    "provenance": true,
    "provenance_lane": "exact_text",
    "commercial_use": "allowed",
    "output_sha256": "63b517eeead2a8d0"
  },
  "error": null
}
```

## ad_layout
```json
{
  "check": "ad_layout",
  "status": "done",
  "elapsed_s": 2.0,
  "output": {
    "exists": true,
    "size": [
      1080,
      1080
    ],
    "mode": "RGB",
    "provenance": true,
    "provenance_lane": "shared_finishing",
    "commercial_use": "allowed",
    "output_sha256": "ad9e1a0af489809d"
  },
  "cutout": {
    "exists": true,
    "size": [
      896,
      1152
    ],
    "mode": "RGBA",
    "provenance": false
  },
  "error": null
}
```

## inpaint
```json
{
  "check": "inpaint",
  "status": "done",
  "elapsed_s": 12.04,
  "output": {
    "exists": true,
    "size": [
      896,
      1152
    ],
    "mode": "RGB",
    "provenance": true,
    "provenance_lane": "sdxl-inpaint",
    "commercial_use": "allowed",
    "output_sha256": "bc76e55c821c60b2"
  },
  "error": null
}
```

## failure_recovery
```json
{
  "check": "failure_recovery",
  "status": "error",
  "error_present": true,
  "error": "upscale requires an existing 'source' image path"
}
```

## cancellation
```json
{
  "check": "cancellation",
  "status": "cancelled"
}
```
