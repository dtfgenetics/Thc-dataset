#!/usr/bin/env python3
"""Starter transfer-learning training script for cannabis/hemp image classification.

This script is intentionally conservative and expects a split-safe manifest.
It is meant to be adapted to a fully reviewed, leakage-safe dataset once labels are
human-checked and the legal rights policy is finalized.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, Dataset
    from torchvision import transforms
    from torchvision.models import convnext_tiny, efficientnet_b0, efficientnet_v2_s
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f'Missing ML dependencies. Install training requirements first: {exc}')


def load_model_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    with config_path.open('r', encoding='utf-8') as handle:
        return json.load(handle)


class ManifestDataset(Dataset):
    def __init__(self, manifest_path: Path, image_root: Path, split: str | None = None, transform=None, limit: int | None = None):
        self.rows = []
        with manifest_path.open('r', encoding='utf-8', newline='') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row.get('image_path'):
                    continue
                if split and row.get('split') and row.get('split') != split:
                    continue
                self.rows.append(row)
        if limit is not None and limit > 0:
            self.rows = self.rows[:limit]
        self.image_root = image_root
        self.transform = transform or transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
        ])
        labels = sorted({row['label'] for row in self.rows if row.get('label')})
        self.label_to_index = {label: idx for idx, label in enumerate(labels)}

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        candidate = Path(row['image_path'])
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if not candidate.exists() and self.image_root is not None:
            candidate = self.image_root / Path(row['image_path']).name
        image = Image.open(candidate).convert('RGB')
        image = self.transform(image)
        label = self.label_to_index[row['label']]
        return image, label


def replace_classifier(model: nn.Module, num_classes: int) -> nn.Module:
    classifier = getattr(model, 'classifier', None)
    if classifier is None:
        raise ValueError('Model does not expose a classifier head for replacement.')

    if isinstance(classifier, nn.Sequential):
        last_layer = classifier[-1]
        if not hasattr(last_layer, 'in_features'):
            raise ValueError('Final classifier layer is not a linear layer.')
        classifier[-1] = nn.Linear(last_layer.in_features, num_classes)
        return model

    if hasattr(classifier, 'in_features'):
        model.classifier = nn.Linear(classifier.in_features, num_classes)
        return model

    raise ValueError('Unsupported classifier type for backbone replacement.')


def build_model(backbone_name: str, num_classes: int) -> nn.Module:
    backbone_name = backbone_name.lower()
    if backbone_name in {'efficientnet_b0', 'efficientnetv2_b0', 'efficientnet_v2_b0'}:
        model = efficientnet_b0(weights=None)
    elif backbone_name in {'efficientnet_v2_s', 'efficientnetv2_s'}:
        model = efficientnet_v2_s(weights=None)
    elif backbone_name in {'convnext_tiny', 'convnext'}:
        model = convnext_tiny(weights=None)
    else:
        raise ValueError(f'Unsupported backbone: {backbone_name}. Choose efficientnet_v2_s or convnext_tiny.')
    return replace_classifier(model, num_classes)


def evaluate_model(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    criterion = nn.CrossEntropyLoss()
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            total_loss += float(loss.item()) * images.size(0)
            predictions = outputs.argmax(dim=1)
            correct += int((predictions == labels).sum().item())
            total += labels.size(0)
    avg_loss = total_loss / max(1, total)
    accuracy = correct / max(1, total)
    return avg_loss, accuracy


def main() -> None:
    parser = argparse.ArgumentParser(description='Train a starter plant-health image classifier')
    parser.add_argument('--manifest', type=Path, default=Path('training/leakage_safe_split.csv'))
    parser.add_argument('--image-root', type=Path, default=Path('dataset/acquisition/acquired'))
    parser.add_argument('--split', choices=['train', 'val', 'test'], default='train')
    parser.add_argument('--eval-split', choices=['train', 'val', 'test'], default='val')
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--learning-rate', type=float, default=1e-4)
    parser.add_argument('--max-samples', type=int, default=0, help='Optional cap for train/val/test rows used in a smoke test; 0 means no limit.')
    parser.add_argument('--backbone', type=str, default=None, help='Model backbone name: efficientnet_v2_s or convnext_tiny')
    parser.add_argument('--config', type=Path, default=Path('training/model_config.json'))
    args = parser.parse_args()

    config = load_model_config(args.config)
    config_backbone = str(config.get('default_backbone', 'efficientnet_v2_s')).lower()
    backbone_name = (args.backbone or config_backbone).lower()

    dataset = ManifestDataset(args.manifest, args.image_root, split=args.split, limit=args.max_samples or None)
    if not dataset.rows:
        raise SystemExit(f'No rows found for split={args.split} in {args.manifest}')

    num_classes = len(dataset.label_to_index)
    if num_classes < 2:
        raise SystemExit(f'Only {num_classes} label(s) available in {args.manifest}; add more reviewed labels before training.')

    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)
    model = build_model(backbone_name, num_classes)
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

    if args.eval_split != args.split:
        eval_dataset = ManifestDataset(args.manifest, args.image_root, split=args.eval_split, limit=args.max_samples or None)
        if eval_dataset.rows:
            eval_loader = DataLoader(eval_dataset, batch_size=max(1, args.batch_size), shuffle=False)
            eval_loss, eval_accuracy = evaluate_model(model, eval_loader, device)
            print(f'eval_split={args.eval_split} loss={eval_loss:.4f} accuracy={eval_accuracy:.4f}')

    print(f'Training complete on {args.split} split with backbone={backbone_name}. This is a starter only; add human-reviewed labels and a locked benchmark before production use.')


if __name__ == '__main__':
    main()
