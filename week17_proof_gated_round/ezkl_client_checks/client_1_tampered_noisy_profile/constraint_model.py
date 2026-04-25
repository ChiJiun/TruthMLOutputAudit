from __future__ import annotations
import torch
import torch.nn as nn

class ConstraintCheckModel(nn.Module):
    def forward(self, packed: torch.Tensor) -> torch.Tensor:
        q_clipped = packed[:, 0:10]
        q_noise = packed[:, 10:20]
        q_noisy = packed[:, 20:30]
        expected_noisy = q_clipped + q_noise
        clip_sum_sq = torch.sum(q_clipped * q_clipped, dim=1, keepdim=True)
        relation_sum_sq = torch.sum((q_noisy - expected_noisy) ** 2, dim=1, keepdim=True)
        return torch.cat([clip_sum_sq, relation_sum_sq], dim=1)
