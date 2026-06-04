import math
import os
from contextlib import contextmanager

import torch
import torch.nn as nn

_LORA_ENABLED = True


@contextmanager
def lora_mode(enabled: bool):
    """Context manager to dynamically enable or disable LoRA adapters during execution.

    Usage:
        with lora_mode(False):
            # Runs pure baseline weights
            emissions, _ = model(waveforms)
    """
    global _LORA_ENABLED
    previous_state = _LORA_ENABLED
    _LORA_ENABLED = enabled
    try:
        yield
    finally:
        _LORA_ENABLED = previous_state


def load_lora_adapter(
    model: nn.Module, checkpoint_path: str, strict: bool = False
):
    """
    Loads saved LoRA adapter weights from a structured checkpoint bundle
    into an already structure-adapted model.
    """
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            f"No adapter checkpoint found at: {checkpoint_path}"
        )

    # 1. Load the dictionary bundle from disk
    checkpoint_bundle = torch.load(checkpoint_path, map_location="cpu")

    # 2. Extract the model layer weights out of the dictionary
    if (
        isinstance(checkpoint_bundle, dict)
        and "model_state_dict" in checkpoint_bundle
    ):
        adapter_state_dict = checkpoint_bundle["model_state_dict"]

        # Print a helpful log tracking exactly what you are loading
        epoch = checkpoint_bundle.get("epoch", "Unknown")
        val_loss = checkpoint_bundle.get("val_loss", float("inf"))
        print(
            f"📦 Extracting weights from Epoch {epoch} checkpoint (Validation Loss: {val_loss:.4f})"
        )
    else:
        # Fallback to handle old, raw checkpoints if you have any left over
        adapter_state_dict = checkpoint_bundle
        print(
            "⚠️ Warning: Loading a legacy raw weights file (no metadata found)."
        )

    # 3. strict=False because the state dict only holds 1% of the total weights (the LoRA layers)
    model.load_state_dict(adapter_state_dict, strict=strict)
    print("✅ Adapter weights loaded successfully into the main architecture.")

    return model


class LoRALinear(nn.Module):
    def __init__(
        self,
        original_linear_layer: nn.Linear,
        r: int = 8,
        alpha: int = 16,
    ):
        super().__init__()
        self.original_layer = original_linear_layer

        in_features = self.original_layer.in_features
        out_features = self.original_layer.out_features

        self.r = r
        self.alpha = alpha
        self.scaling = alpha / r

        # Down-sampler, initialized with standard Gaussian distribution
        self.lora_A = nn.Parameter(torch.zeros(in_features, r))

        # Up-sampler, initialized to zero so the adapter starts inactive
        self.lora_B = nn.Parameter(torch.zeros(r, out_features))

        self.reset_parameters()

    def reset_parameters(self):
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        base_output = self.original_layer(x)
        if _LORA_ENABLED:
            adapter_output = (x @ self.lora_A) @ self.lora_B
            return base_output + (adapter_output * self.scaling)

        return base_output


def apply_lora_to_wav2vec2(model: nn.Module, r: int = 8, alpha: int = 16):
    """
    Traverses the torchaudio Wav2Vec2 architecture, targeting and adapting
    the Query and Value projections inside all 12 self-attention layers.
    """
    model.requires_grad_(False)
    adapted_layers_count = 0

    for transformer_block in model.encoder.transformer.layers:
        attention_block = transformer_block.attention

        attention_block.q_proj = LoRALinear(
            attention_block.q_proj, r=r, alpha=alpha
        )
        attention_block.v_proj = LoRALinear(
            attention_block.v_proj, r=r, alpha=alpha
        )

        adapted_layers_count += 2

    print(
        f"Successfully injected LoRA side-cars into {adapted_layers_count} layers."
    )
    return model
