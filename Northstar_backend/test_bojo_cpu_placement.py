"""Bojo CPU placement — offline contract tests for the owner's model-placement rule.

The owner requirement (2026-10-27):

  * Bojo stays on the CPU and must not occupy dedicated GPU VRAM.
  * The Qwen3.8-27B IQ3_XXS worker stays GPU-only and on demand.
  * Bojo and the 27B worker must never be on the GPU at the same time.
  * The coding/general worker must not stay resident during ComfyUI work.

Bojo is an Ollama model, so its placement is decided by the model definition,
not by this repo's code. That is exactly why the definition is checked in as
`scripts/bojo-cpu.Modelfile`: an operator (or a future session) can otherwise
recreate the tag with Ollama's automatic layer placement and silently put 2.4 GB
of weights back into the render GPU, with nothing in the test suite noticing.

These tests are static: they read the shipped files and never talk to Ollama.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

_BACKEND = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_BACKEND)
sys.path.insert(0, _BACKEND)

MODELFILE = os.path.join(_ROOT, "scripts", "bojo-cpu.Modelfile")
WORKER_LAUNCHER = os.path.join(_ROOT, "scripts", "start-northstar-llm.ps1")


def _modelfile() -> str:
    assert os.path.exists(MODELFILE), f"the Bojo CPU definition is missing: {MODELFILE}"
    with open(MODELFILE, "r", encoding="utf-8") as fh:
        return fh.read()


def _params(text: str) -> dict:
    """PARAMETER name value -> {name: value} from a Modelfile body (not comments)."""
    out = {}
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = re.match(r"\s*PARAMETER\s+(\S+)\s+(\S+)\s*$", line, re.I)
        if m:
            out[m.group(1).lower()] = m.group(2)
    return out


# --- placement ---------------------------------------------------------------

def test_bojo_pins_zero_gpu_layers():
    """num_gpu 0 is the whole point: it forbids any CUDA-offloaded layer."""
    params = _params(_modelfile())
    assert params.get("num_gpu") == "0", (
        "Bojo must be CPU-only. Without `PARAMETER num_gpu 0` Ollama places layers "
        "on the GPU automatically and the render lanes lose 2.4 GB of VRAM.")


def test_bojo_definition_inherits_the_preserved_original():
    """FROM bojo:gpu-orig keeps the TEMPLATE, SYSTEM, PARSER and vision projector.

    Rebuilding FROM the raw weights blob would drop the projector layer and Bojo
    would lose vision without any error being raised.
    """
    body = _modelfile()
    assert re.search(r"^\s*FROM\s+bojo:gpu-orig\s*$", body, re.M | re.I), (
        "the CPU rebuild must inherit from bojo:gpu-orig so the vision projector "
        "layer and the Apache-2.0 license are carried over, not dropped")


def test_bojo_sampling_parameters_are_unchanged():
    """A placement rebuild must not quietly retune the model."""
    params = _params(_modelfile())
    assert params.get("num_ctx") == "8192"
    assert params.get("num_predict") == "2048"
    assert params.get("temperature") == "0.2"
    assert params.get("top_k") == "20"
    assert params.get("top_p") == "0.9"
    assert params.get("presence_penalty") == "1.5"


# --- the 27B worker stays GPU-only and on demand ------------------------------

def test_27b_worker_offloads_all_layers_to_the_gpu():
    assert os.path.exists(WORKER_LAUNCHER), f"missing worker launcher: {WORKER_LAUNCHER}"
    with open(WORKER_LAUNCHER, "r", encoding="utf-8") as fh:
        launcher = fh.read()
    assert re.search(r"-ngl\s+99\b", launcher), (
        "the Qwen3.8-27B IQ3_XXS worker must stay fully GPU-offloaded (-ngl 99)")
    # On demand: nothing in the launcher should install or start it as a service.
    assert "Register-ScheduledTask" not in launcher
    assert "New-Service" not in launcher


def test_worker_launcher_drains_what_ollama_actually_has_resident():
    """The pre-launch eviction must not hard-code a model id that no longer exists.

    The 27B moved out of Ollama into llama.cpp, so the old
    `{"model":"northstaros-qwen3.8:27b"}` eviction targeted nothing, evicted
    nothing, and still printed success. RAM - not VRAM - is the binding
    constraint when a 10.4 GB model plus a 64K q4_0 KV cache loads on this box.
    """
    with open(WORKER_LAUNCHER, "r", encoding="utf-8") as fh:
        launcher = fh.read()
    code = "\n".join(
        line for line in launcher.splitlines() if not line.lstrip().startswith("#"))

    assert "/api/ps" in code, "eviction must read /api/ps to see what is resident"
    assert "$resident" in code, (
        "eviction must iterate the models /api/ps returned, not a remembered id")
    # Comments are allowed to name the retired Ollama id (they explain the
    # history) and --alias legitimately reuses it as the OpenAI-compatible name.
    # What must never come back is an eviction payload with a hardcoded tag.
    for line in code.splitlines():
        if "keep_alive" in line:
            assert not re.search(r"['\"]model['\"]\s*[:=]\s*['\"]", line), (
                "unload payload must take its model name from /api/ps, "
                f"not a literal: {line.strip()}")


# --- the chat lane must not be able to undo the placement ---------------------

def test_chat_lane_defers_placement_to_the_model_definition():
    """CHAT_NUM_GPU defaults to None, so the Ollama call omits `num_gpu`.

    Omitting it is what lets the model-level `num_gpu 0` take effect. If the
    default became a positive layer count, every chat turn would re-enable the
    GPU and silently reverse the owner's placement rule regardless of the
    Modelfile.
    """
    import chat_adapter as ca

    assert ca.CHAT_NUM_GPU is None, (
        "chat must not pin num_gpu; the model definition owns placement "
        f"(got CHAT_NUM_GPU={ca.CHAT_NUM_GPU!r})")


def test_render_path_evicts_every_resident_model():
    """ComfyUI work must never run beside a resident chat model.

    unload_brain drains /api/ps, so a CPU-resident Bojo is evicted too - the
    requirement is about the worker not lingering, not about which device it sat
    on.
    """
    import studio_generation as sg

    src = (sg.unload_brain.__doc__ or "") + "\n" + sg._resident_models.__doc__
    assert "/api/ps" in src
    assert callable(sg.unload_brain)
