#!/usr/bin/env python3
"""Starter transfer-learning training script for cannabis/hemp image classification.

This script is intentionally conservative and expects a split-safe manifest.
It is meant to be adapted to a fully reviewed, leakage-safe dataset once labels are
human-checked and the legal rights policy is finalized.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset
    from torchvision import transforms
    from torchvision.models import efficientnet_b0
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f'Missing ML dependencies. Install training requirements first: {exc}')


class ManifestDataset(Dataset):
    def __init__(self, manifest_path: Path, image_root: Path, split: str | None = None, transform=None):
        self.rows = []
        with manifest_path.open('r', encoding='utf-8', newline='') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row.get('image_path'):
                    continue
                if split and row.get('split') and row.get('split') != split:
                    continue
                self.rows.append(row)
        self.image_root = image_root
        self.transform = transform or transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
        ])
        self.label_to_index = {label: idx for idx, label in enumerate(sorted({row['label'] for row in self.rows}))}

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        image_path = ROOT / row['image_path']
        image = Image.open(image_path).convert('RGB')
        image = self.transform(image)
        label = self.label_to_index[row['label']]
        return image, label


def build_model(num_classes: int) -> nn.Module:
    model = efficientnet_b0(weights=None)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description='Train a starter plant-health image classifier')
    parser.add_argument('--manifest', type=Path, default=Path('training/leakage_safe_split.csv'))
    parser.add_argument('--image-root', type=Path, default=Path('dataset/acquisition/acquired'))
    parser.add_argument('--split', choices=['train', 'val', 'test'], default='train')
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--learning-rate', type=float, default=1e-4)
    args = parser.parse_args()

    dataset = ManifestDataset(args.manifest, args.image_root, split=args.split)
    if not dataset.rows:
        raise SystemExit(f'No rows found for split={args.split} in {args.manifest}')

    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)
    model = build_model(len(set(row['label'] for row in dataset.rows)))
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    criterion = nn.CrossEntropyLoss()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)

    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())
        print(f'epoch={epoch + 1} loss={total_loss / max(1, len(loader)):.4f}')

    print(f'Training complete on {args.split} split. This is a starter only; add human-reviewed labels and a locked benchmark before production use.')


if __name__ == '__main__':
    main()
